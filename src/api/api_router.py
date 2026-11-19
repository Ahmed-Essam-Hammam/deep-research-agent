from fastapi import APIRouter

from src.api.routers.auth import router as auth_router
from src.api.routers.conversations import router as conversations_router
from src.api.routers.health_router import router as health_router
from src.api.routers.messages import router as messages_router
from src.api.routers.research_router import router as research_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(research_router)
api_router.include_router(auth_router)
api_router.include_router(conversations_router)
api_router.include_router(messages_router)
