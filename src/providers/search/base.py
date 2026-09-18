from abc import ABC, abstractmethod
from typing import Literal


class SearchProvider(ABC):

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 3,
        topic: Literal["general", "news", "finance"] = "general",
        include_raw_content: bool = True,
    ) -> dict:

        raise NotImplementedError
