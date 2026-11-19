from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.entities.tokens import Token
from src.models.db.schemas.tokens import TokenCreate, TokenUpdate
from src.repositories.interfaces import Repository


class TokenRepository(Repository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, skip: int, take: int) -> list[Token]:
        result = await self.session.execute(select(Token).offset(skip).limit(take))
        return [r for r in result.scalars().all()]

    async def get(self, token_id: int) -> Token | None:
        result = await self.session.execute(select(Token).where(Token.id == token_id))
        return result.scalars().first()

    async def create(self, token: TokenCreate) -> Token:
        new_token = Token(**token.model_dump())
        self.session.add(new_token)
        await self.session.commit()
        await self.session.refresh(new_token)
        return new_token

    async def update(self, token_id: int, updated_token: TokenUpdate) -> Token | None:
        token = await self.get(token_id)
        if not token:
            return None
        for key, value in updated_token.model_dump(exclude_unset=True).items():
            setattr(token, key, value)

        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def delete(self, token_id: int) -> None:
        token = await self.get(token_id)
        if not token:
            return

        await self.session.delete(token)
        await self.session.commit()
