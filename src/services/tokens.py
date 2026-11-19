from datetime import UTC, datetime, timedelta

from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import UUID4
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies.injection import get_app_settings
from src.exceptions.exceptions import UnauthorizedException
from src.models.db.schemas.tokens import TokenCreate, TokenUpdate
from src.repositories.tokens import TokenRepository

settings = get_app_settings()


class PasswordService:
    security = HTTPBearer()
    pwd_context = CryptContext(schemes=["bcrypt"])

    async def verify_password(self, password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(password, hashed_password)

    async def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)


class TokenService(TokenRepository):
    def __init__(self, session: AsyncSession):
        self.repository = TokenRepository(session)
        self.secret_key = settings.secret_key_sign_tokens
        self.algorithm = settings.encryption_algorithm
        self.expires_in_minutes = settings.token_expiration_time_minutes

    async def create_access_token(
        self,
        user_id,
        extra_claims: dict | None = None,
        expires_delta: timedelta | None = None,
    ) -> str:
        if expires_delta:
            expire = datetime.now(UTC) + expires_delta

        else:
            expire = datetime.now(UTC) + timedelta(minutes=self.expires_in_minutes)

        token_record = await self.repository.create(
            TokenCreate(user_id=user_id, expires_at=expire)
        )

        to_encode = dict(extra_claims or {})
        to_encode.update(
            {
                "sub": str(token_record.id),
                "user_id": str(user_id),
                "exp": expire,
                "iss": "deep-research-api",
            }
        )
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    async def deactivate(self, token_id: UUID4) -> None:
        await self.repository.update(TokenUpdate(id=token_id, is_active=False))

    def decode(self, encoded_token: str) -> dict:
        try:
            return jwt.decode(
                encoded_token, self.secret_key, algorithms=[self.algorithm]
            )
        except JWTError:
            raise UnauthorizedException

    async def validate(self, token_id: UUID4) -> bool:
        return (
            token := await self.repository.get(token_id)
        ) is not None and token.is_active
