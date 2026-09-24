from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    announcements,
    assistant,
    auth,
    complaints,
    documents,
    fees,
    health,
    leave,
    mess,
    notifications,
    reports,
    rooms,
    students,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health")
api_router.include_router(auth.router)
api_router.include_router(students.router)
api_router.include_router(rooms.router)
api_router.include_router(complaints.router)
api_router.include_router(leave.router)
api_router.include_router(fees.router)
api_router.include_router(mess.router)
api_router.include_router(announcements.router)
api_router.include_router(documents.router)
api_router.include_router(assistant.router)
api_router.include_router(analytics.router)
api_router.include_router(notifications.router)
api_router.include_router(reports.router)

__all__ = ["api_router"]
