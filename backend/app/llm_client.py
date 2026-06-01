import asyncio
import logging
import httpx
from app.config import settings

logger = logging.getLogger("docmind.llm")

class LLMClient:
    """
    Unified client for handling embeddings (via local Ollama)
    and text completions (via Gemini API or local Ollama).
    """
    def __init__(self):
        # We use a persistent async HTTPX client to reuse TCP connections.
        # We increase the timeouts for local LLMs which can be slow.
        self.timeout = httpx.Timeout(60.0, connect=5.0)

    async def _post_with_retry(self, client: httpx.AsyncClient, url: str, json_data: dict, headers: dict = None, max_retries: int = 3) -> httpx.Response:
        """
        Helper method to perform POST requests with exponential backoff.
        """
        delay = 1.0
        for attempt in range(max_retries):
            try:
                response = await client.post(url, json=json_data, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                return response
            except (httpx.HTTPStatusError, httpx.RequestError) as e:
                logger.warning(f"HTTP request failed on attempt {attempt + 1}/{max_retries} for URL {url}: {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
        raise httpx.RequestError("Max retries exceeded")

    async def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Fetches embeddings for a list of strings from local Ollama.
        First tries the newer batch /api/embed endpoint, and falls back
        to parallel requests to /api/embeddings if needed.
        """
        if not texts:
            return []

        async with httpx.AsyncClient() as client:
            # 1. Try batch embed endpoint first (/api/embed)
            embed_url = f"{settings.ollama_base_url.rstrip('/')}/api/embed"
            try:
                payload = {
                    "model": settings.ollama_embed_model,
                    "input": texts
                }
                response = await self._post_with_retry(client, embed_url, payload)
                data = response.json()
                if "embeddings" in data:
                    return data["embeddings"]
            except Exception as e:
                logger.warning(f"Batch embedding endpoint (/api/embed) failed, falling back to sequential: {e}")

            # 2. Fallback to older /api/embeddings in parallel
            embeddings_url = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"
            
            async def embed_single(text: str) -> list[float]:
                payload = {
                    "model": settings.ollama_embed_model,
                    "prompt": text
                }
                resp = await self._post_with_retry(client, embeddings_url, payload)
                return resp.json()["embedding"]

            # Run concurrently
            tasks = [embed_single(text) for text in texts]
            results = await asyncio.gather(*tasks)
            return list(results)

    async def generate_completion(self, prompt: str, system_prompt: str = None, temperature: float = 0.2) -> str:
        """
        Generates completions. Uses Gemini API (gemini-2.5-flash) if GEMINI_API_KEY
        is provided, otherwise falls back to local Ollama (settings.ollama_llm_model).
        """
        # System instructions formatting helper
        formatted_prompt = prompt
        if system_prompt:
            formatted_prompt = f"{system_prompt}\n\nUser Question:\n{prompt}"

        # Case A: Gemini API is configured
        if settings.gemini_api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": formatted_prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature
                }
            }
            headers = {"Content-Type": "application/json"}
            
            try:
                async with httpx.AsyncClient() as client:
                    response = await self._post_with_retry(client, url, payload, headers=headers)
                    data = response.json()
                    # Parse candidates
                    text_out = data["candidates"][0]["content"]["parts"][0]["text"]
                    return text_out.strip()
            except Exception as e:
                logger.error(f"Gemini API completion failed: {e}. Falling back to Ollama.")
                # Fallback to Ollama if Gemini API fails

        # Case B: Local Ollama
        ollama_url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": settings.ollama_llm_model,
            "messages": messages,
            "options": {
                "temperature": temperature
            },
            "stream": False
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await self._post_with_retry(client, ollama_url, payload)
                data = response.json()
                return data["message"]["content"].strip()
            except Exception as e:
                logger.error(f"Ollama completion failed: {e}")
                raise RuntimeError(f"All LLM generation providers failed: {e}")

# Global singleton
llm_client = LLMClient()
