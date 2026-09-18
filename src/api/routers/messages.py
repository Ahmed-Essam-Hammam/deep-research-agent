from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse

from src.api.routers.auth import CurrentUserDep
from src.services.messages import MessageService   
from src.models.db.schemas.messages import MessageCreate, MessageOut
from src.dependencies.database import DBsessionDep
from src.dependencies.injection import get_default_llm_provider, get_default_embedding_provider
from src.api.routers.auth import get_current_user
from src.middleware.rate_limiter import limiter

def get_message_service(session: DBsessionDep) -> MessageService:
    return MessageService(session, get_default_llm_provider(), get_default_embedding_provider())

MessageServiceDep = Annotated[MessageService, Depends(get_message_service)]

router = APIRouter(prefix="/conversations/{conversation_id}/messages", tags=["Messages"])


@router.get("")
async def list_messages_controller(conversation_id: int, current_user: CurrentUserDep, message_service: MessageServiceDep) -> list[MessageOut]:
    messages = await message_service.list(conversation_id, current_user.id)
    if messages is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return [MessageOut.model_validate(m) for m in messages]


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_message_controller(request: Request ,conversation_id: int, message: MessageCreate, current_user: CurrentUserDep, message_service: MessageServiceDep) -> StreamingResponse:
    stream = await message_service.stream(conversation_id, current_user.id, message)
    if stream is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
