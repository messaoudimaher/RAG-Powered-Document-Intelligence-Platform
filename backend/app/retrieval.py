import logging
import re

from app.config import settings
from app.database import db_manager
from app.llm_client import llm_client

logger = logging.getLogger("cogniflow.retrieval")


_reranker_model = None


def get_reranker():
    global _reranker_model
    if _reranker_model is None:
        from sentence_transformers import CrossEncoder

        logger.info(f"Loading Cross-Encoder reranker model '{settings.reranker_model}'...")
        _reranker_model = CrossEncoder(settings.reranker_model)
    return _reranker_model


def calculate_confidence(distance: float) -> str:
    """
    Maps cosine distance to a confidence label:
    - Cosine distance ranges from 0 to 2 (0: identical, 1: orthogonal, 2: opposite)
    - Smaller distance is better.
    """
    if distance <= 0.45:
        return "High"
    elif distance <= settings.relevance_threshold:
        return "Medium"
    else:
        return "Low"


def format_citations(results: dict) -> list[dict]:
    """
    Formats raw ChromaDB query results into a structured list of SourceCitations.
    Filters by threshold if ENABLE_FALLBACK_RETRIEVAL is false.
    """
    citations = []
    if not results or not results.get("ids") or not results["ids"][0]:
        return []

    ids = results["ids"][0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for idx in range(len(ids)):
        dist = distances[idx]

        # Check threshold if fallback is disabled
        if not settings.enable_fallback_retrieval and dist > settings.relevance_threshold:
            continue

        meta = metadatas[idx] or {}
        citations.append(
            {
                "id": ids[idx],
                "text": documents[idx],
                "source": meta.get("source", "unknown"),
                "title": meta.get("title", "Untitled"),
                "chunk_idx": meta.get("chunk_idx", 0),
                "total_chunks": meta.get("total_chunks", 1),
                "distance": round(dist, 4),
                "confidence": calculate_confidence(dist),
                "preview": meta.get("preview", documents[idx][:150]),
            }
        )

    # Sort citations by distance ascending (closest first)
    citations.sort(key=lambda x: x["distance"])
    return citations


async def retrieve_baseline(collection_type: str, query: str, limit: int = 5, username: str = None) -> list[dict]:
    """
    Performs standard baseline vector search.
    """
    query_embeddings = await llm_client.get_embeddings([query])
    if not query_embeddings:
        return []

    raw_results = db_manager.query(
        collection_type=collection_type, query_embeddings=[query_embeddings[0]], n_results=limit, username=username
    )
    return format_citations(raw_results)


async def retrieve_hyde(collection_type: str, query: str, limit: int = 5, username: str = None) -> list[dict]:
    """
    Performs HyDE search: LLM generates a hypothetical answer -> Embedded -> Vector search.
    """
    logger.info(f"Executing HyDE retrieval for query: '{query}' (user: {username})")

    # Step 1: Generate hypothetical document
    system_prompt = (
        "You are an expert researcher. Write a paragraph that directly and factually "
        "answers the user's query. Do not write introductory chatter. Write the ideal "
        "document passage that contains the answer."
    )
    hypothetical_doc = await llm_client.generate_completion(
        prompt=f"Generate hypothetical answer for: {query}",
        system_prompt=system_prompt,
        temperature=0.4,
    )
    logger.info(f"Generated hypothetical answer: {hypothetical_doc[:100]}...")

    # Step 2: Embed hypothetical answer
    embeddings = await llm_client.get_embeddings([hypothetical_doc])
    if not embeddings:
        return await retrieve_baseline(collection_type, query, limit, username=username)

    # Step 3: Vector search
    raw_results = db_manager.query(
        collection_type=collection_type, query_embeddings=[embeddings[0]], n_results=limit, username=username
    )
    return format_citations(raw_results)


async def retrieve_multi_query_rrf(collection_type: str, query: str, limit: int = 5, username: str = None) -> list[dict]:
    """
    Multi-query with Reciprocal Rank Fusion:
    1. Generate 3 query variations.
    2. Retrieve top (limit * 2) matches for all 4 queries (original + 3 variations).
    3. Perform Reciprocal Rank Fusion (RRF) to merge, rank, and take top N.
    """
    logger.info(f"Executing Multi-Query RRF retrieval for: '{query}' (user: {username})")

    # Step 1: Generate query variations
    system_prompt = (
        "You are a search engine optimization expert. Generate exactly 3 alternative search queries "
        "for the user's query to retrieve relevant documents. Return ONLY the 3 queries, "
        "one per line, with no labels, numbers, or introductory text."
    )
    variations_text = await llm_client.generate_completion(
        prompt=f"Queries for: {query}", system_prompt=system_prompt, temperature=0.5
    )

    queries = [query]
    for line in variations_text.strip().split("\n"):
        line_clean = re.sub(r"^\d+\.\s*", "", line).strip("\"' ")
        if line_clean:
            queries.append(line_clean)

    logger.info(f"Expanded queries: {queries}")

    # Step 2: Fetch query embeddings and search
    embeddings = await llm_client.get_embeddings(queries)
    if not embeddings:
        return await retrieve_baseline(collection_type, query, limit, username=username)

    # Retrieve slightly more than limit for each to allow rank fusion depth
    search_depth = max(limit * 2, 10)

    # Fetch results for each query in parallel
    results_by_query = []
    for emb in embeddings:
        raw_res = db_manager.query(
            collection_type=collection_type, query_embeddings=[emb], n_results=search_depth, username=username
        )
        results_by_query.append(raw_res)

    # Step 3: Reciprocal Rank Fusion
    # rrf_score = sum(1 / (60 + rank))
    rrf_constant = 60
    chunk_scores = {}  # chunk_id -> rrf_score
    chunk_details = {}  # chunk_id -> {text, source, title, chunk_idx, total_chunks, distance_sum, count, preview}

    for query_res in results_by_query:
        if not query_res or not query_res.get("ids") or not query_res["ids"][0]:
            continue

        ids = query_res["ids"][0]
        documents = query_res["documents"][0]
        metadatas = query_res["metadatas"][0]
        distances = query_res["distances"][0]

        for rank, cid in enumerate(ids):
            # Rank starts at 0, so rank+1
            score = 1.0 / (rrf_constant + (rank + 1))
            chunk_scores[cid] = chunk_scores.get(cid, 0.0) + score

            meta = metadatas[rank] or {}
            # Track metadata details and keep a rolling average of distance
            if cid not in chunk_details:
                chunk_details[cid] = {
                    "id": cid,
                    "text": documents[rank],
                    "source": meta.get("source", "unknown"),
                    "title": meta.get("title", "Untitled"),
                    "chunk_idx": meta.get("chunk_idx", 0),
                    "total_chunks": meta.get("total_chunks", 1),
                    "distance_sum": distances[rank],
                    "distance_min": distances[rank],
                    "count": 1,
                    "preview": meta.get("preview", documents[rank][:150]),
                }
            else:
                chunk_details[cid]["distance_sum"] += distances[rank]
                chunk_details[cid]["distance_min"] = min(
                    chunk_details[cid]["distance_min"], distances[rank]
                )
                chunk_details[cid]["count"] += 1

    # Step 4: Sort by RRF score descending and take top 'limit'
    sorted_chunk_ids = sorted(chunk_scores.keys(), key=lambda cid: chunk_scores[cid], reverse=True)
    top_chunk_ids = sorted_chunk_ids[:limit]

    # Map back to formatted citation objects
    citations = []
    for cid in top_chunk_ids:
        details = chunk_details[cid]
        # We use the minimum distance achieved across queries as the relevance distance
        best_dist = details["distance_min"]

        # Filter if fallback is disabled
        if not settings.enable_fallback_retrieval and best_dist > settings.relevance_threshold:
            continue

        citations.append(
            {
                "id": details["id"],
                "text": details["text"],
                "source": details["source"],
                "title": details["title"],
                "chunk_idx": details["chunk_idx"],
                "total_chunks": details["total_chunks"],
                "distance": round(best_dist, 4),
                "confidence": calculate_confidence(best_dist),
                "preview": details["preview"],
            }
        )

    return citations


async def retrieve_flare(collection_type: str, query: str, limit: int = 5, username: str = None) -> dict:
    """
    Implements a local-friendly active retrieval FLARE loop.
    1. Initial retrieval based on user query to get starting context.
    2. Generate initial answer draft.
    3. Evaluate answer for information gaps or assertions.
    4. If the generator makes factual claims unsupported by initial context,
       extract search queries for those gaps, fetch new context, and regenerate.
    5. Returns both the final grounded answer and the aggregated SourceCitations.
    """
    logger.info(f"Executing FLARE active retrieval for: '{query}' (user: {username})")

    # Step 1: Initial Retrieval
    initial_citations = await retrieve_baseline(collection_type, query, limit=limit, username=username)
    context_text = "\n\n".join(
        [
            f"Source: {c['source']} (Confidence: {c['confidence']})\n{c['text']}"
            for c in initial_citations
        ]
    )

    # Step 2: Generate draft answer
    system_prompt = (
        "You are an intelligence analyst. Answer the user question based strictly on the provided context. "
        "If the context does not contain enough details, write a draft and mark gaps in brackets like [retrieve: specific topic]."
    )
    draft_prompt = f"Context:\n{context_text}\n\nQuestion:\n{query}"
    draft = await llm_client.generate_completion(
        prompt=draft_prompt, system_prompt=system_prompt, temperature=0.3
    )
    logger.info(f"FLARE Initial Draft:\n{draft}")

    # Step 3: Check for information gaps / retrieve tags
    # Detect bracketed retrieve tags or determine if we need to actively search for anything in the draft
    # Let's extract any [retrieve: ...] tags or ask the LLM to inspect the draft for missing facts.
    citations_dict = {c["id"]: c for c in initial_citations}

    retrieve_queries = re.findall(r"\[retrieve:\s*([^\]]+)\]", draft)

    # If no explicit brackets, let's double check if there are sentences needing support
    if not retrieve_queries:
        # Factual query verification prompt
        verification_prompt = (
            f"Given the user query: '{query}' and this draft answer:\n'{draft}'\n"
            "Identify up to 2 specific statements or facts in the draft that require more precise citation or context. "
            "Return each statement as a search query on a new line. If the draft is fully grounded, write 'GROUNDED'."
        )
        ver_text = await llm_client.generate_completion(prompt=verification_prompt, temperature=0.2)
        if "GROUNDED" not in ver_text.upper():
            for line in ver_text.strip().split("\n"):
                clean_line = re.sub(r"^\d+\.\s*", "", line).strip("\"' ")
                if clean_line and len(clean_line) > 5:
                    retrieve_queries.append(clean_line)

    logger.info(f"FLARE detected search gaps: {retrieve_queries}")

    # Step 4: Perform secondary retrieval on gaps and merge context
    if retrieve_queries:
        all_new_citations = []
        for r_query in retrieve_queries[:2]:  # Limit to 2 sub-queries to stay fast
            new_cites = await retrieve_baseline(collection_type, r_query, limit=3, username=username)
            all_new_citations.extend(new_cites)

        # Merge citations
        for c in all_new_citations:
            citations_dict[c["id"]] = c

        # Re-synthesize context
        merged_citations = list(citations_dict.values())
        merged_citations.sort(key=lambda x: x["distance"])

        context_text = "\n\n".join(
            [f"Source: {c['source']}\n{c['text']}" for c in merged_citations[:limit]]
        )

        # Final answer synthesis
        final_system_prompt = (
            "You are a grounded Q&A system. Synthesize a comprehensive final answer to the user question "
            "based ONLY on the provided verified sources. Make sure to reference facts accurately. "
            "Do not include any [retrieve] bracket tags in your final output."
        )
        final_prompt = f"Verified Context:\n{context_text}\n\nQuestion:\n{query}"
        final_answer = await llm_client.generate_completion(
            prompt=final_prompt, system_prompt=final_system_prompt, temperature=0.2
        )

        return {"answer": final_answer, "citations": merged_citations[:limit]}
    else:
        # Draft is already grounded, just clean up any brackets if present
        clean_answer = re.sub(r"\[retrieve:\s*([^\]]+)\]", "", draft).strip()
        return {"answer": clean_answer, "citations": initial_citations}


async def answer_with_rag(
    collection_type: str, query: str, strategy: str = "baseline", limit: int = 5, rerank: bool = False, username: str = None
) -> dict:
    """
    Main entry point for executing RAG queries.
    Retrieves citations, queries the LLM, and formats the response.
    """
    strategy_clean = strategy.lower().strip()

    if strategy_clean == "flare":
        # FLARE handles generation and retrieval iteratively in the function
        response_data = await retrieve_flare(collection_type, query, limit, username=username)
    else:
        # For standard strategies, determine retrieval limit (retrieve more if re-ranking is enabled)
        fetch_limit = max(2 * limit, 10) if rerank else limit

        # 1. Fetch relevant passages based on strategy
        if strategy_clean == "hyde":
            citations = await retrieve_hyde(collection_type, query, fetch_limit, username=username)
        elif strategy_clean == "multi_query":
            citations = await retrieve_multi_query_rrf(collection_type, query, fetch_limit, username=username)
        else:  # baseline
            citations = await retrieve_baseline(collection_type, query, fetch_limit, username=username)

        # 2. Perform Cross-Encoder re-ranking if requested
        if rerank and citations:
            try:
                reranker = get_reranker()
                pairs = [(query, c["text"]) for c in citations]
                scores = reranker.predict(pairs).tolist()
                for c, score in zip(citations, scores):
                    c["rerank_score"] = score
                
                # Sort by rerank score descending
                citations.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
                
                # Slice back to original user-specified limit
                citations = citations[:limit]
            except Exception as e:
                logger.error(f"Error during Cross-Encoder re-ranking: {e}. Falling back to default order.")
                citations = citations[:limit]

        # 3. Generate answer using top re-ranked citations
        context = "\n\n".join([f"Source: {c['source']}\n{c['text']}" for c in citations])
        system_prompt = "You are a highly analytical assistant. Answer the user question based strictly on the provided context."
        answer = await llm_client.generate_completion(
            prompt=f"Context:\n{context}\n\nQuestion:\n{query}",
            system_prompt=system_prompt,
            temperature=0.2,
        )
        response_data = {"answer": answer, "citations": citations}

    # Evaluate overall response confidence flag
    if response_data["citations"]:
        avg_distance = sum(c["distance"] for c in response_data["citations"]) / len(
            response_data["citations"]
        )
        response_data["overall_confidence"] = calculate_confidence(avg_distance)
    else:
        response_data["overall_confidence"] = "Low"

    return response_data
