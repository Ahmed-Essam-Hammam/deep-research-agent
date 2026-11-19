from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.routers.auth import CurrentUserDep
from src.dependencies.database import DBsessionDep
from src.dependencies.injection import get_default_llm_provider
from src.middleware.rate_limiter import limiter
from src.models.db.entities.conversations import Conversation
from src.models.db.schemas.conversations import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
)
from src.services.conversations import ConversationService


def get_conversation_service(session: DBsessionDep) -> ConversationService:
    return ConversationService(session, get_default_llm_provider())


ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]


router = APIRouter(prefix="/conversations", tags=["Conversations"])


async def get_conversation(
    conversation_id: int,
    current_user: CurrentUserDep,
    conversation_service: ConversationServiceDep,
) -> ConversationOut:
    conversation = await conversation_service.get(conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


GetConversationDep = Annotated[Conversation, Depends(get_conversation)]


@router.get("")
async def list_conversations_controller(
    current_user: CurrentUserDep,
    conversation_service: ConversationServiceDep,
    skip: int = 0,
    take: int = 100,
) -> list[ConversationOut]:
    conversations = await conversation_service.list(
        current_user.id, skip=skip, take=take
    )

    return [ConversationOut.model_validate(c) for c in conversations]


@router.get("/{conversation_id}")
async def get_conversation_controller(
    conversation: GetConversationDep,
) -> ConversationOut:

    return ConversationOut.model_validate(conversation)


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def create_conversation_controller(
    request: Request,
    conversation: ConversationCreate,
    current_user: CurrentUserDep,
    conversation_service: ConversationServiceDep,
) -> ConversationOut:
    new_conversation = await conversation_service.create(
        current_user.id, conversation=conversation
    )

    return ConversationOut.model_validate(new_conversation)


@router.put("/{conversation_id}", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def update_conversation_controller(
    request: Request,
    conversation: GetConversationDep,
    updated_conversation: ConversationUpdate,
    current_user: CurrentUserDep,
    conversation_service: ConversationServiceDep,
) -> ConversationOut:
    updated_conversation = await conversation_service.update(
        conversation_id=conversation.id,
        user_id=current_user.id,
        conversation=updated_conversation,
    )

    return ConversationOut.model_validate(updated_conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def delete_conversation_controller(
    request: Request,
    conversation: GetConversationDep,
    current_user: CurrentUserDep,
    conversation_service: ConversationServiceDep,
) -> None:
    await conversation_service.delete(conversation.id, current_user.id)
