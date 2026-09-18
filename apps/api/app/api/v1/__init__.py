from fastapi import APIRouter

from app.api.v1 import assistant, auth, complaints, health

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health")
api_router.include_router(auth.router)
api_router.include_router(complaints.router)
api_router.include_router(assistant.router)

__all__ = ["api_router"]
