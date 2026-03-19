"""Firebase initialisation helper (Phase 1 stub)."""

from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_firebase_app():
    """
    Return the Firebase app instance if credentials are configured.

    Phase 1: Always returns None — FCM sending is stubbed in notification_service.
    """
    from app.config import settings

    if not settings.FIREBASE_CREDENTIALS_PATH:
        return None

    try:
        import firebase_admin

        if firebase_admin._DEFAULT_APP_NAME in firebase_admin._apps:
            return firebase_admin.get_app()

        from firebase_admin import credentials

        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        return firebase_admin.initialize_app(cred)
    except Exception as exc:
        logger.error("Firebase initialisation failed: %s", exc)
        return None
