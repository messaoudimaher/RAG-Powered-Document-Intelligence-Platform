export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
}

export interface DiagnosticsResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  public_count: number;
  papers_count: number;
  threshold: number;
  ollama_connected: boolean;
  chroma_connected: boolean;
  git_sha: string;
}

export interface ArxivIngestRequest {
  arxiv_id: string;
  collection_type: string;
}

export interface IngestResponse {
  source: string;
  title: string;
  chunks_count: number;
  file_type: string;
  status: string;
}

export interface IngestTaskResponse {
  task_id: string;
  status: string;
  source: string;
}

export interface TaskStatusResponse {
  task_id: string;
  status: string;
  result: IngestResponse | null;
  error: string | null;
}

export interface QueryRequest {
  collection_type: string;
  query: string;
  strategy: string;
  limit: number;
}

export interface SourceCitation {
  id: string;
  text: string;
  source: string;
  title: string;
  chunk_idx: number;
  total_chunks: number;
  distance: number;
  confidence: string;
  preview: string;
}

export interface QueryResponse {
  answer: string;
  citations: SourceCitation[];
  overall_confidence: string;
}

export interface DocumentInfo {
  source: string;
  title: string;
  chunk_count: number;
  file_type: string;
  added_at: string;
}
