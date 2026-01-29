"""
Geo Service Abstract Base Class

Defines the interface contract for all geolocation service implementations.
Both MockGeoService and GoogleGeoService must implement these methods.

Use Cases:
    - Address validation before order placement
    - Delivery zone verification
    - Distance calculation for delivery fees
    - Address formatting and standardization

Author: Your Name
Version: 2.0.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class GeoValidationResult:
    """
    Standardized result from address validation.
    
    Attributes:
        is_valid: Whether the address is valid and deliverable
        formatted_address: Standardized address format
        latitude: GPS latitude coordinate
        longitude: GPS longitude coordinate
        zip_code: Extracted/validated zip code
        city: Extracted/validated city name
        state: Extracted/validated state
        country: Country code (e.g., "US")
        is_in_delivery_zone: Whether address is within delivery area
        distance_miles: Distance from restaurant (if calculated)
        error_message: Error description if validation failed
        error_code: Machine-readable error code
        response_time_ms: API response time
    """
    is_valid: bool
    formatted_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    is_in_delivery_zone: bool = False
    distance_miles: Optional[float] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    response_time_ms: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "formatted_address": self.formatted_address,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "zip_code": self.zip_code,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "is_in_delivery_zone": self.is_in_delivery_zone,
            "distance_miles": self.distance_miles,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "response_time_ms": self.response_time_ms,
        }


@dataclass
class DistanceResult:
    """
    Result from distance calculation between two points.
    
    Attributes:
        success: Whether calculation succeeded
        distance_miles: Distance in miles
        distance_km: Distance in kilometers
        duration_minutes: Estimated travel time
        error_message: Error if calculation failed
    """
    success: bool
    distance_miles: Optional[float] = None
    distance_km: Optional[float] = None
    duration_minutes: Optional[int] = None
    error_message: Optional[str] = None


class BaseGeoService(ABC):
    """
    Abstract base class for geolocation services.
    
    All geo service implementations (Mock, Google Maps, etc.) must
    inherit from this class and implement all abstract methods.
    
    Example:
        >>> service = get_geo_service()
        >>> result = await service.validate_address(
        ...     address="350 Fifth Avenue",
        ...     city="New York",
        ...     zip_code="10001"
        ... )
        >>> if result.is_valid and result.is_in_delivery_zone:
        ...     print("Address accepted!")
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Return the name of the geo provider.
        
        Returns:
            str: Provider name (e.g., "mock", "google")
        """
        pass
    
    @abstractmethod
    async def validate_address(
        self,
        address: str,
        city: str,
        zip_code: str,
        state: str = "NY",
        country: str = "US",
    ) -> GeoValidationResult:
        """
        Validate and geocode a delivery address.
        
        This method:
            1. Verifies the address exists
            2. Returns standardized formatting
            3. Provides GPS coordinates
            4. Checks if within delivery zone
        
        Args:
            address: Street address (e.g., "350 Fifth Avenue")
            city: City name (e.g., "New York")
            zip_code: Postal code (e.g., "10001")
            state: State abbreviation (default: "NY")
            country: Country code (default: "US")
            
        Returns:
            GeoValidationResult: Validation result with coordinates
        """
        pass
    
    @abstractmethod
    async def calculate_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> DistanceResult:
        """
        Calculate distance between two points.
        
        Used for:
            - Determining if address is within delivery radius
            - Calculating distance-based delivery fees
            - Estimating delivery time
        
        Args:
            origin_lat: Origin latitude (restaurant location)
            origin_lng: Origin longitude
            dest_lat: Destination latitude (customer)
            dest_lng: Destination longitude
            
        Returns:
            DistanceResult: Distance and duration information
        """
        pass
    
    @abstractmethod
    async def is_in_delivery_zone(
        self,
        zip_code: str,
    ) -> bool:
        """
        Check if a zip code is within the delivery zone.
        
        Simple zone check based on configured valid zip codes.
        
        Args:
            zip_code: Zip code to check
            
        Returns:
            bool: True if zip code is deliverable
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify connectivity to the geo service.
        
        Returns:
            bool: True if service is operational
        """
        pass