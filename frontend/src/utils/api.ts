const LOCAL_STORAGE_BASE_URL_KEY = 'docmind_api_base_url';
const LOCAL_STORAGE_API_KEY_KEY = 'docmind_api_key';
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
