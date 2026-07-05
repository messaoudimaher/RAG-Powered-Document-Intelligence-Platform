import asyncio
import logging
import os
from celery import Celery

from app.config import settings
from app.ingestion import ingest_document
from app.utils import fetch_arxiv_paper

logger = logging.getLogger("cogniflow.celery")

# Initialize Celery with Redis broker and backend
celery_app = Celery("cogniflow", broker=settings.redis_url, backend=settings.redis_url)

# Configure Celery settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="app.celery_app.ingest_file_task")
def ingest_file_task(collection_type: str, file_name: str, file_path: str, file_type: str) -> dict:
    """
    Synchronous Celery task wrapper that runs the async ingest_document pipeline.
    """
    logger.info(f"Celery worker received ingestion task for file: {file_name}")
    try:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Uploaded file not found at local temporary path: {file_path}")
        
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Run the asynchronous ingestion logic
        result = asyncio.run(ingest_document(
            collection_type=collection_type,
            file_name=file_name,
            file_bytes=file_bytes,
            file_type=file_type
        ))
        
        logger.info(f"Successfully processed ingestion for: {file_name}")
        return result
    except Exception as e:
        logger.error(f"In-worker ingestion failure for {file_name}: {e}")
        raise
    finally:
        # Clean up temporary uploaded file from shared directory
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up temporary upload file: {file_path}")
            except Exception as e:
                logger.warning(f"Could not clean up temporary file {file_path}: {e}")


@celery_app.task(name="app.celery_app.ingest_arxiv_task")
def ingest_arxiv_task(collection_type: str, arxiv_id: str) -> dict:
    """
    Synchronous Celery task wrapper that fetches and ingests an arXiv publication.
    """
    logger.info(f"Celery worker received arXiv ingestion task for ID: {arxiv_id}")
    try:
        async def run_arxiv_ingestion():
            title, pdf_bytes = await fetch_arxiv_paper(arxiv_id)
            file_name = f"arxiv_{arxiv_id}.pdf"
            result = await ingest_document(
                collection_type=collection_type,
                file_name=file_name,
                file_bytes=pdf_bytes,
                file_type="pdf",
                title=title
            )
            return result

        result = asyncio.run(run_arxiv_ingestion())
        logger.info(f"Successfully processed arXiv ingestion for ID: {arxiv_id}")
        return result
    except Exception as e:
        logger.error(f"In-worker arXiv ingestion failure for ID {arxiv_id}: {e}")
        raise
