import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from src.config.settings import Settings, get_settings
from src.dependencies.database import async_session
from src.models.db.entities.messages import Message
from src.models.db.schemas.messages import MessageCreate, MessageOut
from src.providers.llm.base import LLMProvider
from src.providers.embedding.base import EmbeddingProvider
from src.repositories.conversations import ConversationRepository
from src.repositories.messages import MessageRepository



def formater(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def fuse_semantic_keyword(
    semantic_matches: list[tuple[Message, float]],
    keyword_matches: list[tuple[Message, float]],
    k: int = 60,
) -> tuple[Message, float] | None:

    scores: dict[int, float] = {}
    messages: dict[int, Message] = {}

    for candidates in (semantic_matches, keyword_matches):
        for rank, (msg, _score) in enumerate(candidates, start=1):
            scores[msg.id] = scores.get(msg.id, 0.0) + 1 / (k + rank)                       # As you may have a message appears in both lists, so you need to add it's score together 
            messages[msg.id] = msg

    if not scores:
        return None

    best_id = max(scores, key=scores.get)
    max_possible_score = 2 / (k + 1)                                                        # When a message ranked the first in both lists
    normalized_score = scores[best_id] / max_possible_score 

    # print(semantic_matches)
    # print(keyword_matches)
    # print(normalized_score)
    # print("##########################################################################")
    return messages[best_id], normalized_score


async def persist_message(
    conversation_id: int,
    prompt: str,
    response_content: str,
    is_success: bool,
    status_code: int,
    embedding: list[float] | None,
    error_message: str | None,
    queue: "asyncio.Queue[dict | None]",
):
    try:
        message = Message(
            conversation_id=conversation_id,
            prompt_content=prompt,
            response_content=response_content,
            is_success=is_success,
            status_code=status_code,
            input_query_embeddings=embedding, 
            ts_vector=func.to_tsvector("english", prompt),
        )

        async with async_session() as session:
            saved = await MessageRepository(session).create(message)
            await ConversationRepository(session).touch(conversation_id)

    except Exception as exc:
        print(f"Failed to save message for conversation {conversation_id}: {exc}")
        await queue.put(None)
        return
    
    done_payload = {"type": "done", "message": MessageOut.model_validate(saved).model_dump(mode="json")}
    if error_message:
        done_payload["error"] = error_message
    await queue.put(done_payload)
    await queue.put(None)


    
async def generate_and_save(
    llm_provider: LLMProvider,
    conversation_id: int,
    model_type: str,
    prompt: str,
    prompt_embedding: list[float] | None,
    queue: "asyncio.Queue[dict | None]",
):
    buffer: list[str] = []
    is_success = True
    error_message: str | None = None

    try:
        chat_model = llm_provider.get_chat_model(model=model_type, max_tokens=1000)
        async for chunk in chat_model.astream([HumanMessage(content=prompt)]):
            text = chunk.content or ""
            if not text:
                continue

            buffer.append(text)
            await queue.put({"type": "chunk", "content": text})

    except Exception as exc:  
        is_success = False
        error_message = str(exc)
 
    response_content = "".join(buffer) or (error_message or "No response was generated.")

    await persist_message(
        conversation_id=conversation_id,
        prompt=prompt,
        response_content=response_content,
        is_success=is_success,
        status_code=200 if is_success else 502,
        embedding=prompt_embedding,
        error_message=error_message,
        queue=queue,
    )


async def serve_cached_response(
    conversation_id: int,
    prompt: str,
    prompt_embedding: list[float],
    cached_response: str,
    queue: "asyncio.Queue[dict | None]",
):
    await queue.put({"type": "chunk", "content": cached_response})

    await persist_message(
        conversation_id=conversation_id,
        prompt=prompt,
        response_content=cached_response,
        is_success=True,
        status_code=200,
        embedding=prompt_embedding,
        error_message=None,
        queue=queue,
    )
    

async def stream_and_persist(
    worker: Callable[["asyncio.Queue[dict | None]"], Awaitable[None]],
) -> AsyncIterator[str]:

    queue: "asyncio.Queue[dict | None]" = asyncio.Queue()
    asyncio.create_task(worker(queue))

    while True:
        item = await queue.get()
        if item is None:
            break
        yield formater(item)

            

        
class MessageService:

    def __init__(
        self,
        session: AsyncSession,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
        settings: Settings | None = None,
    ) -> None:
        self.conversation_repository = ConversationRepository(session)
        self.repository = MessageRepository(session)
        self.llm_provider = llm_provider
        self.embedding_provider = embedding_provider
        self.settings = settings or get_settings()


    async def try_embed(self, prompt: str) -> list[float] | None:
        if not self.settings.cache_enabled:
            return None

        try:
            # print("############################################################")
            # print(await self.embedding_provider.embed_query(prompt))
            return await self.embedding_provider.embed_query(prompt)
        except Exception as exc:
            print(f"Embedding generation failed, skipping semantic cache: {exc}")
            return None


    async def check_cache(self, user_id: UUID, prompt: str, prompt_embedding: list[float] | None) -> str | None:

        if not self.settings.cache_enabled:
            return None

        semantic_matches: list[tuple[Message, float]] = []
        if prompt_embedding is not None:
            semantic_matches = await self.repository.top_semantic_matches(
                user_id=user_id,
                embedding=prompt_embedding,
                lookback=self.settings.cache_lookback,
                limit=self.settings.cache_top_n_per_method
            )

        keyword_matches = await self.repository.top_keyword_matches(
            user_id=user_id,
            query_text=prompt,
            lookback=self.settings.cache_lookback,
            limit=self.settings.cache_top_n_per_method,
        )

        fused = fuse_semantic_keyword(semantic_matches, keyword_matches, k=self.settings.cache_rrf_k)
        if fused is None:
            return None

        best_message, fused_score = fused
        if fused_score >= self.settings.cache_hit_score_threshold:
            return best_message.response_content
        return None
        

    async def list(self, conversation_id: int, user_id: UUID) -> list[Message] | None:
        conversation = await self.conversation_repository.get(conversation_id, user_id)
        if not conversation:
            return None
        return await self.repository.list(conversation_id)


    async def stream(self, conversation_id: int, user_id: UUID, message: MessageCreate) -> AsyncIterator[str] | None:
        conversation = await self.conversation_repository.get(conversation_id, user_id)
        if not conversation:
            return None

        prompt_embedding = await self.try_embed(message.prompt)
        cached_response = await self.check_cache(user_id, message.prompt, prompt_embedding)


        if cached_response is not None:
            return stream_and_persist(
                lambda queue: serve_cached_response(
                    conversation_id,
                    message.prompt,
                    prompt_embedding,
                    cached_response,
                    queue,
                )
            )

        return stream_and_persist(
            lambda queue: generate_and_save(
                self.llm_provider,
                conversation_id,
                conversation.model_type,
                message.prompt,
                prompt_embedding,
                queue,
            )
        )



