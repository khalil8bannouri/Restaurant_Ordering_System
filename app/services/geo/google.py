"""
Google Maps Geo Service Implementation

Production implementation using the Google Maps Geocoding API.
Used when ENV_MODE=production or ENV_MODE=staging.

Requirements:
    - GOOGLE_MAPS_API_KEY must be set in environment
    - Geocoding API must be enabled in Google Cloud Console

API Documentation:
    https://developers.google.com/maps/documentation/geocoding

Author: Your Name
Version: 2.0.0
"""

import logging
from datetime import datetime
from typing import Optional

import googlemaps
from googlemaps.exceptions import ApiError, Timeout, TransportError

from app.core.config import get_settings
from app.services.geo.base import (
    BaseGeoService,
    GeoValidationResult,
    DistanceResult,
)

logger = logging.getLogger(__name__)


class GoogleGeoService(BaseGeoService):
    """
    Production Google Maps geo service implementation.
    
    Integrates with Google Maps APIs for:
        - Address geocoding and validation
        - Distance calculations
        - Delivery zone verification
    
    Configuration:
        Requires GOOGLE_MAPS_API_KEY environment variable.
    
    Example:
        >>> service = GoogleGeoService()
        >>> result = await service.validate_address(
        ...     address="350 Fifth Avenue",
        ...     city="New York",
        ...     zip_code="10118"
        ... )
        >>> print(result.formatted_address)
        '350 5th Ave, New York, NY 10118, USA'
    """
    
    def __init__(self):
        """
        Initialize Google Maps client with API key.
        
        Raises:
            ValueError: If GOOGLE_MAPS_API_KEY is not configured
        """
        settings = get_settings()
        
        if not settings.google_maps_api_key:
            raise ValueError(
                "GOOGLE_MAPS_API_KEY is required for production mode. "
                "Set it in your .env file or environment variables."
            )
        
        self._client = googlemaps.Client(key=settings.google_maps_api_key)
        self._valid_zip_codes = settings.valid_zip_codes_list
        
        logger.info("GoogleGeoService initialized")
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "google"
    
    def _extract_address_components(
        self,
        components: list,
    ) -> dict[str, Optional[str]]:
        """
        Extract address components from Google's response.
        
        Args:
            components: List of address_components from Google API
            
        Returns:
            dict with zip_code, city, state, country
        """
        result = {
            "zip_code": None,
            "city": None,
            "state": None,
            "country": None,
        }
        
        for component in components:
            types = component.get("types", [])
            
            if "postal_code" in types:
                result["zip_code"] = component.get("short_name")
            elif "locality" in types:
                result["city"] = component.get("long_name")
            elif "administrative_area_level_1" in types:
                result["state"] = component.get("short_name")
            elif "country" in types:
                result["country"] = component.get("short_name")
        
        return result
    
    async def validate_address(
        self,
        address: str,
        city: str,
        zip_code: str,
        state: str = "NY",
        country: str = "US",
    ) -> GeoValidationResult:
        """
        Validate and geocode an address using Google Maps API.
        
        Makes a Geocoding API call to:
            1. Verify the address exists
            2. Get standardized formatting
            3. Retrieve GPS coordinates
            4. Check delivery zone eligibility
        """
        start_time = datetime.now()
        
        # Construct full address string
        full_address = f"{address}, {city}, {state} {zip_code}, {country}"
        
        logger.debug(f"Google: Geocoding address - {full_address}")
        
        try:
            # Call Google Geocoding API
            # Note: googlemaps library is synchronous, but lightweight
            geocode_result = self._client.geocode(full_address)
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            if not geocode_result:
                logger.warning(f"Google: Address not found - {full_address}")
                return GeoValidationResult(
                    is_valid=False,
                    error_message="Address not found. Please check and try again.",
                    error_code="address_not_found",
                    response_time_ms=elapsed_ms,
                )
            
            # Get the first (best) result
            result = geocode_result[0]
            
            # Extract location
            location = result.get("geometry", {}).get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")
            
            # Extract address components
            components = self._extract_address_components(
                result.get("address_components", [])
            )
            
            # Get formatted address
            formatted_address = result.get("formatted_address", full_address)
            
            # Check delivery zone
            result_zip = components.get("zip_code") or zip_code
            is_in_zone = result_zip in self._valid_zip_codes
            
            if not is_in_zone:
                logger.info(f"Google: Address outside delivery zone - {result_zip}")
                return GeoValidationResult(
                    is_valid=False,
                    formatted_address=formatted_address,
                    latitude=lat,
                    longitude=lng,
                    zip_code=result_zip,
                    city=components.get("city"),
                    state=components.get("state"),
                    country=components.get("country"),
                    is_in_delivery_zone=False,
                    error_message=f"Sorry, we don't deliver to zip code {result_zip}",
                    error_code="outside_delivery_zone",
                    response_time_ms=elapsed_ms,
                )
            
            logger.info(f"Google: Address validated - {formatted_address}")
            
            return GeoValidationResult(
                is_valid=True,
                formatted_address=formatted_address,
                latitude=lat,
                longitude=lng,
                zip_code=result_zip,
                city=components.get("city"),
                state=components.get("state"),
                country=components.get("country"),
                is_in_delivery_zone=True,
                response_time_ms=elapsed_ms,
            )
            
        except Timeout:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error("Google: API timeout")
            
            return GeoValidationResult(
                is_valid=False,
                error_message="Address validation timed out. Please try again.",
                error_code="timeout",
                response_time_ms=elapsed_ms,
            )
            
        except ApiError as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Google: API error - {e}")
            
            return GeoValidationResult(
                is_valid=False,
                error_message="Address validation service error",
                error_code="api_error",
                response_time_ms=elapsed_ms,
            )
            
        except TransportError as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Google: Transport error - {e}")
            
            return GeoValidationResult(
                is_valid=False,
                error_message="Unable to reach address validation service",
                error_code="transport_error",
                response_time_ms=elapsed_ms,
            )
            
        except Exception as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.exception(f"Google: Unexpected error - {e}")
            
            return GeoValidationResult(
                is_valid=False,
                error_message="An unexpected error occurred",
                error_code="unknown_error",
                response_time_ms=elapsed_ms,
            )
    
    async def calculate_distance(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
    ) -> DistanceResult:
        """
        Calculate distance using Google Distance Matrix API.
        """
        try:
            result = self._client.distance_matrix(
                origins=[(origin_lat, origin_lng)],
                destinations=[(dest_lat, dest_lng)],
                mode="driving",
                units="imperial",
            )
            
            element = result["rows"][0]["elements"][0]
            
            if element["status"] != "OK":
                return DistanceResult(
                    success=False,
                    error_message=f"Distance calculation failed: {element['status']}",
                )
            
            distance_meters = element["distance"]["value"]
            duration_seconds = element["duration"]["value"]
            
            distance_miles = round(distance_meters / 1609.34, 1)
            distance_km = round(distance_meters / 1000, 1)
            duration_minutes = int(duration_seconds / 60)
            
            return DistanceResult(
                success=True,
                distance_miles=distance_miles,
                distance_km=distance_km,
                duration_minutes=duration_minutes,
            )
            
        except Exception as e:
            logger.error(f"Google: Distance calculation error - {e}")
            
            return DistanceResult(
                success=False,
                error_message=str(e),
            )
    
    async def is_in_delivery_zone(
        self,
        zip_code: str,
    ) -> bool:
        """Check if zip code is in delivery zone."""
        return zip_code in self._valid_zip_codes
    
    async def health_check(self) -> bool:
        """
        Verify Google Maps API connectivity.
        
        Makes a simple geocode request to verify credentials and connectivity.
        """
        try:
            # Simple geocode to verify API is working
            result = self._client.geocode("New York, NY")
            
            if result:
                logger.debug("Google: Health check passed")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Google: Health check failed - {e}")
            return False