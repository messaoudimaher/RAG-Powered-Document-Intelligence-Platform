from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.retrieval import (
    calculate_confidence,
    format_citations,
    retrieve_baseline,
    retrieve_hyde,
    retrieve_multi_query_rrf,
    retrieve_flare,
)


def test_calculate_confidence():
    """
    Test mapping of cosine distance metrics to labels.
    """
    assert calculate_confidence(0.2) == "High"
    assert calculate_confidence(0.4) == "High"
    assert calculate_confidence(0.6) == "Medium"
    assert calculate_confidence(0.7) == "Medium"
    assert calculate_confidence(0.9) == "Low"

def test_format_citations_empty():
    """
    Test format_citations handles empty or invalid database outputs.
    """
    assert format_citations(None) == []
    assert format_citations({}) == []
    assert format_citations({"ids": [[]]}) == []

def test_format_citations_threshold_filtering():
    """
    Test that format_citations filters results according to relevance threshold
    and fallback retrieval settings.
    """
    raw_results = {
        "ids": [["chunk_1", "chunk_2"]],
        "documents": [["Doc content 1", "Doc content 2"]],
        "metadatas": [[{"source": "doc1.txt", "title": "Doc 1"}, {"source": "doc2.txt", "title": "Doc 2"}]],
        "distances": [[0.3, 0.9]]  # threshold is 0.75 by default
    }

    # Case A: Fallback enabled (should return both chunks, chunk_2 with Low confidence)
    settings.enable_fallback_retrieval = True
    citations = format_citations(raw_results)
    assert len(citations) == 2
    assert citations[0]["id"] == "chunk_1"
    assert citations[0]["confidence"] == "High"
    assert citations[1]["id"] == "chunk_2"
    assert citations[1]["confidence"] == "Low"

    # Case B: Fallback disabled (should filter out chunk_2 with distance 0.9)
    settings.enable_fallback_retrieval = False
    citations = format_citations(raw_results)
    assert len(citations) == 1
    assert citations[0]["id"] == "chunk_1"

@pytest.mark.asyncio
@patch("app.llm_client.llm_client.get_embeddings", new_callable=AsyncMock)
@patch("app.database.db_manager.query")
async def test_retrieve_baseline(mock_db_query, mock_embeddings):
    """
    Verify baseline vector search orchestration.
    """
    mock_embeddings.return_value = [[0.1, 0.2, 0.3]]
    mock_db_query.return_value = {
        "ids": [["c1"]],
        "documents": [["content 1"]],
        "metadatas": [[{"source": "doc.txt", "title": "Doc"}]],
        "distances": [[0.2]]
    }

    res = await retrieve_baseline("public", "test query", limit=2)
    assert len(res) == 1
    assert res[0]["id"] == "c1"
    assert res[0]["distance"] == 0.2
    mock_embeddings.assert_called_once_with(["test query"])

@pytest.mark.asyncio
@patch("app.llm_client.llm_client.generate_completion", new_callable=AsyncMock)
@patch("app.llm_client.llm_client.get_embeddings", new_callable=AsyncMock)
@patch("app.database.db_manager.query")
async def test_retrieve_hyde(mock_db_query, mock_embeddings, mock_llm):
    """
    Verify HyDE strategy: generates hypothetical answer, embeds it, queries DB.
    """
    mock_llm.return_value = "This is a hypothetical answer."
    mock_embeddings.return_value = [[0.1, 0.1, 0.1]]
    mock_db_query.return_value = {
        "ids": [["hyde_chunk"]],
        "documents": [["Real document content"]],
        "metadatas": [[{"source": "real.txt", "title": "Real"}]],
        "distances": [[0.35]]
    }

    res = await retrieve_hyde("public", "query text", limit=1)
    assert len(res) == 1
    assert res[0]["id"] == "hyde_chunk"
    mock_llm.assert_called_once()
    mock_embeddings.assert_called_once_with(["This is a hypothetical answer."])

@pytest.mark.asyncio
@patch("app.llm_client.llm_client.generate_completion", new_callable=AsyncMock)
@patch("app.llm_client.llm_client.get_embeddings", new_callable=AsyncMock)
@patch("app.database.db_manager.query")
async def test_retrieve_multi_query_rrf(mock_db_query, mock_embeddings, mock_llm):
    """
    Verify Multi-Query RRF logic: generates alternative queries, merges results with RRF.
    """
    # 3 alternatives
    mock_llm.return_value = "query alternate 1\nquery alternate 2\nquery alternate 3"
    # Embeddings for 4 queries (original + 3 variations)
    mock_embeddings.return_value = [[1], [2], [3], [4]]

    # Query 1 result
    def query_mock(collection_type, query_embeddings, n_results, where=None):
        emb = query_embeddings[0]
        if emb == [1]:  # original query
            return {"ids": [["c1", "c2"]], "documents": [["doc 1", "doc 2"]], "metadatas": [[{"source": "s1"}, {"source": "s2"}]], "distances": [[0.1, 0.4]]}
        elif emb == [2]:  # alternate 1
            return {"ids": [["c2", "c3"]], "documents": [["doc 2", "doc 3"]], "metadatas": [[{"source": "s2"}, {"source": "s3"}]], "distances": [[0.3, 0.5]]}
        else:
            return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    mock_db_query.side_effect = query_mock
    settings.enable_fallback_retrieval = True

    # Limit = 2, RRF should rank 'c2' first (appears at rank 1 in Q1, rank 0 in Q2)
    res = await retrieve_multi_query_rrf("public", "main query", limit=2)
    assert len(res) == 2
    assert res[0]["distance"] == 0.3


@pytest.mark.asyncio
@patch("app.retrieval.retrieve_baseline", new_callable=AsyncMock)
@patch("app.llm_client.llm_client.generate_completion", new_callable=AsyncMock)
async def test_retrieve_flare_grounded(mock_generate_completion, mock_retrieve_baseline):
    """
    Verify FLARE logic when draft answer is already grounded and needs no secondary retrieval.
    """
    mock_retrieve_baseline.return_value = [
        {
            "id": "c1",
            "text": "Initial context sentence.",
            "source": "doc1.txt",
            "title": "Doc 1",
            "chunk_idx": 0,
            "total_chunks": 1,
            "distance": 0.2,
            "confidence": "High",
            "preview": "Initial context..."
        }
    ]
    mock_generate_completion.side_effect = [
        "This draft answer is fully supported by Initial context sentence.",
        "GROUNDED"
    ]

    res = await retrieve_flare("public", "test query", limit=1)
    assert res["answer"] == "This draft answer is fully supported by Initial context sentence."
    assert len(res["citations"]) == 1
    assert res["citations"][0]["id"] == "c1"
    mock_retrieve_baseline.assert_called_once_with("public", "test query", limit=1)


@pytest.mark.asyncio
@patch("app.retrieval.retrieve_baseline", new_callable=AsyncMock)
@patch("app.llm_client.llm_client.generate_completion", new_callable=AsyncMock)
async def test_retrieve_flare_with_secondary_retrieval(mock_generate_completion, mock_retrieve_baseline):
    """
    Verify FLARE logic when draft answer has retrieval tags and needs secondary retrieval.
    """
    mock_retrieve_baseline.side_effect = [
        [
            {
                "id": "c1",
                "text": "Initial info.",
                "source": "doc1.txt",
                "title": "Doc 1",
                "chunk_idx": 0,
                "total_chunks": 1,
                "distance": 0.3,
                "confidence": "High",
                "preview": "Initial info..."
            }
        ],
        [
            {
                "id": "c2",
                "text": "Secondary info on RRF.",
                "source": "doc2.txt",
                "title": "Doc 2",
                "chunk_idx": 0,
                "total_chunks": 1,
                "distance": 0.25,
                "confidence": "High",
                "preview": "Secondary info..."
            }
        ]
    ]

    mock_generate_completion.side_effect = [
        "Draft answer needing [retrieve: RRF] details.",
        "Final synthesized answer with RRF details."
    ]

    res = await retrieve_flare("public", "test query", limit=2)
    assert res["answer"] == "Final synthesized answer with RRF details."
    assert len(res["citations"]) == 2
    assert any(c["id"] == "c2" for c in res["citations"])
    mock_retrieve_baseline.assert_any_call("public", "RRF", limit=3)

