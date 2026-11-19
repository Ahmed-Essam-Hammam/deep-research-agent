from langchain_openai import OpenAIEmbeddings

from src.config.settings import get_settings
from src.providers.embedding.base import EmbeddingProvider

settings = get_settings()

API_KEY = settings.openrouter_api_key
DEFAULT_MODEL = settings.embedding_model
DEFAULT_BASE_URL = settings.openrouter_site_url


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        default_model: str = DEFAULT_MODEL,
    ):

        if not api_key:
            api_key = API_KEY

        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model

        self.client = OpenAIEmbeddings(
            model=self.default_model,
            api_key=self.api_key,
            base_url=self.base_url,
            tiktoken_enabled=False,
            check_embedding_ctx_length=False,
            encoding_format="float",
        )

    async def embed_query(self, text: str) -> list[float]:
        return await self.client.aembed_query(text)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self.client.aembed_documents(texts)
