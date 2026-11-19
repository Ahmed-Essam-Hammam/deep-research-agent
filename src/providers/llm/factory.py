from typing import Callable, Dict

from src.providers.llm.anthropic_provider import AnthropicProvider
from src.providers.llm.base import LLMProvider
from src.providers.llm.openai_provider import OpenAIProvider
from src.providers.llm.openrouter_provider import OpenRouterProvider

_PROVIDER_REGISTRY: Dict[str, Callable[[], LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "openrouter": OpenRouterProvider,
}


def register_llm_provider(name: str, factory: Callable[[], LLMProvider]) -> None:

    _PROVIDER_REGISTRY[name.lower()] = factory


def get_llm_provider(name: str) -> LLMProvider:
    key = name.lower()
    if key not in _PROVIDER_REGISTRY:
        available = ", ".join(sorted(_PROVIDER_REGISTRY))
        raise ValueError(
            f"Unknown LLM provider '{name}'. Available providers: {available}"
        )
    return _PROVIDER_REGISTRY[key]()
