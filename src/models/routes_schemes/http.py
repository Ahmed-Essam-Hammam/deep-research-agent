from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
from uuid import uuid4

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"


 
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
 
 
class _TaskRecord(BaseModel):
    task_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    result: Optional[Any] = None
    error: Optional[str] = None
 
 
_TASKS: dict[str, _TaskRecord] = {}