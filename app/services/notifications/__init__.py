"""
Notification Service Factory

Returns Mock or Real notification service based on ENV_MODE.

Author: Khalil Bannouri
Version: 3.0.0
"""

import logging
from functools import lru_cache

from app.core.config import get_settings
from app.services.notifications.base import (
    BaseNotificationService,
    NotificationResult,
    PaymentLinkResult,
)
from app.services.notifications.mock import MockNotificationService
from app.services.notifications.real import RealNotificationService

logger = logging.getLogger(__name__)


@lru_cache()
def get_notification_service() -> BaseNotificationService:
    """Get the configured notification service."""
    settings = get_settings()
    
    if settings.is_development:
        logger.info("Notification Service: Using MockNotificationService (development mode)")
        return MockNotificationService(failure_rate=0.05)
    else:
        logger.info(f"Notification Service: Using RealNotificationService ({settings.env_mode.value} mode)")
        return RealNotificationService()


def reset_notification_service() -> None:
    """Clear the cached service instance."""
    get_notification_service.cache_clear()


__all__ = [
    "get_notification_service",
    "reset_notification_service",
    "BaseNotificationService",
    "NotificationResult",
    "PaymentLinkResult",
]