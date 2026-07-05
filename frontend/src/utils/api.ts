import {
  DiagnosticsResponse,
  DocumentInfo,
  IngestResponse,
  IngestTaskResponse,
  TaskStatusResponse,
  QueryResponse,
} from '../types';

const LOCAL_STORAGE_BASE_URL_KEY = 'cogniflow_api_base_url';
const LOCAL_STORAGE_API_KEY_KEY = 'cogniflow_api_key';
const DEFAULT_API_BASE_URL = 'http://localhost:8000';

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    return window.localStorage.getItem(LOCAL_STORAGE_BASE_URL_KEY) || DEFAULT_API_BASE_URL;
  }
  return DEFAULT_API_BASE_URL;
}

export function setApiBaseUrl(url: string): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LOCAL_STORAGE_BASE_URL_KEY, url);
  }
}

export function getApiKey(): string {
  if (typeof window !== 'undefined') {
    return window.localStorage.getItem(LOCAL_STORAGE_API_KEY_KEY) || '';
  }
  return '';
}

export function setApiKey(key: string): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(LOCAL_STORAGE_API_KEY_KEY, key);
  }
}

// Helper to make fetch requests with auth headers and error handling
async function fetchJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, '');
  const apiKey = getApiKey();
  
  const headers = new Headers(options.headers || {});
  if (apiKey) {
    headers.set('X-API-Key', apiKey);
  }
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMessage = `HTTP error ${response.status}`;
    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorMessage;
    } catch {
      // ignore parsing error, default message stands
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}

export const api = {
  async getDiagnostics(): Promise<DiagnosticsResponse> {
    return fetchJson<DiagnosticsResponse>('/api/diagnostics');
  },

  async queryRag(payload: {
    collection_type: 'public' | 'papers';
    query: string;
    strategy: 'baseline' | 'hyde' | 'multi_query' | 'flare';
    limit: number;
  }): Promise<QueryResponse> {
    return fetchJson<QueryResponse>('/api/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  async uploadFile(collection_type: 'public' | 'papers', file: File): Promise<IngestTaskResponse> {
    const formData = new FormData();
    formData.append('collection_type', collection_type);
    formData.append('file', file);

    return fetchJson<IngestTaskResponse>('/api/ingest', {
      method: 'POST',
      body: formData,
    });
  },

  async ingestArxiv(collection_type: 'public' | 'papers', arxivId: string): Promise<IngestTaskResponse> {
    return fetchJson<IngestTaskResponse>('/api/ingest/arxiv', {
      method: 'POST',
      body: JSON.stringify({
        arxiv_id: arxivId,
        collection_type,
      }),
    });
  },

  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    return fetchJson<TaskStatusResponse>(`/api/ingest/status/${taskId}`);
  },

  async listDocuments(collection_type: 'public' | 'papers'): Promise<DocumentInfo[]> {
    return fetchJson<DocumentInfo[]>(`/api/documents?collection_type=${collection_type}`);
  },

  async deleteDocument(collection_type: 'public' | 'papers', source: string): Promise<void> {
    await fetchJson<any>(`/api/documents?collection_type=${collection_type}&source=${encodeURIComponent(source)}`, {
      method: 'DELETE',
    });
  },
};
