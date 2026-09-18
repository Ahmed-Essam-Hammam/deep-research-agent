from typing import Callable, Dict, Optional

from src.providers.search.base import SearchProvider
from src.providers.search.tavily_provider import TavilySearchProvider

_PROVIDER_REGISTRY: Dict[str, Callable[[Optional[str]], SearchProvider]] = {
    "tavily": lambda api_key: TavilySearchProvider(api_key=api_key),
}


def register_search_provider(name: str, factory: Callable[[Optional[str]], SearchProvider]) -> None:

    _PROVIDER_REGISTRY[name.lower()] = factory


def get_search_provider(name: str, api_key: Optional[str] = None) -> SearchProvider:
    key = name.lower()
    if key not in _PROVIDER_REGISTRY:
        available = ", ".join(sorted(_PROVIDER_REGISTRY))
        raise ValueError(f"Unknown search provider '{name}'. Available providers: {available}")
    return _PROVIDER_REGISTRY[key](api_key)
