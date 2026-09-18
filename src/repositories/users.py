import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.interfaces import Repository
from src.models.db.entities.users import User
from src.models.db.schemas.users import UserCreate, UserUpdate


class UserRepository(Repository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session


    async def list(self, skip: int, take: int) -> list[User]:
        result = await self.session.execute(
            select(User).offset(skip).limit(take)
        )
        return [r for r in result.scalars().all()]

    
    async def get(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalars().first()


    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalars().first()


    async def create(self, user: UserCreate) -> User:
        new_user = User(**user.model_dump())
        self.session.add(new_user)
        await self.session.commit()
        await self.session.refresh(new_user)
        return new_user


    async def update(self, user_id: uuid.UUID, updated_user: UserUpdate) -> User | None:
        user = await self.get(user_id)
        if not user:
            return None
        for key, value in updated_user.model_dump(exclude_unset=True).items():
            setattr(user, key, value)

        await self.session.commit()
        await self.session.refresh(user)
        return user


    async def update_password(self, user_id: uuid.UUID, hashed_password: str) -> User | None:
        user = await self.get(user_id)
        if not user:
            return None
        user.hashed_password = hashed_password
        
        await self.session.commit()
        await self.session.refresh(user)
        return user


    async def delete(self, user_id: uuid.UUID) -> None:
        user = await self.get(user_id)
        if not user:
            return
        await self.session.delete(user)
        await self.session.commit()