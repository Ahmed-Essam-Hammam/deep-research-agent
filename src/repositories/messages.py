from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.models.db.entities.conversations import Conversation
from src.models.db.entities.messages import Message
from src.models.db.schemas.messages import MessageCreate, MessageUpdate
from src.repositories.interfaces import Repository


class MessageRepository(Repository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def recent_messages_subquery(
        self, user_id: UUID, lookback: int, require_embedding: bool = False
    ):
        conditions = [Conversation.user_id == user_id]
        if require_embedding:
            conditions.append(Message.input_query_embeddings.is_not(None))

        return (
            select(Message)
            .join(Conversation, Conversation.id == Message.conversation_id)
            .where(*conditions)
            .order_by(Message.created_at.desc())
            .limit(lookback)
            .subquery()
        )

    async def top_semantic_matches(
        self, user_id: UUID, embedding: list[float], lookback: int = 20, limit: int = 3
    ) -> list[tuple[Message, float]]:

        recent_subquery = self.recent_messages_subquery(
            user_id, lookback, require_embedding=True
        )
        recent_message = aliased(Message, recent_subquery)

        distance = recent_message.input_query_embeddings.cosine_distance(embedding)
        result = await self.session.execute(
            select(recent_message, (1 - distance).label("similarity"))
            .order_by(distance.asc())
            .limit(limit)
        )

        return [(message, similarity) for message, similarity in result.all()]

    async def top_keyword_matches(
        self, user_id: UUID, query_text: str, lookback: int = 20, limit: int = 3
    ) -> list[tuple[Message, float]]:

        recent_subquery = self.recent_messages_subquery(
            user_id, lookback, require_embedding=False
        )
        recent_message = aliased(Message, recent_subquery)

        missing_ids = (
            (
                await self.session.execute(
                    select(recent_message.id).where(recent_message.ts_vector.is_(None))
                )
            )
            .scalars()
            .all()
        )

        if missing_ids:
            await self.session.execute(
                update(Message)
                .where(Message.id.in_(missing_ids))
                .values(ts_vector=func.to_tsvector("english", Message.prompt_content))
            )
            await self.session.commit()

        query = func.plainto_tsquery("english", query_text)

        # normalization flag `1`, which bounds ts_rank_cd's output to [0, 1]
        rank = func.ts_rank_cd(recent_message.ts_vector, query, 1).label("rank")

        result = await self.session.execute(
            select(recent_message, rank)
            .where(recent_message.ts_vector.op("@@")(query))
            .order_by(rank.desc())
            .limit(limit)
        )

        return [(message, score) for message, score in result.all()]

    async def list(self, conversation_id: int) -> list[Message]:
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def get(self, message_id: int) -> Message | None:
        result = await self.session.execute(
            select(Message).where(Message.id == message_id)
        )
        return result.scalars().first()

    async def create(self, message: MessageCreate) -> Message:
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def update(
        self, message_id: int, updated_message: MessageUpdate
    ) -> Message | None:
        token = await self.get(message_id)
        if not token:
            return None
        for key, value in updated_message.model_dump(exclude_unset=True).items():
            setattr(token, key, value)

        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def delete(self, message_id: int) -> None:
        token = await self.get(message_id)
        if not token:
            return

        await self.session.delete(token)
        await self.session.commit()
