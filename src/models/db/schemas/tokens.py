from datetime import datetime
from pydantic import BaseModel, UUID4

class TokenBase(BaseModel):
    user_id: UUID4
    expires_at: datetime
    is_active: bool = True
    ip_address: str = None


class TokenCreate(TokenBase):
    pass


class TokenUpdate(TokenBase): 
    pass


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "Bearer"