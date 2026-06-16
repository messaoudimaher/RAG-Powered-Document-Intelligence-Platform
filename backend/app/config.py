from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Chroma configurations
    chroma_persist_dir: str = Field(default="data/chroma", validation_alias="CHROMA_PERSIST_DIR")
    chroma_collection_public: str = Field(
        default="public_index", validation_alias="CHROMA_COLLECTION_PUBLIC"
    )
    chroma_collection_name: str = Field(
        default="papers_index", validation_alias="CHROMA_COLLECTION_NAME"
    )

    # Ollama configurations
    ollama_base_url: str = Field(
        default="http://localhost:11434", validation_alias="OLLAMA_BASE_URL"
    )
    ollama_llm_model: str = Field(default="llama3", validation_alias="OLLAMA_LLM_MODEL")
    ollama_embed_model: str = Field(
        default="nomic-embed-text", validation_alias="OLLAMA_EMBED_MODEL"
    )

    # Gemini configuration for optional hybrid reasoning
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")

    # API configurations
    next_public_api_base_url: str = Field(
        default="http://localhost:8000", validation_alias="NEXT_PUBLIC_API_BASE_URL"
    )
    max_file_size_mb: int = Field(default=15, validation_alias="MAX_FILE_SIZE_MB")
    api_key: str = Field(default="", validation_alias="API_KEY")
    seed_sample_docs: bool = Field(default=True, validation_alias="SEED_SAMPLE_DOCS")
    enable_fallback_retrieval: bool = Field(
        default=True, validation_alias="ENABLE_FALLBACK_RETRIEVAL"
    )
    arxiv_base_url: str = Field(
        default="http://export.arxiv.org/api", validation_alias="ARXIV_BASE_URL"
    )
    disable_openapi: bool = Field(default=False, validation_alias="DISABLE_OPENAPI")
    docmind_git_sha: str = Field(default="dev", validation_alias="DOCMIND_GIT_SHA")

    # Minimum relevance threshold (cosine distance threshold)
    # Cosine distance range is 0 to 2 (0: identical, 1: orthogonal, 2: opposite).
    # A distance of <= 0.7 to 0.8 is typical for text retrieval.
    relevance_threshold: float = Field(default=0.75, validation_alias="RELEVANCE_THRESHOLD")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
