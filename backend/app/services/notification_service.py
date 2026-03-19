"""
Push notification service.

Phase 1: Firebase integration is stubbed. Actual FCM sending is no-op unless
FIREBASE_CREDENTIALS_PATH is configured.
"""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.db.device_token import DeviceToken
from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

_firebase_app = None


def _init_firebase() -> bool:
    """Initialise Firebase app if credentials are configured."""
    global _firebase_app
    if _firebase_app is not None:
        return True
    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.debug("No Firebase credentials configured — notifications are stubbed.")
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials

        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase app initialised.")
        return True
    except Exception as exc:
        logger.error("Failed to initialise Firebase: %s", exc)
        return False


async def send_signal_notification(
    db: AsyncSession,
    signal_id: str,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """
    Send a push notification to all active device tokens.

    Returns a summary dict with sent/failed counts.
    """
    result = await db.execute(
        select(DeviceToken).where(DeviceToken.active == True)  # noqa: E712
    )
    tokens = result.scalars().all()

    if not tokens:
        logger.info("No active device tokens — nothing to send.")
        return {"sent": 0, "failed": 0, "skipped": 0}

    firebase_ready = _init_firebase()
    sent = failed = skipped = 0

    for dt in tokens:
        if not firebase_ready:
            # Stub — log instead of sending
            logger.info(
                "[STUB] Would send FCM to token %s…: %s — %s",
                dt.token[:12],
                title,
                body,
            )
            skipped += 1
            continue

        try:
            from firebase_admin import messaging

            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                token=dt.token,
                apns=messaging.APNSConfig(
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(sound="default")
                    )
                ),
            )
            messaging.send(message)
            sent += 1
        except Exception as exc:
            logger.warning("Failed to send notification to token %s: %s", dt.token[:12], exc)
            # Deactivate stale tokens
            if "registration-token-not-registered" in str(exc).lower():
                dt.active = False
            failed += 1

    logger.info("Notifications: sent=%d failed=%d skipped=%d", sent, failed, skipped)
    return {"sent": sent, "failed": failed, "skipped": skipped}


async def register_device_token(db: AsyncSession, token: str, platform: str = "ios") -> DeviceToken:
    """Register or reactivate a device token."""
    result = await db.execute(select(DeviceToken).where(DeviceToken.token == token))
    existing = result.scalar_one_or_none()

    if existing:
        existing.active = True
        from datetime import datetime
        existing.last_seen = datetime.utcnow()
        return existing

    dt = DeviceToken(token=token, platform=platform, active=True)
    db.add(dt)
    await db.flush()
    return dt
