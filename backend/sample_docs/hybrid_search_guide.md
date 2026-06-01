# Hybrid Retrieval and Advanced RAG Techniques

In production-grade RAG systems, baseline vector search is often augmented by sophisticated retrieval strategies to handle complex, multi-faceted queries.

## 1. Multi-Query Expansion
Users often write ambiguous or short queries. Multi-query expansion utilizes an LLM to generate multiple variations (usually 3 distinct phrasing options) of the initial query. Each query is embedded and searched separately.

## 2. Reciprocal Rank Fusion (RRF)
To combine results from multiple searches (like different query variations), Reciprocal Rank Fusion is used. The RRF score for a document $d$ is computed as:
$$RRF(d) = \sum_{q \in Q} \frac{1}{k + r_q(d)}$$
where $r_q(d)$ is the rank of document $d$ in the results of query $q$, and $k$ is a constant (typically 60) that prevents top-ranked documents from dominating excessively. RRF combines lists without needing normalized scores.

## 3. FLARE (Forward-Looking Active Retrieval)
FLARE is an active retrieval strategy. Instead of retrieving documents once at the beginning, FLARE iteratively generates sentences. 
- For each generated sentence, it assesses confidence.
- If confidence is low, it extracts a search query from the sentence, queries the vector database for new context, and regenerates the sentence.
- This ensures that long-form generation remains continuously grounded.

## 4. HyDE (Hypothetical Document Embeddings)
HyDE addresses the query-document gap. It uses an LLM to generate a "hypothetical" answer to the user's query. This hypothetical answer, though it might contain fabricated facts, represents the ideal document layout. The hypothetical document is embedded and used to retrieve actual documents.
