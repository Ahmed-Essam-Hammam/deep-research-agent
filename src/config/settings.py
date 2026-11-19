from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    tavily_api_key: str = Field(default="", description="API key for Tavily search")
    openai_api_key: str = Field(default="", description="API key for OpenAI")
    anthropic_api_key: str = Field(default="", description="API key for Anthropic")
    openrouter_api_key: str = Field(default="", description="API key for OpenRouter")
    openrouter_site_url: str = Field(
        default="",
        description="Optional HTTP-Referer sent to OpenRouter for attribution",
    )
    openrouter_app_name: str = Field(
        default="", description="Optional X-Title sent to OpenRouter for attribution"
    )

    langsmith_api_key: str = Field(default="")
    langsmith_tracing: bool = Field(default=True)
    langsmith_project: str = Field(default="deep_research_from_scratch")
    langsmith_endpoint: str = Field(default="https://api.smith.langchain.com")

    default_llm_provider: str = Field(default="openrouter")
    default_llm_model: str = Field(default="openrouter/auto")

    scoping_llm_provider: str = Field(default="openrouter")
    scoping_llm_model: str = Field(default="openrouter/auto")

    compression_llm_provider: str = Field(default="openrouter")
    compression_llm_model: str = Field(default="openrouter/auto")
    compression_llm_max_tokens: int = Field(default=1000)

    writer_llm_provider: str = Field(default="openrouter")
    writer_llm_model: str = Field(default="openrouter/auto")
    writer_llm_max_tokens: int = Field(default=1000)

    summarization_llm_provider: str = Field(default="openrouter")
    summarization_llm_model: str = Field(default="openrouter/auto")

    supervisor_llm_provider: str = Field(default="openrouter")
    supervisor_llm_model: str = Field(default="openrouter/auto")

    researcher_llm_provider: str = Field(default="openrouter")
    researcher_llm_model: str = Field(default="openrouter/auto")

    search_provider: str = Field(
        default="tavily", description="Which SearchProvider implementation to use"
    )
    search_max_results: int = Field(default=3)
    search_topic: str = Field(default="general")
    search_include_raw_content: bool = Field(default=True)

    embedding_provider: str = Field(
        default="openrouter",
        description="Which EmbeddingProvider implementation to use",
    )
    embedding_model: str = Field(
        default="nvidia/nemotron-3-embed-1b:free",
        description="Embedding model id passed to the embedding provider",
    )
    embedding_dimensions: int = Field(
        default=2048,
        description="The dimension of the generated embedding vector, must me compatible with the embedding model",
    )

    cache_enabled: bool = Field(
        default=True,
        description="Whether to check the response cache (semantic + keyword) before calling the LLM",
    )
    cache_lookback: int = Field(
        default=20,
        description="How many of the user's most recent messages (across all their conversations) form the candidate pool for both the semantic and keyword cache lookups",
    )
    cache_top_n_per_method: int = Field(
        default=3,
        description="How many top candidates to take from the semantic lookup and from the keyword lookup before fusing them",
    )
    cache_rrf_k: int = Field(
        default=60,
        description="The 'k' constant in the Reciprocal Rank Fusion formula 1/(k+rank); higher k flattens the influence of rank position",
    )
    cache_hit_score_threshold: float = Field(
        default=0.80,
        description="Minimum normalized fused score (0-1) required to serve a cached response instead of calling the LLM",
    )

    max_researcher_iterations: int = Field(
        default=6, description="Max supervisor <-> tool loop iterations"
    )
    max_concurrent_researchers: int = Field(
        default=3, description="Max parallel ConductResearch sub-agents"
    )
    researcher_max_tool_calls_simple: int = Field(default=3)
    researcher_max_tool_calls_complex: int = Field(default=5)

    token_expiration_time_minutes: int = Field(
        default=60, description="How much time does the token has before it expires"
    )
    encryption_algorithm: str = Field(default="")
    secret_key_sign_tokens: str = Field(
        default="",
        description="A private key used to sign and verify your JWT tokens, to to verify that the token was actually signed by your server and hasn't been modified",
    )

    postgres_url: str = Field(default="", description="Postgres database URL")

    title_fallback_length: int = Field(
        default=50,
        description="Fallback length of the generated title of a conversation",
    )

    message_checkpoint_interval_seconds: float = Field(
        default=1000, description="Time interval to save the response in the database"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
