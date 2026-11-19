from datetime import datetime

from pydantic import UUID4, BaseModel, ConfigDict, Field


class ConversationBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    title: str | None = None
    model_type: str


class ConversationCreate(ConversationBase):
    initial_prompt: str = Field(
        ...,
        min_length=1,
        description="The user's first message; used to auto-generate the title",
    )


class ConversationUpdate(ConversationBase):
    pass


class ConversationOut(ConversationBase):
    id: int
    user_id: UUID4
    created_at: datetime
    updated_at: datetime
