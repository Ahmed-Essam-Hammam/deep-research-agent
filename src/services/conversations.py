from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies.injection import get_app_settings
from src.models.db.entities.conversations import Conversation
from src.models.db.entities.messages import Message
from src.models.db.schemas.conversations import ConversationCreate, ConversationUpdate
from src.prompts.prompts import TITLE_GENERATION_SYSTEM_PROMPT
from src.providers.llm.base import LLMProvider
from src.repositories.conversations import ConversationRepository
from src.repositories.messages import MessageRepository

settings = get_app_settings()


class ConversationService(ConversationRepository):
    def __init__(self, session: AsyncSession, llm_provider: LLMProvider) -> None:
        self.repository = ConversationRepository(session)
        self.message_repository = MessageRepository(session)
        self.llm_provider = llm_provider

    async def generate_title(self, initial_prompt: str) -> str:
        try:
            model = self.llm_provider.get_chat_model(temperature=0.3, max_tokens=20)
            response = await model.ainvoke(
                [
                    SystemMessage(content=TITLE_GENERATION_SYSTEM_PROMPT),
                    HumanMessage(content=initial_prompt),
                ]
            )
            title = (response.content or "").strip().strip('"')
            if title:
                return title

        except Exception as exc:
            print(f"Title generation failed, falling back to a truncated prompt: {exc}")

        if len(initial_prompt) <= settings.title_fallback_length:
            return initial_prompt
        return initial_prompt[: settings.title_fallback_length - 3] + "..."

    async def list(self, user_id: UUID, skip: int, take: int) -> list[Message]:
        return await self.repository.list(user_id, skip, take)

    async def get(self, conversation_id: int, user_id: UUID) -> Conversation | None:
        return await self.repository.get(conversation_id, user_id)

    async def create(
        self, user_id: UUID, conversation: ConversationCreate
    ) -> Conversation:
        title = conversation.title or await self.generate_title(
            conversation.initial_prompt
        )
        new_conversation = Conversation(
            user_id=user_id, title=title, model_type=conversation.model_type
        )
        return await self.repository.create(new_conversation)

    async def update(
        self, user_id: UUID, conversation_id: int, conversation: ConversationUpdate
    ) -> Conversation | None:
        return await self.repository.update(conversation_id, user_id, conversation)

    async def delete(self, conversation_id: int, user_id: UUID) -> None:
        await self.repository.delete(conversation_id, user_id)

    async def touch(self, conversation_id: int) -> None:
        await self.repository.touch(conversation_id)
