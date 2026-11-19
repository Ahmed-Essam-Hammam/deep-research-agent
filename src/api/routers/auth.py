from typing import Annotated

from fastapi import APIRouter, Depends

from src.dependencies.database import DBsessionDep
from src.models.db.entities.users import User
from src.models.db.schemas.tokens import TokenOut
from src.models.db.schemas.users import PasswordUpdate, UserCreate, UserOut
from src.services.auth import AuthHeaderDep, AuthService, LoginFormDep


def get_auth_service(session: DBsessionDep) -> AuthService:
    return AuthService(session)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


async def get_current_user(
    credentials: AuthHeaderDep, auth_service: AuthServiceDep
) -> User:
    return await auth_service.get_current_user(credentials)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def register_user_controller(
    new_user: UserCreate, auth_service: AuthServiceDep
) -> UserOut:
    user = await auth_service.register_user(new_user)
    return UserOut.model_validate(user)


@router.post("/token")
async def login_for_access_token_controller(
    form_data: LoginFormDep, auth_service: AuthServiceDep
) -> TokenOut:
    access_token = await auth_service.authenticate_user(form_data)
    return TokenOut(access_token=access_token, token_type="Bearer")


@router.post("/logout")
async def logout_access_token_controller(
    credentials: AuthHeaderDep, auth_service: AuthServiceDep
) -> dict:
    await auth_service.logout(credentials)
    return {"message": "Logged out"}


@router.post("/reset-password")
async def reset_password_controller(
    payload: PasswordUpdate, user: CurrentUserDep, auth_service: AuthServiceDep
) -> dict:
    await auth_service.reset_password(user, payload)
    return {"message": "Password updated successfully"}
