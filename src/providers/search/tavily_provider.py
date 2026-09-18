from typing import Literal, Optional

from tavily import TavilyClient

from src.providers.search.base import SearchProvider


class TavilySearchProvider(SearchProvider):

    def __init__(self, api_key: Optional[str] = None):
        # TavilyClient reads TAVILY_API_KEY from the environment if api_key is None.
        self._client = TavilyClient(api_key=api_key) if api_key else TavilyClient()

    def search(
        self,
        query: str,
        max_results: int = 3,
        topic: Literal["general", "news", "finance"] = "general",
        include_raw_content: bool = True,
    ) -> dict:
        return self._client.search(
            query,
            max_results=max_results,
            include_raw_content=include_raw_content,
            topic=topic,
        )
