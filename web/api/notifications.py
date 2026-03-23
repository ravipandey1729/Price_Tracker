"""
Notifications API Router

Provides notification center APIs and a lightweight SSE stream.
"""

import asyncio
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from database.connection import get_session
from database.models import NotificationRecord, User
from web.auth import get_current_user, get_optional_current_user, get_user_from_token

router = APIRouter()


@router.get("/")
async def list_notifications(
    limit: int = 30,
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
):
    """List notifications for the authenticated user."""
    with get_session() as session:
        query = session.query(NotificationRecord).filter(
            NotificationRecord.user_id == current_user.id
        )

        if unread_only:
            query = query.filter(NotificationRecord.is_read.is_(False))

        items = query.order_by(NotificationRecord.created_at.desc()).limit(limit).all()

        return {
            "total": len(items),
            "notifications": [
                {
                    "id": n.id,
                    "title": n.title,
                    "message": n.message,
                    "type": n.notification_type.value,
                    "is_read": n.is_read,
                    "product_id": n.product_id,
                    "created_at": n.created_at.isoformat(),
                }
                for n in items
            ],
        }


@router.get("/unread-count")
async def unread_count(current_user: User = Depends(get_current_user)):
    with get_session() as session:
        query = session.query(NotificationRecord).filter(
            NotificationRecord.is_read.is_(False),
            NotificationRecord.user_id == current_user.id,
        )

        return {"unread": query.count()}


@router.post("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
):
    with get_session() as session:
        query = session.query(NotificationRecord).filter(
            NotificationRecord.id == notification_id,
            NotificationRecord.user_id == current_user.id,
        )

        notification = query.first()
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        notification.is_read = True
        notification.read_at = datetime.utcnow()
        session.commit()

        return {"status": "ok", "id": notification_id}


@router.get("/stream")
async def stream_notifications(
    token: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Simple SSE stream that pushes unread count updates every 5 seconds."""

    stream_user = current_user
    if stream_user is None and token:
        stream_user = get_user_from_token(token)

    if stream_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    async def event_generator() -> AsyncGenerator[str, None]:
        last_count = None
        while True:
            with get_session() as session:
                query = session.query(NotificationRecord).filter(NotificationRecord.is_read.is_(False))
                query = query.filter(NotificationRecord.user_id == stream_user.id)

                count = query.count()

            if count != last_count:
                yield f"event: unread_count\ndata: {count}\n\n"
                last_count = count

            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
