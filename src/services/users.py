from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db.entities.users import User
from src.models.db.schemas.users import UserCreate, UserUpdate
from src.repositories.users import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.repository = UserRepository(session)

    async def list(self, skip: int, take: int) -> list[User]:
        return await self.repository.list(skip, take)

    async def get(self, user_id: UUID) -> User | None:
        return await self.repository.get(user_id)

    async def get_by_username(self, username: str) -> User | None:
        return await self.repository.get_by_username(username)

    async def create(self, user: UserCreate) -> User:
        return await self.repository.create(user)

    async def update(self, user_id: UUID, user: UserUpdate) -> User | None:
        return await self.repository.update(user_id, user)

    async def update_password(self, user_id: UUID, hashed_password: str) -> User | None:
        return await self.repository.update_password(user_id, hashed_password)

    async def delete(self, user_id: UUID) -> None:
        await self.repository.delete(user_id)
