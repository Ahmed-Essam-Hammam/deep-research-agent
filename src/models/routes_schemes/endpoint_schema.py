from datetime import datetime
from typing import Any

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
    result: Any | None = None
    error: str | None = None
