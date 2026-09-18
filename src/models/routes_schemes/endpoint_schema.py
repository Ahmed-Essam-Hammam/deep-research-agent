from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from uuid import uuid4

from pydantic import BaseModel, Field
from src.models.routes_schemes.http import TaskStatus

 
class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The research question or topic.")
 
 
class ResearchStartResponse(BaseModel):
    task_id: str
    status: TaskStatus
 
 
class ResearchStatusResponse(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    result: Optional[Any] = None
    error: Optional[str] = None