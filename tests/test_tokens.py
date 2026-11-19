from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from jose import jwt

from src.exceptions.exceptions import UnauthorizedException
from src.models.db.entities.tokens import Token
from src.models.db.schemas.tokens import TokenCreate, TokenUpdate
from src.repositories.tokens import TokenRepository
from src.services.tokens import PasswordService, TokenService
from tests.conftest import future_expiry

# ===== PasswordService (real bcrypt) =====


@pytest.mark.asyncio
async def test_get_password_hash_does_not_return_the_plaintext():
    service = PasswordService()
    hashed = await service.get_password_hash("Abcdef12")
    assert hashed != "Abcdef12"
    assert hashed.startswith("$2b$")


@pytest.mark.asyncio
async def test_verify_password_succeeds_for_the_correct_password():
    service = PasswordService()
    hashed = await service.get_password_hash("Abcdef12")
    assert await service.verify_password("Abcdef12", hashed) is True


@pytest.mark.asyncio
async def test_verify_password_fails_for_the_wrong_password():
    service = PasswordService()
    hashed = await service.get_password_hash("Abcdef12")
    assert await service.verify_password("wrong-password", hashed) is False


# ===== TokenRepository (integration) =====


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_persists_a_token(db_session):
    repo = TokenRepository(db_session)
    user_id = uuid4()

    created = await repo.create(
        TokenCreate(user_id=user_id, expires_at=future_expiry())
    )

    assert created.id is not None
    assert created.user_id == user_id
    assert created.is_active is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_can_deactivate_a_token_when_called_correctly(db_session):

    repo = TokenRepository(db_session)
    created = await repo.create(
        TokenCreate(user_id=uuid4(), expires_at=future_expiry())
    )

    updated = await repo.update(
        created.id,
        TokenUpdate(
            user_id=created.user_id, expires_at=created.expires_at, is_active=False
        ),
    )

    assert updated.is_active is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_removes_the_token(db_session):
    repo = TokenRepository(db_session)
    created = await repo.create(
        TokenCreate(user_id=uuid4(), expires_at=future_expiry())
    )

    await repo.delete(created.id)
    assert await repo.get(created.id) is None


# ===== TokenService.create_access_token (unit, mocked repository) =====


def _token_service_with_mock_repo():
    service = TokenService(session=MagicMock())
    service.repository = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_create_access_token_encodes_the_expected_claims():
    service = _token_service_with_mock_repo()
    user_id = uuid4()
    service.repository.create.return_value = Token(
        id=42, user_id=user_id, expires_at=future_expiry()
    )

    encoded = await service.create_access_token(
        user_id=user_id, extra_claims={"username": "alice"}
    )

    payload = jwt.decode(encoded, service.secret_key, algorithms=[service.algorithm])
    assert payload["sub"] == "42"
    assert payload["user_id"] == str(user_id)
    assert payload["username"] == "alice"
    assert payload["iss"] == "deep-research-api"


# @pytest.mark.asyncio
# async def test_create_access_token_uses_default_expiry_when_no_delta_given():
#     service = _token_service_with_mock_repo()
#     user_id = uuid4()
#     service.repository.create.return_value = Token(id=1, user_id=user_id, expires_at=future_expiry())

#     await service.create_access_token(user_id=user_id)

#     passed_token_create = service.repository.create.call_args.args[0]
#     expected_minutes = service.expires_in_minutes
#     delta = passed_token_create.expires_at - future_expiry(0)
#     assert abs(delta.total_seconds() - expected_minutes * 60) < 5  # small tolerance for test execution time


# ===== TokenService.decode (real JWT, no mocks) =====


def test_decode_round_trips_a_token_signed_with_the_same_secret():
    service = _token_service_with_mock_repo()
    encoded = jwt.encode(
        {"sub": "1", "user_id": "abc"}, service.secret_key, algorithm=service.algorithm
    )

    payload = service.decode(encoded)

    assert payload["sub"] == "1"
    assert payload["user_id"] == "abc"


def test_decode_raises_unauthorized_for_a_garbage_token():
    service = _token_service_with_mock_repo()
    with pytest.raises(HTTPException) as exc_info:
        service.decode("not-a-real-jwt")
    assert exc_info.value is UnauthorizedException


# ===== TokenService.validate (unit, mocked repository) =====


@pytest.mark.asyncio
async def test_validate_returns_true_for_an_active_token():
    service = _token_service_with_mock_repo()
    service.repository.get.return_value = Token(
        id=1, user_id=uuid4(), expires_at=future_expiry(), is_active=True
    )

    assert await service.validate(1) is True


@pytest.mark.asyncio
async def test_validate_returns_false_for_an_inactive_token():
    service = _token_service_with_mock_repo()
    service.repository.get.return_value = Token(
        id=1, user_id=uuid4(), expires_at=future_expiry(), is_active=False
    )

    assert await service.validate(1) is False
