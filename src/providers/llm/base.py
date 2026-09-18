from abc import ABC, abstractmethod
from typing import Any, Optional


class LLMProvider(ABC):

    @abstractmethod
    def get_chat_model(
        self,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:

        raise NotImplementedError
