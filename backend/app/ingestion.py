import io
import logging
import uuid
from datetime import datetime

from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from app.database import db_manager
from app.llm_client import llm_client

logger = logging.getLogger("docmind.ingestion")

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts text content from PDF file bytes using pypdf.
    """
    try:
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text_parts = []
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        raise ValueError(f"Failed to parse PDF document: {e}")

def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extracts text content from DOCX file bytes using python-docx.
    """
    try:
        docx_file = io.BytesIO(file_bytes)
        doc = Document(docx_file)
        text_parts = [p.text for p in doc.paragraphs if p.text]
        return "\n".join(text_parts)
    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        raise ValueError(f"Failed to parse DOCX document: {e}")

def extract_text_from_txt(file_bytes: bytes) -> str:
    """
    Extracts text content from TXT file bytes with decoding fallbacks.
    """
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return file_bytes.decode("latin-1")
        except Exception as e:
            logger.error(f"Error decoding text file: {e}")
            raise ValueError(f"Failed to decode TXT file: {e}")

def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> list[str]:
    """
    Splits text into chunks using LangChain's RecursiveCharacterTextSplitter.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    return splitter.split_text(text)

async def ingest_document(
    collection_type: str,
    file_name: str,
    file_bytes: bytes,
    file_type: str,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    title: str = None
) -> dict:
    """
    Coordinates the ingestion pipeline:
    1. Extract text from raw bytes based on file_type.
    2. Chunk the text.
    3. Generate embeddings for chunks in batches.
    4. Store chunks in ChromaDB.
    """
    logger.info(f"Starting ingestion for file: {file_name} into {collection_type} collection.")

    # 1. Text Extraction
    normalized_type = file_type.lower().strip(".")
    if normalized_type == "pdf":
        text = extract_text_from_pdf(file_bytes)
    elif normalized_type in ["docx", "doc"]:
        text = extract_text_from_docx(file_bytes)
    elif normalized_type in ["txt", "md", "markdown"]:
        text = extract_text_from_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {normalized_type}")

    if not text.strip():
        raise ValueError("The document is empty or no readable text could be extracted.")

    # 2. Chunking
    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    total_chunks = len(chunks)
    logger.info(f"Split {file_name} into {total_chunks} chunks.")

    if total_chunks == 0:
        raise ValueError("No text chunks generated. Check chunking parameters.")

    # 3. Embedding Generation (Batching to prevent request overload)
    embeddings = []
    batch_size = 16
    for i in range(0, total_chunks, batch_size):
        batch_chunks = chunks[i:i+batch_size]
        try:
            batch_embeddings = await llm_client.get_embeddings(batch_chunks)
            embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error(f"Error generating embeddings for batch {i//batch_size}: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}")

    # 4. Save to ChromaDB
    doc_title = title or file_name
    added_at_str = datetime.utcnow().isoformat()

    ids = [f"{uuid.uuid4()}" for _ in range(total_chunks)]
    metadatas = [
        {
            "source": file_name,
            "title": doc_title,
            "chunk_idx": idx,
            "total_chunks": total_chunks,
            "file_type": normalized_type,
            "added_at": added_at_str,
            # Preview is first 100 characters of the chunk for rapid sidebar index view
            "preview": chunk[:150].replace("\n", " ") + ("..." if len(chunk) > 150 else "")
        }
        for idx, chunk in enumerate(chunks)
    ]

    db_manager.add_chunks(
        collection_type=collection_type,
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=chunks
    )

    return {
        "source": file_name,
        "title": doc_title,
        "chunks_count": total_chunks,
        "file_type": normalized_type,
        "status": "success"
    }
