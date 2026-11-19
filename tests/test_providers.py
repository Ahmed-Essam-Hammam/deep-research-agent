from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.providers.embedding.factory import get_embedding_provider
from src.providers.embedding.openrouter_provider import OpenRouterEmbeddingProvider
from src.providers.llm.anthropic_provider import AnthropicProvider
from src.providers.llm.base import LLMProvider
from src.providers.llm.factory import get_llm_provider, register_llm_provider
from src.providers.llm.openrouter_provider import OpenRouterProvider

# ===== LLM provider factory =====


def test_llm_factory_returns_an_openrouter_provider_by_default():
    assert isinstance(get_llm_provider("openrouter"), OpenRouterProvider)


def test_llm_factory_returns_an_anthropic_provider():
    assert isinstance(get_llm_provider("anthropic"), AnthropicProvider)


def test_llm_factory_is_case_insensitive():
    assert isinstance(get_llm_provider("OpenRouter"), OpenRouterProvider)


def test_llm_factory_raises_for_an_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_provider("does-not-exist")


def test_register_llm_provider_adds_a_new_entry():
    class FakeProvider(LLMProvider):
        def get_chat_model(
            self, model=None, temperature=None, max_tokens=None, **kwargs
        ):
            return "fake-model"

    register_llm_provider("fake", lambda: FakeProvider())
    try:
        assert isinstance(get_llm_provider("fake"), FakeProvider)
    finally:
        from src.providers.llm.factory import _PROVIDER_REGISTRY

        _PROVIDER_REGISTRY.pop("fake", None)


# ===== OpenRouterProvider (mocked ChatOpenAI - no network) =====


def test_openrouter_provider_uses_the_given_api_key_and_base_url():
    provider = OpenRouterProvider(
        api_key="explicit-key", base_url="https://example.com/v1"
    )
    assert provider.api_key == "explicit-key"
    assert provider.base_url == "https://example.com/v1"


def test_openrouter_provider_falls_back_to_settings_api_key():
    provider = OpenRouterProvider()
    assert provider.api_key == "test-openrouter-key"


def test_openrouter_provider_get_chat_model_uses_default_model_when_none_given():
    provider = OpenRouterProvider(api_key="k", default_model="openrouter/auto")

    with patch("src.providers.llm.openrouter_provider.ChatOpenAI") as fake_chat_openai:
        provider.get_chat_model()

    assert fake_chat_openai.call_args.kwargs["model"] == "openrouter/auto"


# ===== Embedding provider factory =====


def test_embedding_factory_returns_an_openrouter_provider_by_default():
    with patch("src.providers.embedding.openrouter_provider.OpenAIEmbeddings"):
        assert isinstance(
            get_embedding_provider("openrouter"), OpenRouterEmbeddingProvider
        )


# ===== OpenRouterEmbeddingProvider (mocked OpenAIEmbeddings - no network) =====


def test_openrouter_embedding_provider_disables_tiktoken_precheck():
    with patch(
        "src.providers.embedding.openrouter_provider.OpenAIEmbeddings"
    ) as fake_embeddings:
        OpenRouterEmbeddingProvider(api_key="k")

    passed_kwargs = fake_embeddings.call_args.kwargs
    assert passed_kwargs["tiktoken_enabled"] is False
    assert passed_kwargs["check_embedding_ctx_length"] is False
    assert passed_kwargs["model"] == "nvidia/nemotron-3-embed-1b:free"


@pytest.mark.asyncio
async def test_embed_query_delegates_to_the_underlying_client():
    with patch(
        "src.providers.embedding.openrouter_provider.OpenAIEmbeddings"
    ) as fake_embeddings_cls:
        fake_client = MagicMock()
        fake_client.aembed_query = AsyncMock(return_value=[0.1, 0.2])
        fake_embeddings_cls.return_value = fake_client

        provider = OpenRouterEmbeddingProvider(api_key="k")
        result = await provider.embed_query("hello")

    assert result == [0.1, 0.2]
    fake_client.aembed_query.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_embed_documents_delegates_to_the_underlying_client():
    with patch(
        "src.providers.embedding.openrouter_provider.OpenAIEmbeddings"
    ) as fake_embeddings_cls:
        fake_client = MagicMock()
        fake_client.aembed_documents = AsyncMock(return_value=[[0.1], [0.2]])
        fake_embeddings_cls.return_value = fake_client

        provider = OpenRouterEmbeddingProvider(api_key="k")
        result = await provider.embed_documents(["a", "b"])

    assert result == [[0.1], [0.2]]
    fake_client.aembed_documents.assert_called_once_with(["a", "b"])
