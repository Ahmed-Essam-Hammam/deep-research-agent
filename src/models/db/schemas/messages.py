from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

class MessageBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageCreate(MessageBase):
    prompt: str = Field(..., min_length=1)


class MessageUpdate(MessageBase):
    pass


class MessageOut(MessageBase):

    id: int
    conversation_id: int
    prompt_content: str
    response_content: str
    prompt_tokens: int | None = None
    response_tokens: int | None = None
    total_tokens: int | None = None
    is_success: bool | None = None
    status_code: int | None = None
    created_at: datetime
