
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    collection_type: str = Field(..., description="Target database collection: 'public' or 'papers'")
    query: str = Field(..., min_length=2, description="The search and question query string")
    strategy: str = Field(default="baseline", description="Retrieval strategy: 'baseline', 'hyde', 'multi_query', or 'flare'")
    limit: int = Field(default=5, ge=1, le=20, description="Max number of citation passages to retrieve")

class SourceCitation(BaseModel):
    id: str
    text: str
    source: str
    title: str
    chunk_idx: int
    total_chunks: int
    distance: float
    confidence: str
    preview: str

class QueryResponse(BaseModel):
    answer: str
    citations: list[SourceCitation]
    overall_confidence: str

class ArxivIngestRequest(BaseModel):
    arxiv_id: str = Field(..., description="Standard arXiv identifier (e.g. 2305.16300 or 1706.03762)")
    collection_type: str = Field(default="papers", description="Target database collection (typically 'papers')")

class IngestResponse(BaseModel):
    source: str
    title: str
    chunks_count: int
    file_type: str
    status: str

class DocumentInfo(BaseModel):
    source: str
    title: str
    chunk_count: int
    file_type: str
    added_at: str

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float

class DiagnosticsResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    public_count: int
    papers_count: int
    threshold: float
    ollama_connected: bool
    chroma_connected: bool
    git_sha: str
