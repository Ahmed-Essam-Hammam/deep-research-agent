"""Anthropic implementation of the LLMProvider interface."""

from typing import Any

from langchain.chat_models import init_chat_model

from src.providers.llm.base import LLMProvider

DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicProvider(LLMProvider):
    def __init__(self, default_model: str = DEFAULT_MODEL):
        self.default_model = default_model

    def get_chat_model(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Any:
        model_name = model or self.default_model
        init_kwargs: dict = {}
        if temperature is not None:
            init_kwargs["temperature"] = temperature
        if max_tokens is not None:
            init_kwargs["max_tokens"] = max_tokens
        init_kwargs.update(kwargs)
        return init_chat_model(model=f"anthropic:{model_name}", **init_kwargs)
