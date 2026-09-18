from typing import Any, Optional

from langchain_openai import ChatOpenAI

from src.providers.llm.base import LLMProvider
from src.config.settings import get_settings


settings = get_settings()

API_KEY = settings.openrouter_api_key
DEFAULT_MODEL = settings.default_llm_model
DEFAULT_BASE_URL = settings.openrouter_site_url 


class OpenRouterProvider(LLMProvider):

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        default_model: str = DEFAULT_MODEL,
    ):
        if not api_key:
            api_key = API_KEY

        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model


    def get_chat_model(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        model_name = model or self.default_model

        init_kwargs: dict = {
            "model": model_name,
            "api_key": self.api_key,
            "base_url": self.base_url,
        }
        if temperature is not None:
            init_kwargs["temperature"] = temperature
        if max_tokens is not None:
            init_kwargs["max_tokens"] = max_tokens


        init_kwargs.update(kwargs)
        return ChatOpenAI(**init_kwargs)
