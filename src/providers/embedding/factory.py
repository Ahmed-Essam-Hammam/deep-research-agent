from typing import Callable, Dict

from src.providers.embedding.base import EmbeddingProvider
from src.providers.embedding.openrouter_provider import OpenRouterEmbeddingProvider

_PROVIDER_REGISTRY: Dict[str, Callable[[], EmbeddingProvider]] = {
    "openrouter": OpenRouterEmbeddingProvider,
}


def register_embedding_provider(
    name: str, factory: Callable[[], EmbeddingProvider]
) -> None:
    _PROVIDER_REGISTRY[name.lower()] = factory


def get_embedding_provider(name: str) -> EmbeddingProvider:
    key = name.lower()

    if key not in _PROVIDER_REGISTRY:
        available = ", ".join(sorted(_PROVIDER_REGISTRY))
        raise ValueError(
            f"Unknown embedding provider '{name}'. Available providers: {available}"
        )
    return _PROVIDER_REGISTRY[key]()
