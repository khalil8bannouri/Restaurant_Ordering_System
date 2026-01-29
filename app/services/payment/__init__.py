"""
Payment Service Factory

Provides a single entry point for obtaining a payment service instance.
The factory pattern allows the rest of the application to remain agnostic
about which implementation is being used.

Usage:
    from app.services.payment import get_payment_service
    
    # Returns MockPaymentService or StripePaymentService based on ENV_MODE
    payment_service = get_payment_service()
    
    result = await payment_service.process_payment(29.99)

Environment Switching:
    - ENV_MODE=development → MockPaymentService (no API calls)
    - ENV_MODE=staging → StripePaymentService (test keys)
    - ENV_MODE=production → StripePaymentService (live keys)

Author: Your Name
Version: 2.0.0
"""

import logging
from functools import lru_cache
from typing import Union

from app.core.config import get_settings
from app.services.payment.base import (
    BasePaymentService,
    PaymentResult,
    RefundResult,
)
from app.services.payment.mock import MockPaymentService
from app.services.payment.stripe import StripePaymentService

logger = logging.getLogger(__name__)

# Type alias for any payment service
PaymentService = Union[MockPaymentService, StripePaymentService]


@lru_cache()
def get_payment_service() -> BasePaymentService:
    """
    Get the configured payment service instance.
    
    Factory function that returns either MockPaymentService or 
    StripePaymentService based on the ENV_MODE configuration.
    
    The instance is cached (singleton pattern) to avoid creating
    multiple instances and to maintain consistent state.
    
    Returns:
        BasePaymentService: Configured payment service instance
        
    Raises:
        ValueError: If production mode but Stripe key not configured
        
    Example:
        >>> service = get_payment_service()
        >>> print(service.provider_name)
        'mock'  # In development mode
        
        >>> # Or in production:
        >>> print(service.provider_name)
        'stripe'
    """
    settings = get_settings()
    
    if settings.is_development:
        logger.info("Payment Service: Using MockPaymentService (development mode)")
        return MockPaymentService(
            failure_rate=0.10,  # 10% simulated failures
            min_latency=0.2,
            max_latency=0.8,
        )
    else:
        logger.info(
            f"Payment Service: Using StripePaymentService "
            f"({settings.env_mode.value} mode)"
        )
        return StripePaymentService()


def reset_payment_service() -> None:
    """
    Clear the cached payment service instance.
    
    Useful for testing or when configuration changes at runtime.
    The next call to get_payment_service() will create a new instance.
    """
    get_payment_service.cache_clear()
    logger.debug("Payment service cache cleared")


# Export commonly used types and functions
__all__ = [
    "get_payment_service",
    "reset_payment_service",
    "BasePaymentService",
    "PaymentResult",
    "RefundResult",
    "MockPaymentService",
    "StripePaymentService",
]