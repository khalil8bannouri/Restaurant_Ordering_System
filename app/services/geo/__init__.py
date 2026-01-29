"""
Geo Service Factory

Provides a single entry point for obtaining a geo service instance.
Automatically selects Mock or Google Maps based on ENV_MODE configuration.

Usage:
    from app.services.geo import get_geo_service
    
    geo_service = get_geo_service()
    result = await geo_service.validate_address(
        address="350 Fifth Avenue",
        city="New York",
        zip_code="10001"
    )

Author: Your Name
Version: 2.0.0
"""

import logging
from functools import lru_cache
from typing import Union

from app.core.config import get_settings
from app.services.geo.base import (
    BaseGeoService,
    GeoValidationResult,
    DistanceResult,
)
from app.services.geo.mock import MockGeoService
from app.services.geo.google import GoogleGeoService

logger = logging.getLogger(__name__)

# Type alias for any geo service
GeoService = Union[MockGeoService, GoogleGeoService]


@lru_cache()
def get_geo_service() -> BaseGeoService:
    """
    Get the configured geo service instance.
    
    Factory function that returns either MockGeoService or 
    GoogleGeoService based on the ENV_MODE configuration.
    
    Returns:
        BaseGeoService: Configured geo service instance
        
    Raises:
        ValueError: If production mode but Google API key not configured
    """
    settings = get_settings()
    
    if settings.is_development:
        logger.info("Geo Service: Using MockGeoService (development mode)")
        return MockGeoService(
            failure_rate=0.05,  # 5% simulated failures
            min_latency=0.1,
            max_latency=0.5,
        )
    else:
        logger.info(
            f"Geo Service: Using GoogleGeoService "
            f"({settings.env_mode.value} mode)"
        )
        return GoogleGeoService()


def reset_geo_service() -> None:
    """
    Clear the cached geo service instance.
    
    Useful for testing or when configuration changes at runtime.
    """
    get_geo_service.cache_clear()
    logger.debug("Geo service cache cleared")


# Export commonly used types and functions
__all__ = [
    "get_geo_service",
    "reset_geo_service",
    "BaseGeoService",
    "GeoValidationResult",
    "DistanceResult",
    "MockGeoService",
    "GoogleGeoService",
]