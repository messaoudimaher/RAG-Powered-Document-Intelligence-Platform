from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import jwt

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

@pytest.fixture
def auth_headers():
    """
    Generates valid authorization headers for test_user.
    """
    token = jwt.encode(
        {"sub": "test_user", "exp": datetime.utcnow() + timedelta(hours=1)},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return {"Authorization": f"Bearer {token}"}

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
    Test diagnostics fails without JWT auth.
    """
    response = client.get("/api/diagnostics")
    assert response.status_code == 401

@patch("httpx.AsyncClient.get")
def test_diagnostics_authorized(mock_httpx_get, auth_headers):
    """
    Test diagnostics succeeds with correct JWT token.
    """
    # Mock Ollama status call
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_httpx_get.return_value = mock_resp

    with patch("app.database.db_manager.get_stats") as mock_stats:
        mock_stats.return_value = {"public_count": 10, "papers_count": 5}
        response = client.get("/api/diagnostics", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["public_count"] == 10
        assert data["papers_count"] == 5
        assert data["threshold"] == settings.relevance_threshold
        mock_stats.assert_called_once_with("test_user")

def test_ingest_file_unauthorized():
    """
    Test file ingestion blocks unauthorized requests.
    """
    response = client.post(
        "/api/ingest",
        data={"collection_type": "public"},
        files={"file": ("test.txt", b"dummy content", "text/plain")}
    )
    assert response.status_code == 401

@patch("app.main.ingest_file_task.delay")
def test_ingest_file_success(mock_ingest_task, auth_headers):
    """
    Test successful file ingestion.
    """
    mock_task = MagicMock()
    mock_task.id = "mock_task_id"
    mock_ingest_task.return_value = mock_task

    response = client.post(
        "/api/ingest",
        headers=auth_headers,
        data={"collection_type": "public"},
        files={"file": ("test.txt", b"dummy content", "text/plain")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "test.txt"
    assert data["task_id"] == "mock_task_id"
    assert data["status"] == "processing"

@patch("app.main.answer_with_rag", new_callable=AsyncMock)
def test_query_rag_success(mock_answer, auth_headers):
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
        headers=auth_headers,
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "This is a mocked RAG answer."
    assert len(data["citations"]) == 1
    assert data["overall_confidence"] == "High"
    mock_answer.assert_called_once_with(
        collection_type="public",
        query="What is the answer?",
        strategy="baseline",
        limit=3,
        rerank=False,
        username="test_user"
    )

@patch("app.database.db_manager.get_unique_documents")
def test_list_documents_success(mock_get_docs, auth_headers):
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
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["source"] == "paper1.pdf"
    assert data[0]["chunk_count"] == 12
    mock_get_docs.assert_called_once_with("papers", "test_user")

def test_list_documents_unauthorized():
    """
    Verify listing documents requires authorization.
    """
    response = client.get("/api/documents?collection_type=public")
    assert response.status_code == 401

@patch("app.database.db_manager.delete_document")
def test_delete_document_success(mock_delete, auth_headers):
    """
    Verify document deletion works and returns 200 response.
    """
    mock_delete.return_value = True

    response = client.delete(
        "/api/documents?collection_type=public&source=test_doc.txt",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "Successfully deleted" in data["message"]
    mock_delete.assert_called_once_with("public", "test_doc.txt", "test_user")

@patch("app.database.db_manager.delete_document")
def test_delete_document_failure(mock_delete, auth_headers):
    """
    Verify document deletion failure yields internal server error.
    """
    mock_delete.return_value = False

    response = client.delete(
        "/api/documents?collection_type=public&source=test_doc.txt",
        headers=auth_headers
    )
    assert response.status_code == 500

@patch("app.main.ingest_arxiv_task.delay")
def test_ingest_arxiv_success(mock_ingest_task, auth_headers):
    """
    Verify successful arXiv ingestion.
    """
    mock_task = MagicMock()
    mock_task.id = "mock_task_id"
    mock_ingest_task.return_value = mock_task

    payload = {
        "arxiv_id": "2305.16300",
        "collection_type": "papers"
    }

    response = client.post(
        "/api/ingest/arxiv",
        headers=auth_headers,
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "arxiv_2305.16300.pdf"
    assert data["task_id"] == "mock_task_id"
    assert data["status"] == "processing"
    mock_ingest_task.assert_called_once_with("papers", "2305.16300", "test_user")

def test_ingest_arxiv_unauthorized():
    """
    Verify arXiv ingestion is unauthorized without credentials.
    """
    payload = {
        "arxiv_id": "2305.16300",
        "collection_type": "papers"
    }
    response = client.post("/api/ingest/arxiv", json=payload)
    assert response.status_code == 401
