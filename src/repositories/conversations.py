from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession
from src.repositories.interfaces import Repository
from src.models.db.entities.conversations import Conversation
from src.models.db.schemas.conversations import ConversationCreate, ConversationUpdate


class ConversationRepository(Repository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session


    async def list(self, user_id: UUID, skip: int, take: int) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc()).offset(skip).limit(take)
        )
        return [r for r in result.scalars().all()]


    async def get(self, conversation_id: int, user_id: UUID) -> Conversation | None:
        result = await self.session.execute(
            select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
        )
        return result.scalars().first()


    async def create(self, conversation: ConversationCreate) -> Conversation:
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation


    async def update(self, conversation_id: int, user_id: UUID, updated_conversation: ConversationUpdate) -> Conversation | None:
        conversation = await self.get(conversation_id, user_id)
        if not conversation:
            return None
        for key, value in updated_conversation.model_dump().items():
            setattr(conversation, key, value)
            
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation


    async def delete(self, conversation_id: int, user_id: UUID) -> None:
        conversation = await self.get(conversation_id, user_id)
        if not conversation:
            return
        await self.session.delete(conversation)
        await self.session.commit()


    async def touch(self, conversation_id: int) -> None:
        conversation = await self.session.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = datetime.now(UTC)
            await self.session.commit()

