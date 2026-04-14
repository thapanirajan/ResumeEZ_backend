import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.db import get_db
from src.middlewares.auth_middleware import get_current_user
from src.models import User
from src.schema.notification_schema import NotificationResponse, UnreadCountResponse
from src.services.notification_service import (
    get_notifications_service,
    get_unread_count_service,
    mark_notification_read_service,
    mark_all_notifications_read_service,
)

notification_router = APIRouter(tags=["Notifications"])


# ─── GET /api/notifications/ ──────────────────────────────────────────────────
@notification_router.get(
    "/",
    response_model=List[NotificationResponse],
)
async def get_notifications(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await get_notifications_service(db, current_user, limit=limit)


# ─── GET /api/notifications/unread-count ─────────────────────────────────────
@notification_router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = await get_unread_count_service(db, current_user)
    return UnreadCountResponse(unread_count=count)


# ─── PATCH /api/notifications/read-all ───────────────────────────────────────
@notification_router.patch(
    "/read-all",
    status_code=status.HTTP_200_OK,
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await mark_all_notifications_read_service(db, current_user)


# ─── PATCH /api/notifications/{notification_id}/read ─────────────────────────
@notification_router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await mark_notification_read_service(db, notification_id, current_user)
