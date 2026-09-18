from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.config.settings import get_settings
from src.models.db.entities.conversations import Conversation
from src.models.db.schemas.conversations import ConversationCreate, ConversationUpdate
from src.repositories.conversations import ConversationRepository
from src.services.conversations import ConversationService


# ===== Schema validation =====

def test_conversation_create_requires_a_non_empty_initial_prompt():
    with pytest.raises(ValidationError):
        ConversationCreate(initial_prompt="", model_type="openrouter/auto")


def test_conversation_create_allows_an_explicit_title():
    payload = ConversationCreate(initial_prompt="hello", model_type="openrouter/auto", title="My chat")
    assert payload.title == "My chat"



# ===== ConversationRepository (integration) =====

@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_persists_a_new_conversation(db_session):
    repo = ConversationRepository(db_session)
    user_id = uuid4()

    created = await repo.create(Conversation(user_id=user_id, title="Hello", model_type="openrouter/auto"))

    assert created.id is not None
    assert created.title == "Hello"
    assert created.user_id == user_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_scopes_by_user_id(db_session):
    repo = ConversationRepository(db_session)
    owner_id, other_id = uuid4(), uuid4()
    created = await repo.create(Conversation(user_id=owner_id, title="Mine", model_type="openrouter/auto"))

    assert await repo.get(created.id, owner_id) is not None
    assert await repo.get(created.id, other_id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_orders_by_updated_at_descending(db_session):
    repo = ConversationRepository(db_session)
    user_id = uuid4()
    first = await repo.create(Conversation(user_id=user_id, title="First", model_type="openrouter/auto"))
    second = await repo.create(Conversation(user_id=user_id, title="Second", model_type="openrouter/auto"))

    await repo.touch(first.id)  

    results = await repo.list(user_id, skip=0, take=10)
    assert [c.id for c in results][:2] == [first.id, second.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_with_a_full_payload_changes_all_fields(db_session):
    repo = ConversationRepository(db_session)
    user_id = uuid4()
    created = await repo.create(Conversation(user_id=user_id, title="Old", model_type="openrouter/auto"))

    updated = await repo.update(created.id, user_id, ConversationUpdate(title="New", model_type="gpt-4"))

    assert updated.title == "New"
    assert updated.model_type == "gpt-4"



@pytest.mark.integration
@pytest.mark.asyncio
async def test_delete_removes_the_conversation(db_session):
    repo = ConversationRepository(db_session)
    user_id = uuid4()
    created = await repo.create(Conversation(user_id=user_id, title="Bye", model_type="openrouter/auto"))

    await repo.delete(created.id, user_id)
    assert await repo.get(created.id, user_id) is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_touch_updates_the_updated_at_timestamp(db_session):
    repo = ConversationRepository(db_session)
    user_id = uuid4()
    created = await repo.create(Conversation(user_id=user_id, title="X", model_type="openrouter/auto"))
    original_updated_at = created.updated_at

    await repo.touch(created.id)

    refreshed = await repo.get(created.id, user_id)
    assert refreshed.updated_at > original_updated_at


# ===== ConversationService (unit, mocked repository / LLM) =====

def _service_with_mocks():
    service = ConversationService.__new__(ConversationService)  
    service.repository = AsyncMock()
    service.message_repository = AsyncMock()
    service.llm_provider = MagicMock()
    return service


@pytest.mark.asyncio
async def test_generate_title_returns_the_llm_response_stripped_and_dequoted():
    service = _service_with_mocks()
    chat_model = MagicMock()
    chat_model.ainvoke = AsyncMock(return_value=MagicMock(content='  "Trip to Japan"  '))
    service.llm_provider.get_chat_model.return_value = chat_model

    title = await service.generate_title("Plan a trip to Japan")

    assert title == "Trip to Japan"


@pytest.mark.asyncio
async def test_generate_title_falls_back_when_the_llm_raises():
    service = _service_with_mocks()
    chat_model = MagicMock()
    chat_model.ainvoke = AsyncMock(side_effect=RuntimeError("provider down"))
    service.llm_provider.get_chat_model.return_value = chat_model

    title = await service.generate_title("short prompt")

    assert title == "short prompt"


@pytest.mark.asyncio
async def test_generate_title_fallback_truncates_long_prompts():
    service = _service_with_mocks()
    chat_model = MagicMock()
    chat_model.ainvoke = AsyncMock(side_effect=RuntimeError("provider down"))
    service.llm_provider.get_chat_model.return_value = chat_model

    fallback_length = get_settings().title_fallback_length
    long_prompt = "x" * (fallback_length + 20)

    title = await service.generate_title(long_prompt)

    assert len(title) == fallback_length
    assert title.endswith("...")



@pytest.mark.asyncio
async def test_create_generates_a_title_when_none_is_given():
    service = _service_with_mocks()
    chat_model = MagicMock()
    chat_model.ainvoke = AsyncMock(return_value=MagicMock(content="Generated Title"))
    service.llm_provider.get_chat_model.return_value = chat_model
    service.repository.create.return_value = Conversation(title="Generated Title", model_type="openrouter/auto")

    payload = ConversationCreate(initial_prompt="hello", model_type="openrouter/auto")
    await service.create(uuid4(), payload)

    created_arg = service.repository.create.call_args.args[0]
    assert created_arg.title == "Generated Title"
