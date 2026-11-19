import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.config.settings import get_settings
from src.models.db.entities.conversations import Conversation
from src.models.db.entities.messages import Message
from src.models.db.schemas.messages import MessageCreate
from src.repositories.conversations import ConversationRepository
from src.repositories.messages import MessageRepository
from src.services.messages import (
    MessageService,
    fuse_semantic_keyword,
    generate_and_save,
    persist_message,
    serve_cached_response,
    stream_and_persist,
)


def _msg(id: int, response_content: str = "cached answer") -> Message:
    return Message(
        id=id, conversation_id=1, prompt_content="q", response_content=response_content
    )


def _vector(
    hot_index: int, dimensions: int = get_settings().embedding_dimensions
) -> list[float]:

    vec = [0.0] * dimensions
    vec[hot_index] = 1.0
    return vec


# ===== fuse_cache_candidates (pure) =====


def test_fuse_returns_none_when_both_lists_are_empty():
    assert fuse_semantic_keyword([], []) is None


def test_fuse_gives_max_score_to_a_message_ranked_first_in_both_lists():
    m1, m2 = _msg(1), _msg(2)
    best, score = fuse_semantic_keyword([(m1, 0.99), (m2, 0.5)], [(m1, 5.0), (m2, 1.0)])
    assert best.id == 1
    assert score == pytest.approx(1.0)


def test_fuse_caps_a_single_list_match_around_half():
    m1 = _msg(1)
    _, score = fuse_semantic_keyword([(m1, 0.99)], [])
    assert score == pytest.approx(0.5)


def test_fuse_prefers_agreement_across_both_lists_over_a_single_top_rank():
    m1, m2 = _msg(1), _msg(2)
    best, _ = fuse_semantic_keyword([(m1, 0.99), (m2, 0.9)], [(m2, 4.0), (m1, 1.0)])
    assert best.id == 1


def test_fuse_ignores_the_raw_score_values_only_rank_position_matters():
    m1, m2 = _msg(1), _msg(2)
    fused_a = fuse_semantic_keyword([(m1, 0.51), (m2, 0.50)], [])
    fused_b = fuse_semantic_keyword([(m1, 999.0), (m2, 1.0)], [])
    assert fused_a[0].id == fused_b[0].id == 1
    assert fused_a[1] == pytest.approx(fused_b[1])


# ===== MessageService (unit, mocked repos/providers) =====


def _service(settings_overrides: dict | None = None) -> MessageService:
    settings = get_settings().model_copy(update=settings_overrides or {})
    service = MessageService.__new__(
        MessageService
    )  # skip __init__'s real repositories
    service.repository = AsyncMock()
    service.conversation_repository = AsyncMock()
    service.llm_provider = MagicMock()
    service.embedding_provider = AsyncMock()
    service.settings = settings
    return service


@pytest.mark.asyncio
async def test_try_embed_returns_the_embedding_on_success():
    service = _service({"cache_enabled": True})
    service.embedding_provider.embed_query.return_value = [0.1, 0.2]

    result = await service.try_embed("hello")

    assert result == [0.1, 0.2]


@pytest.mark.asyncio
async def test_try_embed_returns_none_when_caching_is_disabled():
    service = _service({"cache_enabled": False})

    result = await service.try_embed("hello")

    assert result is None
    service.embedding_provider.embed_query.assert_not_called()


@pytest.mark.asyncio
async def test_try_embed_swallows_provider_errors_and_returns_none():
    service = _service({"cache_enabled": True})
    service.embedding_provider.embed_query.side_effect = RuntimeError("provider outage")

    assert await service.try_embed("hello") is None


@pytest.mark.asyncio
async def test_check_cache_returns_none_when_caching_is_disabled():
    service = _service({"cache_enabled": False})

    result = await service.check_cache(uuid4(), "hello", [0.1])

    assert result is None
    service.repository.top_semantic_matches.assert_not_called()
    service.repository.top_keyword_matches.assert_not_called()


@pytest.mark.asyncio
async def test_check_cache_returns_response_when_fused_score_clears_threshold():
    service = _service(
        {"cache_enabled": True, "cache_hit_score_threshold": 0.9, "cache_rrf_k": 60}
    )
    cached = _msg(1, response_content="the cached answer")
    # Ranked #1 in both lists -> fused score is 1.0, comfortably over 0.9.
    service.repository.top_semantic_matches.return_value = [(cached, 0.99)]
    service.repository.top_keyword_matches.return_value = [(cached, 5.0)]

    result = await service.check_cache(uuid4(), "hello", [0.1])

    assert result == "the cached answer"


@pytest.mark.asyncio
async def test_check_cache_returns_none_when_fused_score_is_below_threshold():
    service = _service(
        {"cache_enabled": True, "cache_hit_score_threshold": 0.9, "cache_rrf_k": 60}
    )
    cached = _msg(1)
    # Ranked #1 in only one list -> fused score ~0.5, below the 0.9 threshold.
    service.repository.top_semantic_matches.return_value = [(cached, 0.99)]
    service.repository.top_keyword_matches.return_value = []

    result = await service.check_cache(uuid4(), "hello", [0.1])

    assert result is None


@pytest.mark.asyncio
async def test_stream_falls_back_to_the_llm_when_there_is_no_cache_hit():
    service = _service({"cache_enabled": True})
    service.conversation_repository.get.return_value = Conversation(
        id=1, model_type="openrouter/auto"
    )
    service.embedding_provider.embed_query.return_value = [0.1]

    captured = {}

    async def _empty_gen():
        return
        yield

    def _capture_worker(worker):
        captured["worker"] = worker
        return _empty_gen()

    with (
        patch.object(MessageService, "check_cache", AsyncMock(return_value=None)),
        patch("src.services.messages.stream_and_persist", side_effect=_capture_worker),
        patch("src.services.messages.serve_cached_response") as fake_serve,
        patch("src.services.messages.generate_and_save") as fake_generate,
    ):
        await service.stream(1, uuid4(), MessageCreate(prompt="hi"))
        await captured["worker"](asyncio.Queue())

    fake_generate.assert_called_once()
    fake_serve.assert_not_called()


# ===== Streaming helpers (unit, mocked DB) =====


def _fake_async_session_cm(fake_session):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=fake_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


@pytest.mark.asyncio
async def test_stream_and_persist_yields_sse_formatted_frames():
    async def worker(queue):
        await queue.put({"type": "chunk", "content": "hi"})
        await queue.put(None)

    frames = [frame async for frame in stream_and_persist(worker)]

    assert len(frames) == 1
    assert frames[0].startswith("data: ")
    assert frames[0].endswith("\n\n")
    assert json.loads(frames[0][len("data: ") :].strip()) == {
        "type": "chunk",
        "content": "hi",
    }


@pytest.mark.asyncio
async def test_persist_message_saves_and_emits_a_done_event():
    fake_saved = Message(
        id=1,
        conversation_id=1,
        prompt_content="hi",
        response_content="hello",
        is_success=True,
        status_code=200,
        created_at=datetime.now(timezone.utc),
    )
    fake_message_repo = AsyncMock()
    fake_message_repo.create.return_value = fake_saved
    fake_conversation_repo = AsyncMock()

    queue = asyncio.Queue()

    with (
        patch(
            "src.services.messages.async_session", _fake_async_session_cm(MagicMock())
        ),
        patch(
            "src.services.messages.MessageRepository", return_value=fake_message_repo
        ),
        patch(
            "src.services.messages.ConversationRepository",
            return_value=fake_conversation_repo,
        ),
    ):
        await persist_message(
            conversation_id=1,
            prompt="hi",
            response_content="hello",
            is_success=True,
            status_code=200,
            embedding=None,
            error_message=None,
            queue=queue,
        )

    fake_conversation_repo.touch.assert_awaited_once_with(1)
    done_event = await queue.get()
    assert done_event["type"] == "done"
    assert done_event["message"]["response_content"] == "hello"
    assert await queue.get() is None


@pytest.mark.asyncio
async def test_generate_and_save_streams_chunks_then_persists():
    async def fake_astream(_messages):
        for piece in ["Hel", "lo"]:
            yield MagicMock(content=piece)

    chat_model = MagicMock()
    chat_model.astream = fake_astream
    llm_provider = MagicMock()
    llm_provider.get_chat_model.return_value = chat_model

    fake_saved = Message(
        id=1,
        conversation_id=1,
        prompt_content="hi",
        response_content="Hello",
        is_success=True,
        created_at=datetime.now(timezone.utc),
    )
    fake_message_repo = AsyncMock()
    fake_message_repo.create.return_value = fake_saved

    queue = asyncio.Queue()

    with (
        patch(
            "src.services.messages.async_session", _fake_async_session_cm(MagicMock())
        ),
        patch(
            "src.services.messages.MessageRepository", return_value=fake_message_repo
        ),
        patch("src.services.messages.ConversationRepository", return_value=AsyncMock()),
    ):
        await generate_and_save(llm_provider, 1, "openrouter/auto", "hi", None, queue)

    events = []
    while True:
        item = await queue.get()
        if item is None:
            break
        events.append(item)

    chunk_events = [e for e in events if e["type"] == "chunk"]
    assert [e["content"] for e in chunk_events] == ["Hel", "lo"]
    assert events[-1]["type"] == "done"

    saved_message_arg = fake_message_repo.create.call_args.args[0]
    assert saved_message_arg.response_content == "Hello"
    assert saved_message_arg.is_success is True


@pytest.mark.asyncio
async def test_generate_and_save_marks_the_message_failed_when_the_llm_errors():
    chat_model = MagicMock()

    async def failing_astream(_messages):
        raise RuntimeError("model unavailable")
        yield  # pragma: no cover - makes this an async generator

    chat_model.astream = failing_astream
    llm_provider = MagicMock()
    llm_provider.get_chat_model.return_value = chat_model

    fake_message_repo = AsyncMock()
    fake_message_repo.create.return_value = Message(
        id=1,
        conversation_id=1,
        prompt_content="hi",
        response_content="model unavailable",
        is_success=False,
        created_at=datetime.now(timezone.utc),
    )

    queue = asyncio.Queue()

    with (
        patch(
            "src.services.messages.async_session", _fake_async_session_cm(MagicMock())
        ),
        patch(
            "src.services.messages.MessageRepository", return_value=fake_message_repo
        ),
        patch("src.services.messages.ConversationRepository", return_value=AsyncMock()),
    ):
        await generate_and_save(llm_provider, 1, "openrouter/auto", "hi", None, queue)

    saved_message_arg = fake_message_repo.create.call_args.args[0]
    assert saved_message_arg.is_success is False
    assert saved_message_arg.status_code == 502


@pytest.mark.asyncio
async def test_serve_cached_response_emits_the_cached_text_as_one_chunk():
    fake_message_repo = AsyncMock()
    fake_message_repo.create.return_value = Message(
        id=1,
        conversation_id=1,
        prompt_content="hi",
        response_content="cached",
        is_success=True,
        created_at=datetime.now(timezone.utc),
    )
    queue = asyncio.Queue()

    with (
        patch(
            "src.services.messages.async_session", _fake_async_session_cm(MagicMock())
        ),
        patch(
            "src.services.messages.MessageRepository", return_value=fake_message_repo
        ),
        patch("src.services.messages.ConversationRepository", return_value=AsyncMock()),
    ):
        await serve_cached_response(1, "hi", [0.1], "cached", queue)

    first_event = await queue.get()
    assert first_event == {"type": "chunk", "content": "cached"}
    done_event = await queue.get()
    assert done_event["type"] == "done"


# ===== MessageRepository (integration) =====


async def _make_conversation(db_session, user_id=None) -> Conversation:
    repo = ConversationRepository(db_session)
    return await repo.create(
        Conversation(
            user_id=user_id or uuid4(), title="t", model_type="openrouter/auto"
        )
    )


async def _make_message(
    db_session, conversation_id, prompt_content, embedding=None
) -> Message:
    repo = MessageRepository(db_session)
    return await repo.create(
        Message(
            conversation_id=conversation_id,
            prompt_content=prompt_content,
            response_content=f"response to: {prompt_content}",
            input_query_embeddings=embedding,
        )
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repository_list_returns_messages_oldest_first(db_session):
    conv = await _make_conversation(db_session)
    await _make_message(db_session, conv.id, "first")
    await _make_message(db_session, conv.id, "second")

    messages = await MessageRepository(db_session).list(conv.id)

    assert [m.prompt_content for m in messages] == ["first", "second"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_top_semantic_matches_ranks_by_cosine_similarity(db_session):
    user_id = uuid4()
    conv = await _make_conversation(db_session, user_id)
    close = await _make_message(
        db_session, conv.id, "close match", embedding=_vector(0)
    )
    await _make_message(db_session, conv.id, "unrelated", embedding=_vector(1))

    results = await MessageRepository(db_session).top_semantic_matches(
        user_id=user_id, embedding=_vector(0), lookback=50, limit=3
    )

    assert results[0][0].id == close.id
    assert results[0][1] == pytest.approx(1.0, abs=1e-4)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_top_semantic_matches_only_considers_the_given_users_messages(db_session):
    other_user_conv = await _make_conversation(db_session)
    await _make_message(
        db_session, other_user_conv.id, "someone else's message", embedding=_vector(0)
    )

    results = await MessageRepository(db_session).top_semantic_matches(
        user_id=uuid4(), embedding=_vector(0), lookback=50, limit=3
    )

    assert results == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_top_keyword_matches_finds_shared_terms(db_session):
    user_id = uuid4()
    conv = await _make_conversation(db_session, user_id)
    match = await _make_message(db_session, conv.id, "how do I bake sourdough bread")
    await _make_message(db_session, conv.id, "what is the capital of France")

    results = await MessageRepository(db_session).top_keyword_matches(
        user_id=user_id, query_text="sourdough bread recipe", lookback=50, limit=3
    )

    assert any(msg.id == match.id for msg, _score in results)
