from functools import lru_cache

from src.config.settings import Settings, get_settings
from src.providers.llm.base import LLMProvider
from src.providers.llm.factory import get_llm_provider as _get_llm_provider
from src.providers.search.base import SearchProvider
from src.providers.search.factory import get_search_provider as _get_search_provider
from src.providers.embedding.factory import get_embedding_provider as _get_embedding_provider
from src.providers.embedding.base import EmbeddingProvider


@lru_cache
def get_app_settings() -> Settings:
    """Dependency-injectable accessor for application settings."""
    return get_settings()

@lru_cache
def get_default_llm_provider() -> LLMProvider:
    """The system-wide default LLM provider (used unless a node overrides it)."""
    settings = get_app_settings()
    return _get_llm_provider(settings.default_llm_provider)

def get_llm_provider_by_name(name: str) -> LLMProvider:
    """Resolve any registered LLM provider by name (not cached - cheap to build)."""
    return _get_llm_provider(name)

@lru_cache
def get_default_search_provider() -> SearchProvider:
    """The configured SearchProvider (e.g. Tavily), built once and cached."""
    settings = get_app_settings()
    api_key = settings.tavily_api_key or None
    return _get_search_provider(settings.search_provider, api_key=api_key)

@lru_cache
def get_default_embedding_provider() -> EmbeddingProvider:
    """The system-wide default EmbeddingProvider (used for semantic caching)."""
    settings = get_app_settings()
    return _get_embedding_provider(settings.embedding_provider)