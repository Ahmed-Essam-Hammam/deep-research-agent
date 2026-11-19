import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from src.dependencies.injection import get_llm_provider_by_name
from src.models.routes_schemes.endpoint_schema import (
    ResearchRequest,
    ResearchStartResponse,
    ResearchStatusResponse,
)
from src.models.routes_schemes.http import _TASKS, TaskStatus, _TaskRecord
from src.services.agents.graphs.full_graph import agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


async def _run_research_graph(task_id: str, query: str) -> None:
    """Invoke the compiled LangGraph agent and store its result."""
    record = _TASKS[task_id]
    record.status = TaskStatus.RUNNING
    record.updated_at = datetime.now(UTC)

    try:
        final_state = await agent.ainvoke({"messages": [HumanMessage(content=query)]})
        record.status = TaskStatus.COMPLETED
        record.result = final_state
    except Exception as exc:
        logger.exception("Research task %s failed", task_id)
        record.status = TaskStatus.FAILED
        record.error = str(exc)
    finally:
        record.updated_at = datetime.now(UTC)


# ===== Endpoints =====


@router.post(
    "", response_model=ResearchStartResponse, status_code=status.HTTP_202_ACCEPTED
)
async def start_research(
    request: ResearchRequest, background_tasks: BackgroundTasks
) -> ResearchStartResponse:
    """Kick off a research run in the background and return immediately with a task_id."""
    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    _TASKS[task_id] = _TaskRecord(
        task_id=task_id,
        status=TaskStatus.PENDING,
        created_at=now,
        updated_at=now,
    )

    background_tasks.add_task(_run_research_graph, task_id, request.query)

    return ResearchStartResponse(task_id=task_id, status=TaskStatus.PENDING)


@router.get("/{task_id}", response_model=ResearchStatusResponse)
async def get_research_status(task_id: str) -> ResearchStatusResponse:
    """Poll for the status (and, once done, the result) of a research task."""
    record = _TASKS.get(task_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    return ResearchStatusResponse(
        task_id=record.task_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        result=record.result,
        error=record.error,
    )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def clear_research_task(task_id: str) -> None:
    """Optional cleanup endpoint to drop a completed/failed task from memory."""
    if task_id not in _TASKS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    del _TASKS[task_id]


#################################################################################3


class LLMTestRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str | None = Field(
        default=None,
        description="OpenRouter model id, Falls back to the provider's default model if omitted.",
    )


class LLMTestResponse(BaseModel):
    model: str
    response: str


@router.post("/test-llm")
async def test_llm_controller(request: LLMTestRequest) -> LLMTestResponse:

    llm_provider = get_llm_provider_by_name("openrouter")
    chat_model = llm_provider.get_chat_model(model=request.model, max_tokens=1000)
    try:
        response = await chat_model.ainvoke([HumanMessage(content=request.prompt)])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenRouter call failed: {exc}",
        ) from exc
    return LLMTestResponse(
        model=request.model or llm_provider.default_model,
        response=str(response.content),
    )
