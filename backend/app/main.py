import logging
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, File, Form, HTTPException, Security, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyHeader

from app.config import settings
from app.database import db_manager
from app.ingestion import ingest_document
from app.retrieval import answer_with_rag
from app.schemas import (
    ArxivIngestRequest,
    DiagnosticsResponse,
    DocumentInfo,
    HealthResponse,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)
from app.utils import fetch_arxiv_paper, get_uptime_seconds

logger = logging.getLogger("cogniflow.main")

# ----------------------------------------------------
# 1. API KEY AUTHENTICATION
# ----------------------------------------------------
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(x_api_key: str = Security(api_key_header)):
    """
    Verifies the client API key header if the API_KEY environment variable is configured.
    """
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Invalid or missing X-API-Key header.",
        )
    return x_api_key


# ----------------------------------------------------
# 2. LIFESPAN MANAGEMENT & STARTUP SEEDING
# ----------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Initializing CogniFlow RAG Backend...")

    # 1. Verify Chroma DB connection
    try:
        stats = db_manager.get_stats()
        logger.info(f"Connected to ChromaDB SQLite Store. Count stats: {stats}")
    except Exception as e:
        logger.error(f"ChromaDB connection check failed: {e}")

    # 2. Verify Ollama Connection (Optional verification - don't crash startup)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=5.0
            )
            if resp.status_code == 200:
                logger.info("Successfully reached Ollama local server.")
    except Exception as e:
        logger.warning(
            f"Ollama local server not reached during startup: {e}. (Ensure it is running at {settings.ollama_base_url})"
        )

    # 3. Seed Sample Documents on empty DB
    if settings.seed_sample_docs:
        try:
            stats = db_manager.get_stats()
            # If public collection is empty, seed it
            if stats["public_count"] == 0:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sample_txt_path = os.path.join(base_dir, "sample_docs", "rag_overview.txt")
                if os.path.exists(sample_txt_path):
                    logger.info("Seeding database with sample RAG overview document...")
                    with open(sample_txt_path, "rb") as f:
                        file_bytes = f.read()
                    await ingest_document(
                        collection_type="public",
                        file_name="rag_overview.txt",
                        file_bytes=file_bytes,
                        file_type="txt",
                        title="Introduction to RAG Systems",
                    )

            # If papers collection is empty, seed it
            if stats["papers_count"] == 0:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sample_md_path = os.path.join(base_dir, "sample_docs", "hybrid_search_guide.md")
                if os.path.exists(sample_md_path):
                    logger.info("Seeding database with sample Hybrid Search guide document...")
                    with open(sample_md_path, "rb") as f:
                        file_bytes = f.read()
                    await ingest_document(
                        collection_type="papers",
                        file_name="hybrid_search_guide.md",
                        file_bytes=file_bytes,
                        file_type="md",
                        title="Advanced RAG Strategies Guide",
                    )
        except Exception as e:
            logger.error(f"Error seeding sample documents: {e}")

    yield
    # Shutdown tasks
    logger.info("Shutting down CogniFlow RAG Backend...")


# ----------------------------------------------------
# 3. FASTAPI APPLICATION INITIALIZATION
# ----------------------------------------------------
app = FastAPI(
    title="CogniFlow Platform API",
    description="Local-first RAG vector engine orchestrator",
    version="1.0.0",
    docs_url=None if settings.disable_openapi else "/docs",
    redoc_url=None if settings.disable_openapi else "/redoc",
    openapi_url=None if settings.disable_openapi else "/openapi.json",
    lifespan=lifespan,
)

# CORS configurations for Streamlit and Next.js operations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In local dev allow all; configure specifically if deploying
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------
# 4. PUBLIC ROUTE ENDPOINTS
# ----------------------------------------------------
@app.get("/", include_in_schema=False)
async def root():
    """
    Redirects to docs endpoint or health status.
    """
    if not settings.disable_openapi:
        return RedirectResponse(url="/docs")
    return {"message": "CogniFlow RAG Platform Backend is running."}


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """
    Provides lightweight health check endpoint.
    """
    return HealthResponse(
        status="healthy", version="1.0.0", uptime_seconds=round(get_uptime_seconds(), 2)
    )


@app.get("/api/readiness")
async def readiness():
    """
    Checks readiness of external systems (Ollama + ChromaDB).
    Returns 200 OK or 503 Service Unavailable.
    """
    chroma_ok = False
    ollama_ok = False

    try:
        db_manager.get_stats()
        chroma_ok = True
    except Exception:
        pass

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                ollama_ok = True
    except Exception:
        pass

    if not (chroma_ok and (ollama_ok or settings.gemini_api_key)):
        # If Gemini is configured, we don't strictly require Ollama LLM readiness
        # (though we still need it for embeddings).
        # We raise a 503 if core services are offline.
        detail_msg = f"ChromaDB: {'ONLINE' if chroma_ok else 'OFFLINE'}, Ollama: {'ONLINE' if ollama_ok else 'OFFLINE'}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service Unavailable. System status: {detail_msg}",
        )

    return {"status": "ready"}


@app.get(
    "/api/diagnostics", response_model=DiagnosticsResponse, dependencies=[Depends(verify_api_key)]
)
async def diagnostics():
    """
    Provides comprehensive server statistics, settings, and health metadata.
    Protected by X-API-Key if configured.
    """
    chroma_ok = False
    ollama_ok = False

    try:
        stats = db_manager.get_stats()
        chroma_ok = True
        public_count = stats.get("public_count", 0)
        papers_count = stats.get("papers_count", 0)
    except Exception:
        public_count = 0
        papers_count = 0

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                ollama_ok = True
    except Exception:
        pass

    return DiagnosticsResponse(
        status="healthy" if (chroma_ok and ollama_ok) else "degraded",
        version="1.0.0",
        uptime_seconds=round(get_uptime_seconds(), 2),
        public_count=public_count,
        papers_count=papers_count,
        threshold=settings.relevance_threshold,
        ollama_connected=ollama_ok,
        chroma_connected=chroma_ok,
        git_sha=settings.cogniflow_git_sha,
    )


# ----------------------------------------------------
# 5. DATA INGESTION & QUERY ENDPOINTS (PROTECTED)
# ----------------------------------------------------
@app.post("/api/ingest", response_model=IngestResponse, dependencies=[Depends(verify_api_key)])
async def ingest_file(
    collection_type: str = Form(
        ..., description="Target database collection: 'public' or 'papers'"
    ),
    file: UploadFile = File(...),
):
    """
    Ingests and vectorizes uploaded PDF, DOCX, or TXT document.
    """
    # Verify file size
    file_bytes = await file.read()
    file_size_mb = len(file_bytes) / (1024 * 1024)
    if file_size_mb > settings.max_file_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size of {settings.max_file_size_mb}MB.",
        )

    # Ingest document
    file_ext = os.path.splitext(file.filename)[1].lstrip(".")
    try:
        result = await ingest_document(
            collection_type=collection_type,
            file_name=file.filename,
            file_bytes=file_bytes,
            file_type=file_ext,
        )
        return IngestResponse(
            source=result["source"],
            title=result["title"],
            chunks_count=result["chunks_count"],
            file_type=result["file_type"],
            status=result["status"],
        )
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document ingestion failed: {e!s}",
        ) from e


@app.post(
    "/api/ingest/arxiv", response_model=IngestResponse, dependencies=[Depends(verify_api_key)]
)
async def ingest_arxiv(request: ArxivIngestRequest):
    """
    Fetches a scientific publication from arXiv by ID, parses, embeds and indexes.
    """
    try:
        title, pdf_bytes = await fetch_arxiv_paper(request.arxiv_id)
        file_name = f"arxiv_{request.arxiv_id}.pdf"

        result = await ingest_document(
            collection_type=request.collection_type,
            file_name=file_name,
            file_bytes=pdf_bytes,
            file_type="pdf",
            title=title,
        )
        return IngestResponse(
            source=result["source"],
            title=result["title"],
            chunks_count=result["chunks_count"],
            file_type=result["file_type"],
            status=result["status"],
        )
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to communicate with arXiv services: {e!s}",
        ) from e
    except Exception as e:
        logger.exception("arXiv download or ingestion failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"arXiv Ingestion failed: {e!s}",
        ) from e


@app.post("/api/query", response_model=QueryResponse, dependencies=[Depends(verify_api_key)])
async def query_rag(request: QueryRequest):
    """
    Executes a retrieval-augmented generation search with configurable strategies:
    - baseline: Top-K dense vector search
    - hyde: Hypothetical document query expansion
    - multi_query: Multi-query generation and Reciprocal Rank Fusion ranking
    - flare: Factual claim verification active lookahead loop
    """
    try:
        # Validate collection type
        if request.collection_type not in ["public", "papers"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="collection_type must be either 'public' or 'papers'.",
            )

        result = await answer_with_rag(
            collection_type=request.collection_type,
            query=request.query,
            strategy=request.strategy,
            limit=request.limit,
        )
        return QueryResponse(
            answer=result["answer"],
            citations=result["citations"],
            overall_confidence=result["overall_confidence"],
        )
    except Exception as e:
        logger.exception("RAG query failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Query request failed: {e!s}"
        ) from e


@app.get(
    "/api/documents", response_model=list[DocumentInfo], dependencies=[Depends(verify_api_key)]
)
async def list_documents(collection_type: str):
    """
    Lists unique source documents in a collection and their chunk counts.
    """
    if collection_type not in ["public", "papers"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="collection_type must be either 'public' or 'papers'.",
        )
    try:
        docs = db_manager.get_unique_documents(collection_type)
        return [
            DocumentInfo(
                source=doc["source"],
                title=doc["title"],
                chunk_count=doc["chunk_count"],
                file_type=doc["file_type"],
                added_at=doc["added_at"],
            )
            for doc in docs
        ]
    except Exception as e:
        logger.exception("Failed to retrieve document library")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {e!s}",
        ) from e


@app.delete("/api/documents", dependencies=[Depends(verify_api_key)])
async def delete_document(collection_type: str, source: str):
    """
    Deletes all chunks corresponding to a specific source document.
    """
    if collection_type not in ["public", "papers"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="collection_type must be 'public' or 'papers'.",
        )

    success = db_manager.delete_document(collection_type, source)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document from the database index.",
        )
    return {
        "message": f"Successfully deleted document '{source}' from {collection_type} collection."
    }
