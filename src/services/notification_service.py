import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.notification_model import Notification, NotificationType
from src.models.user_model import User
from src.utils.error_code import ErrorCode
from src.utils.exceptions import AppException


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/notifications/  — Fetch current user's in-app notifications
# ─────────────────────────────────────────────────────────────────────────────
async def get_notifications_service(
    db: AsyncSession,
    current_user: User,
    limit: int = 50,
) -> list[Notification]:
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/notifications/unread-count  — Unread count for badge
# ─────────────────────────────────────────────────────────────────────────────
async def get_unread_count_service(
    db: AsyncSession,
    current_user: User,
) -> int:
    from sqlalchemy import func as sa_func
    result = await db.execute(
        select(sa_func.count()).where(
            and_(
                Notification.user_id == current_user.id,
                Notification.is_read == False,  # noqa: E712
            )
        )
    )
    return result.scalar_one()


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/notifications/{id}/read  — Mark a single notification as read
# ─────────────────────────────────────────────────────────────────────────────
async def mark_notification_read_service(
    db: AsyncSession,
    notification_id: uuid.UUID,
    current_user: User,
) -> Notification:
    result = await db.execute(
        select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == current_user.id,
            )
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise AppException(ErrorCode.RESOURCE_NOT_FOUND, "Notification not found")

    notification.is_read = True
    await db.commit()
    await db.refresh(notification)
    return notification


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/notifications/read-all  — Mark all notifications as read
# ─────────────────────────────────────────────────────────────────────────────
async def mark_all_notifications_read_service(
    db: AsyncSession,
    current_user: User,
) -> dict:
    from sqlalchemy import update

    await db.execute(
        update(Notification)
        .where(
            and_(
                Notification.user_id == current_user.id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"success": True}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helper — create a single in-app notification
# ─────────────────────────────────────────────────────────────────────────────
async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: NotificationType,
    title: str,
    message: str,
    job_id: uuid.UUID | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        job_id=job_id,
    )
    db.add(notification)
    await db.flush()  # persist without committing (caller commits)
    return notification
