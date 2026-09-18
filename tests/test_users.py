from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.exceptions.exceptions import AlreadyRegisteredException, IncorrectPasswordException, UnauthorizedException
from src.models.db.schemas.users import (
    PasswordUpdate,
    UserCreate,
    UserInDB,
    UserUpdate,
    validate_password,
    validate_username,
)
from src.models.db.entities.users import User
from src.repositories.users import UserRepository
from src.services.auth import AuthService
from tests.conftest import unique_username


# ===== Schema validation: username =====

def test_validate_username_accepts_alphanumeric():
    assert validate_username("alice123") == "alice123"


@pytest.mark.parametrize("bad_username", ["alice smith", "alice-smith", "alice_smith", "alice!"])
def test_validate_username_rejects_non_alphanumeric(bad_username):
    with pytest.raises(ValueError):
        validate_username(bad_username)


def test_user_create_rejects_username_shorter_than_3_chars():
    with pytest.raises(ValidationError):
        UserCreate(username="ab", password="Abcdef12")


def test_validate_password_raises_without_a_digit():
    with pytest.raises(ValueError, match="digit"):
        validate_password("Abcdefgh")


def test_validate_password_accepts_a_fully_valid_password():
    assert validate_password("Abcdefg1") == "Abcdefg1"


def test_validate_password_should_reject_password_missing_uppercase():
    with pytest.raises(ValueError, match="uppercase"):
        validate_password("abcdefg1")


def test_user_create_rejects_password_shorter_than_8_chars():
    with pytest.raises(ValidationError):
        UserCreate(username="alice", password="Ab1")


# ===== UserRepository (integration) =====

@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_persists_a_new_user_with_defaults(db_session):
    repo = UserRepository(db_session)
    created = await repo.create(UserInDB(username=unique_username(), hashed_password="hashed-value"))

    assert created.id is not None
    assert created.is_active is True
    assert created.role == "USER"
    assert created.hashed_password == "hashed-value"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_by_username_finds_a_created_user(db_session):
    repo = UserRepository(db_session)
    username = unique_username()
    created = await repo.create(UserInDB(username=username, hashed_password="x"))

    found = await repo.get_by_username(username)
    assert found is not None
    assert found.id == created.id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_changes_mutable_fields(db_session):
    repo = UserRepository(db_session)
    created = await repo.create(UserInDB(username=unique_username(), hashed_password="x"))

    new_username = unique_username("renamed")
    updated = await repo.update(created.id, UserUpdate(username=new_username, is_active=False, role="ADMIN"))

    assert updated.username == new_username
    assert updated.is_active is False
    assert updated.role == "ADMIN"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_password_changes_only_the_hash(db_session):
    repo = UserRepository(db_session)
    created = await repo.create(UserInDB(username=unique_username(), hashed_password="old-hash"))

    updated = await repo.update_password(created.id, "new-hash")
    assert updated.hashed_password == "new-hash"
    assert updated.username == created.username


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_removes_the_user(db_session):
    repo = UserRepository(db_session)
    created = await repo.create(UserInDB(username=unique_username(), hashed_password="x"))

    await repo.delete(created.id)
    assert await repo.get(created.id) is None


# ===== AuthService (unit, mocked sub-services) =====

@pytest.fixture
def auth_service_with_mocks():
    service = AuthService.__new__(AuthService)  
    service.password_service = MagicMock()
    service.password_service.verify_password = AsyncMock()
    service.password_service.get_password_hash = AsyncMock()
    service.token_service = MagicMock()
    service.token_service.create_access_token = AsyncMock()
    service.token_service.decode = MagicMock()
    service.token_service.validate = AsyncMock()
    service.token_service.deactivate = AsyncMock()
    service.user_service = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_register_user_hashes_password_and_stores_user(auth_service_with_mocks):
    service = auth_service_with_mocks
    service.user_service.get_by_username.return_value = None
    service.password_service.get_password_hash.return_value = "hashed-pw"
    service.user_service.create.return_value = User(username="alice", hashed_password="hashed-pw")

    new_user = UserCreate(username="alice", password="Abcdef12")
    result = await service.register_user(new_user)

    service.password_service.get_password_hash.assert_awaited_once_with("Abcdef12")
    created_arg = service.user_service.create.call_args.args[0]
    assert isinstance(created_arg, UserInDB)
    assert created_arg.username == "alice"
    assert created_arg.hashed_password == "hashed-pw"
    assert result.username == "alice"


@pytest.mark.asyncio
async def test_register_user_raises_when_username_already_taken(auth_service_with_mocks):
    service = auth_service_with_mocks
    service.user_service.get_by_username.return_value = User(username="alice", hashed_password="x")

    with pytest.raises(HTTPException) as exc_info:
        await service.register_user(UserCreate(username="alice", password="Abcdef12"))

    assert exc_info.value is AlreadyRegisteredException
    service.user_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_user_returns_token_for_valid_credentials(auth_service_with_mocks):
    service = auth_service_with_mocks
    user = User(id=uuid4(), username="alice", hashed_password="hashed")
    service.user_service.get_by_username.return_value = user
    service.password_service.verify_password.return_value = True
    service.token_service.create_access_token.return_value = "a.jwt.token"

    form = MagicMock(username="alice", password="Abcdef12")
    token = await service.authenticate_user(form)

    assert token == "a.jwt.token"
    service.token_service.create_access_token.assert_awaited_once_with(
        user_id=user.id, extra_claims={"username": "alice"}
    )


@pytest.mark.asyncio
async def test_authenticate_user_raises_for_wrong_password(auth_service_with_mocks):
    service = auth_service_with_mocks
    service.user_service.get_by_username.return_value = User(username="alice", hashed_password="hashed")
    service.password_service.verify_password.return_value = False

    with pytest.raises(HTTPException) as exc_info:
        await service.authenticate_user(MagicMock(username="alice", password="wrong"))

    assert exc_info.value is UnauthorizedException


@pytest.mark.asyncio
async def test_get_current_user_returns_user_for_a_valid_bearer_token(auth_service_with_mocks):
    service = auth_service_with_mocks
    service.token_service.decode.return_value = {"sub": "7", "username": "alice"}
    service.token_service.validate.return_value = True
    service.user_service.get_by_username.return_value = User(username="alice", hashed_password="x")

    credentials = MagicMock(scheme="Bearer", credentials="a.jwt.token")
    user = await service.get_current_user(credentials)

    assert user.username == "alice"
    service.token_service.validate.assert_awaited_once_with(7)


@pytest.mark.asyncio
async def test_get_current_user_rejects_an_inactive_token(auth_service_with_mocks):
    service = auth_service_with_mocks
    service.token_service.decode.return_value = {"sub": "7", "username": "alice"}
    service.token_service.validate.return_value = False

    credentials = MagicMock(scheme="Bearer", credentials="a.jwt.token")
    with pytest.raises(HTTPException) as exc_info:
        await service.get_current_user(credentials)

    assert exc_info.value is UnauthorizedException


@pytest.mark.asyncio
async def test_logout_deactivates_the_token_from_the_bearer_credentials(auth_service_with_mocks):
    service = auth_service_with_mocks
    service.token_service.decode.return_value = {"sub": "7"}
    credentials = MagicMock(credentials="a.jwt.token")

    await service.logout(credentials)

    service.token_service.deactivate.assert_awaited_once_with("7")


@pytest.mark.asyncio
async def test_reset_password_raises_for_wrong_current_password(auth_service_with_mocks):
    service = auth_service_with_mocks
    service.password_service.verify_password.return_value = False
    user = User(username="alice", hashed_password="hashed")

    with pytest.raises(HTTPException) as exc_info:
        await service.reset_password(user, PasswordUpdate(current_password="wrong", new_password="Abcdef12"))

    assert exc_info.value is IncorrectPasswordException
    service.user_service.update_password.assert_not_called()


@pytest.mark.asyncio
async def test_reset_password_updates_for_correct_current_password(auth_service_with_mocks):
    service = auth_service_with_mocks
    service.password_service.verify_password.return_value = True
    service.password_service.get_password_hash.return_value = "new-hashed"
    user = User(id=uuid4(), username="alice", hashed_password="old-hashed")
    service.user_service.update_password.return_value = User(
        id=user.id, username="alice", hashed_password="new-hashed"
    )

    result = await service.reset_password(user, PasswordUpdate(current_password="old-pw", new_password="Abcdef12"))

    service.password_service.get_password_hash.assert_awaited_once_with("Abcdef12")
    service.user_service.update_password.assert_awaited_once_with(user.id, "new-hashed")
    assert result.hashed_password == "new-hashed"
