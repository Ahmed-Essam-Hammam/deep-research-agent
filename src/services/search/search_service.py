from typing_extensions import List, Literal
from src.providers.search.base import SearchProvider


class SearchService:
    def __init__(self, search_client: SearchProvider):
        self.search_client = search_client


    def tavily_search_multiple(
        self,
        search_queries: List[str], 
        max_results: int = 3, 
        topic: Literal["general", "news", "finance"] = "general", 
        include_raw_content: bool = True, 
    ) -> List[dict]:
        """Perform search using Tavily API for multiple queries.

        Args:
            search_queries: List of search queries to execute
            max_results: Maximum number of results per query
            topic: Topic filter for search results
            include_raw_content: Whether to include raw webpage content

        Returns:
            List of search result dictionaries
        """

        # Execute searches sequentially. Note: yon can use AsyncTavilyClient to parallelize this step.
        search_docs = []
        for query in search_queries:
            result = self.search_client.search(
                query,
                max_results=max_results,
                include_raw_content=include_raw_content,
                topic=topic
            )
            search_docs.append(result)

        return search_docs