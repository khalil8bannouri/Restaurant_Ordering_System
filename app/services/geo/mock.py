"""
Mock Geo Service Implementation

Simulates Google Maps Geocoding API without making real API calls.
Used in development mode (ENV_MODE=development) for local testing.

Behavior:
    - Validates against configured list of valid zip codes
    - Generates realistic NYC coordinates
    - Simulates network latency (100-500ms)
    - 5% random API failure rate for testing error handling

Author: Your Name
Version: 2.0.0
"""

import asyncio
import random
import logging
from datetime import datetime
from typing import Optional

from app.core.config import get_settings
from app.services.geo.base import (
    BaseGeoService,
    GeoValidationResult,
    DistanceResult,
)

logger = logging.getLogger(__name__)


class MockGeoService(BaseGeoService):
    """
    Mock implementation of the geo service.
    
    Simulates address validation and geocoding for development and testing.
    Uses configured valid zip codes to determine delivery zones.
    
    Attributes:
        failure_rate: Probability of simulated API failure (0.0-1.0)
        min_latency: Minimum response time in seconds
        max_latency: Maximum response time in seconds
        valid_zip_codes: List of zip codes in delivery zone
        
    Example:
        >>> service = MockGeoService()
        >>> result = await service.validate_address(
        ...     address="123 Main St",
        ...     city="New York",
        ...     zip_code="10001"
        ... )
        >>> print(result.is_valid)
        True
    """
    
    # NYC center coordinates for generating realistic mock data
    NYC_CENTER_LAT = 40.7128
    NYC_CENTER_LNG = -74.0060
    
    def __init__(
        self,
        failure_rate: float = 0.05,
        min_latency: float = 0.1,
        max_latency: float = 0.5,
    ):
        """
        Initialize the mock geo service.
        
        Args:
            failure_rate: Probability of API failure (default: 5%)
            min_latency: Minimum response time in seconds
            max_latency: Maximum response time in seconds
        """
        self.failure_rate = failure_rate
        self.min_latency = min_latency
        self.max_latency = max_latency
        
        settings = get_settings()
        self.valid_zip_codes = settings.valid_zip_codes_list
        
        logger.info(
            f"MockGeoService initialized "
            f"(failure_rate={failure_rate:.0%}, "
            f"delivery_zones={len(self.valid_zip_codes)} zip codes)"
        )
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "mock"
    
    async def _simulate_latency(self) -> float:
        """
        Simulate network latency.
        
        Returns:
            float: Latency in milliseconds
        """
        latency = random.uniform(self.min_latency, self.max_latency)
        await asyncio.sleep(latency)
        return latency * 1000
    
    def _should_fail(self) -> bool:
        """Determine if this request should simulate a failure."""
        return random.random() < self.failure_rate
    
    def _generate_coordinates(self) -> tuple[float, float]:
        """
        Generate realistic NYC coordinates.
        
        Returns:
            tuple: (latitude, longitude) within NYC area
        """
        lat = self.NYC_CENTER_LAT + random.uniform(-0.05, 0.05)
        lng = self.NYC_CENTER_LNG + random.uniform(-0.05, 0.05)
        return round(lat, 6), round(lng, 6)
    
    async def validate_address(
        self,
        address: str,
        city: str,
        zip_code: str,
        state: str = "NY",
        country: str = "US",
    ) -> GeoValidationResult:
        """
        Validate an address (mock implementation).
        
        Validation rules:
            1. Address must not be empty
            2. Zip code must be in valid delivery zones
            3. Random 5% failure rate to simulate API errors
        """
        start_time = datetime.now()
        
        logger.debug(f"Mock: Validating address - {address}, {city}, {zip_code}")
        
        # Simulate network latency
        latency_ms = await self._simulate_latency()
        
        # Simulate random API failure
        if self._should_fail():
            logger.debug("Mock: Simulated API failure")
            return GeoValidationResult(
                is_valid=False,
                error_message="Geocoding service temporarily unavailable",
                error_code="service_unavailable",
                response_time_ms=latency_ms,
            )
        
        # Validate address is not empty
        if not address or not address.strip():
            return GeoValidationResult(
                is_valid=False,
                error_message="Address is required",
                error_code="invalid_address",
                response_time_ms=latency_ms,
            )
        
        # Check if zip code is in delivery zone
        is_in_zone = zip_code in self.valid_zip_codes
        
        if not is_in_zone:
            logger.debug(f"Mock: Zip code {zip_code} not in delivery zone")
            return GeoValidationResult(
                is_valid=False,
                is_in_delivery_zone=False,
                error_message=f"Sorry, we don't deliver to zip code {zip_code}",
                error_code="outside_delivery_zone",
                response_time_ms=latency_ms,
            )
        
        # Generate mock coordinates
        lat, lng = self._generate_coordinates()
        
        # Format the address nicely
        formatted_address = f"{address.title()}, {city.title()}, {state.upper()} {zip_code}"
        
        logger.info(f"Mock: Address validated - {formatted_address}")
        
        return GeoValidationResult(
            is_valid=True,
            formatted_address=formatted_address,
            latitude=lat,
            longitude=lng,
            zip_code=zip_code,
            city=city.title(),
            state=state.upper(),
            country=country,
            is_in_delivery_zone=True,
            distance_miles=round(random.uniform(0.5, 4.5), 1),
            response_time_ms=latency_ms,
        )
    
    async def calculate_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> DistanceResult:
        """
        Calculate distance between two points (mock).
        
        Uses a simple approximation formula for mock purposes.
        """
        await self._simulate_latency()
        
        # Simple distance approximation (good enough for mock)
        # 1 degree latitude ≈ 69 miles
        # 1 degree longitude ≈ 54.6 miles (at NYC latitude)
        lat_diff = abs(dest_lat - origin_lat) * 69
        lng_diff = abs(dest_lng - origin_lng) * 54.6
        
        distance_miles = round((lat_diff**2 + lng_diff**2)**0.5, 1)
        distance_km = round(distance_miles * 1.60934, 1)
        
        # Estimate duration (assume 15 mph average in city)
        duration_minutes = int(distance_miles / 15 * 60)
        
        return DistanceResult(
            success=True,
            distance_miles=distance_miles,
            distance_km=distance_km,
            duration_minutes=max(duration_minutes, 5),  # Minimum 5 minutes
        )
    
    async def is_in_delivery_zone(
        self,
        zip_code: str,
    ) -> bool:
        """Check if zip code is in delivery zone."""
        return zip_code in self.valid_zip_codes
    
    async def health_check(self) -> bool:
        """Mock health check always returns True."""
        logger.debug("Mock: Geo health check passed")
        return True