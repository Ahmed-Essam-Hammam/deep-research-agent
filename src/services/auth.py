from typing import Annotated

from fastapi import Depends
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordRequestForm,
)

from src.dependencies.database import DBsessionDep
from src.exceptions.exceptions import (
    AlreadyRegisteredException,
    IncorrectPasswordException,
    UnauthorizedException,
)
from src.models.db.entities.tokens import Token
from src.models.db.entities.users import User
from src.models.db.schemas.users import PasswordUpdate, UserCreate, UserInDB
from src.services.tokens import PasswordService, TokenService
from src.services.users import UserService

security = HTTPBearer()
LoginFormDep = Annotated[OAuth2PasswordRequestForm, Depends()]
AuthHeaderDep = Annotated[HTTPAuthorizationCredentials, Depends(security)]


class AuthService:
    def __init__(self, session: DBsessionDep):
        self.password_service = PasswordService()
        self.token_service = TokenService(session)
        self.user_service = UserService(session)

    async def register_user(self, user: UserCreate) -> User:
        if await self.user_service.get_by_username(user.username):
            raise AlreadyRegisteredException

        hashed_password = await self.password_service.get_password_hash(user.password)

        return await self.user_service.create(
            UserInDB(username=user.username, hashed_password=hashed_password)
        )

    async def authenticate_user(self, from_data: LoginFormDep) -> Token:
        if not (user := await self.user_service.get_by_username(from_data.username)):
            raise UnauthorizedException
        if not await self.password_service.verify_password(
            from_data.password, user.hashed_password
        ):
            raise UnauthorizedException

        return await self.token_service.create_access_token(
            user_id=user.id, extra_claims={"username": user.username}
        )

    async def get_current_user(self, credentials: AuthHeaderDep) -> User:
        if credentials.scheme != "Bearer":
            raise UnauthorizedException
        if not (token := credentials.credentials):
            raise UnauthorizedException

        payload = self.token_service.decode(token)
        if not await self.token_service.validate(int(payload.get("sub"))):
            raise UnauthorizedException
        if not (username := payload.get("username")):
            raise UnauthorizedException
        if not (user := await self.user_service.get_by_username(username)):
            raise UnauthorizedException

        return user

    async def logout(self, credentials: AuthHeaderDep) -> None:
        payload = self.token_service.decode(credentials.credentials)
        await self.token_service.deactivate(payload.get("sub"))

    async def reset_password(self, user: User, payload: PasswordUpdate) -> User:
        if not await self.password_service.verify_password(
            payload.current_password, user.hashed_password
        ):
            raise IncorrectPasswordException

        new_hashed_password = await self.password_service.get_password_hash(
            payload.new_password
        )
        return await self.user_service.update_password(user.id, new_hashed_password)
