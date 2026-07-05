from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def configure_test_env():
    """
    Ensure settings are configured for a test environment.
    """
    settings.api_key = "test_secret_key"
    settings.seed_sample_docs = False
    yield

def test_root_redirect():
    """
    Test redirect to docs.
    """
    response = client.get("/", follow_redirects=False)
    assert response.status_code in [302, 307]
    assert "/docs" in response.headers["location"]

def test_health_check():
    """
    Test public health check endpoint.
    """
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert "version" in data

@patch("app.database.db_manager.get_stats")
@patch("httpx.AsyncClient.get")
def test_readiness_healthy(mock_httpx_get, mock_get_stats):
    """
    Test readiness check when both Chroma and Ollama are healthy.
    """
    mock_get_stats.return_value = {"public_count": 5, "papers_count": 2}

    # Mock Ollama HTTP check
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_httpx_get.return_value = mock_response

    response = client.get("/api/readiness")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

@patch("app.database.db_manager.get_stats")
@patch("httpx.AsyncClient.get")
def test_readiness_degraded(mock_httpx_get, mock_get_stats):
    """
    Test readiness check when ChromaDB or Ollama is down.
    """
    mock_get_stats.side_effect = Exception("ChromaDB connection failed")

    response = client.get("/api/readiness")
    assert response.status_code == 503
    assert "Service Unavailable" in response.json()["detail"]

def test_diagnostics_unauthorized():
    """
    Test diagnostics fails without X-API-Key header.
    """
    response = client.get("/api/diagnostics")
    assert response.status_code == 403

@patch("httpx.AsyncClient.get")
def test_diagnostics_authorized(mock_httpx_get):
    """
    Test diagnostics succeeds with correct X-API-Key.
    """
    # Mock Ollama status call
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_httpx_get.return_value = mock_resp

    with patch("app.database.db_manager.get_stats") as mock_stats:
        mock_stats.return_value = {"public_count": 10, "papers_count": 5}
        response = client.get("/api/diagnostics", headers={"X-API-Key": "test_secret_key"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["public_count"] == 10
        assert data["papers_count"] == 5
        assert data["threshold"] == settings.relevance_threshold

@patch("app.main.ingest_document")
def test_ingest_file_unauthorized(mock_ingest):
    """
    Test file ingestion blocks unauthorized requests.
    """
    response = client.post(
        "/api/ingest",
        data={"collection_type": "public"},
        files={"file": ("test.txt", b"dummy content", "text/plain")}
    )
    assert response.status_code == 403

@patch("app.main.ingest_document", new_callable=AsyncMock)
def test_ingest_file_success(mock_ingest):
    """
    Test successful file ingestion.
    """
    mock_ingest.return_value = {
        "source": "test.txt",
        "title": "test.txt",
        "chunks_count": 3,
        "file_type": "txt",
        "status": "success"
    }

    response = client.post(
        "/api/ingest",
        headers={"X-API-Key": "test_secret_key"},
        data={"collection_type": "public"},
        files={"file": ("test.txt", b"dummy content", "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "test.txt"
    assert data["chunks_count"] == 3
    assert data["status"] == "success"

@patch("app.main.answer_with_rag", new_callable=AsyncMock)
def test_query_rag_success(mock_answer):
    """
    Test successful RAG query endpoint.
    """
    mock_answer.return_value = {
        "answer": "This is a mocked RAG answer.",
        "citations": [
            {
                "id": "chunk_1",
                "text": "Chunk contents",
                "source": "test_doc.txt",
                "title": "Test Title",
                "chunk_idx": 0,
                "total_chunks": 1,
                "distance": 0.25,
                "confidence": "High",
                "preview": "Chunk..."
            }
        ],
        "overall_confidence": "High"
    }

    payload = {
        "collection_type": "public",
        "query": "What is the answer?",
        "strategy": "baseline",
        "limit": 3
    }

    response = client.post(
        "/api/query",
        headers={"X-API-Key": "test_secret_key"},
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "This is a mocked RAG answer."
    assert len(data["citations"]) == 1
    assert data["overall_confidence"] == "High"


@patch("app.database.db_manager.get_unique_documents")
def test_list_documents_success(mock_get_docs):
    """
    Test successful retrieval of unique documents in a collection.
    """
    mock_get_docs.return_value = [
        {
            "source": "paper1.pdf",
            "title": "Paper 1 Title",
            "chunk_count": 12,
            "file_type": "pdf",
            "added_at": "2026-07-05T12:00:00Z"
        }
    ]

    response = client.get(
        "/api/documents?collection_type=papers",
        headers={"X-API-Key": "test_secret_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["source"] == "paper1.pdf"
    assert data[0]["chunk_count"] == 12
    mock_get_docs.assert_called_once_with("papers")


def test_list_documents_unauthorized():
    """
    Verify listing documents requires authorization.
    """
    response = client.get("/api/documents?collection_type=public")
    assert response.status_code == 403


@patch("app.database.db_manager.delete_document")
def test_delete_document_success(mock_delete):
    """
    Verify document deletion works and returns 200 response.
    """
    mock_delete.return_value = True

    response = client.delete(
        "/api/documents?collection_type=public&source=test_doc.txt",
        headers={"X-API-Key": "test_secret_key"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "Successfully deleted" in data["message"]
    mock_delete.assert_called_once_with("public", "test_doc.txt")


@patch("app.database.db_manager.delete_document")
def test_delete_document_failure(mock_delete):
    """
    Verify document deletion failure yields internal server error.
    """
    mock_delete.return_value = False

    response = client.delete(
        "/api/documents?collection_type=public&source=test_doc.txt",
        headers={"X-API-Key": "test_secret_key"}
    )
    assert response.status_code == 500



@patch("app.main.fetch_arxiv_paper", new_callable=AsyncMock)
@patch("app.main.ingest_document", new_callable=AsyncMock)
def test_ingest_arxiv_success(mock_ingest, mock_fetch):
    """
    Verify successful arXiv ingestion.
    """
    mock_fetch.return_value = ("Test Arxiv Title", b"fake pdf bytes")
    mock_ingest.return_value = {
        "source": "arxiv_2305.16300.pdf",
        "title": "Test Arxiv Title",
        "chunks_count": 8,
        "file_type": "pdf",
        "status": "success"
    }

    payload = {
        "arxiv_id": "2305.16300",
        "collection_type": "papers"
    }

    response = client.post(
        "/api/ingest/arxiv",
        headers={"X-API-Key": "test_secret_key"},
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "arxiv_2305.16300.pdf"
    assert data["chunks_count"] == 8
    assert data["status"] == "success"
    mock_fetch.assert_called_once_with("2305.16300")
    mock_ingest.assert_called_once()


def test_ingest_arxiv_unauthorized():
    """
    Verify arXiv ingestion is unauthorized without credentials.
    """
    payload = {
        "arxiv_id": "2305.16300",
        "collection_type": "papers"
    }
    response = client.post("/api/ingest/arxiv", json=payload)
    assert response.status_code == 403
