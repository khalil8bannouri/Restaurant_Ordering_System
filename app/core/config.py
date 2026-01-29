"""
Application Configuration Module

Centralizes all configuration using environment variables with Pydantic Settings.
Supports two modes:
    - DEVELOPMENT: Uses mock services (no API keys needed)
    - PRODUCTION: Uses real APIs (Stripe, Google Maps, Vapi)

The ENV_MODE variable controls which services are instantiated throughout
the application, enabling seamless switching between local testing and
production deployment.

Usage:
    from app.core.config import get_settings
    
    settings = get_settings()
    if settings.is_development:
        # Use mock services
    else:
        # Use real APIs

Author: Your Name
Version: 2.0.0
"""

import os
import logging
import sys
from enum import Enum
from typing import Optional
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvironmentMode(str, Enum):
    """
    Application environment modes.
    
    Attributes:
        DEVELOPMENT: Local testing with mock services
        PRODUCTION: Live environment with real API integrations
        STAGING: Pre-production testing with real APIs but test keys
    """
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    STAGING = "staging"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings can be overridden via environment variables or .env file.
    Sensitive values (API keys) should NEVER be committed to version control.
    
    Attributes:
        env_mode: Current environment (development/production/staging)
        debug: Enable verbose logging and error details
        
        # API Configuration
        api_host: Host to bind the API server
        api_port: Port for the API server
        
        # Database
        database_url: PostgreSQL connection string
        
        # Redis
        redis_url: Redis connection string for Celery
        
        # External Services (Required in production)
        stripe_secret_key: Stripe API secret key
        stripe_webhook_secret: Stripe webhook signing secret
        google_maps_api_key: Google Maps Geocoding API key
        vapi_api_key: Vapi.ai API key
        vapi_webhook_secret: Vapi webhook verification secret
        
        # Business Configuration
        restaurant_name: Display name for the restaurant
        delivery_radius_miles: Maximum delivery distance
        tax_rate: Local tax rate (decimal)
        delivery_fee: Standard delivery charge
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # ==========================================================================
    # ENVIRONMENT
    # ==========================================================================
    
    env_mode: EnvironmentMode = Field(
        default=EnvironmentMode.DEVELOPMENT,
        description="Application environment mode"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode with verbose logging"
    )
    
    # ==========================================================================
    # APPLICATION
    # ==========================================================================
    
    app_name: str = Field(
        default="AI Restaurant Ordering System",
        description="Application display name"
    )
    app_version: str = Field(
        default="2.0.0",
        description="Application version"
    )
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    api_port: int = Field(
        default=8001,
        description="API server port"
    )
    
    # ==========================================================================
    # DATABASE
    # ==========================================================================
    
    database_url: str = Field(
        default="postgresql+psycopg://restaurant_admin:secretpassword123@localhost:5433/restaurant_orders",
        description="PostgreSQL connection URL"
    )
    
    # ==========================================================================
    # REDIS / CELERY
    # ==========================================================================
    
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    # ==========================================================================
    # STRIPE PAYMENT GATEWAY
    # ==========================================================================
    
    stripe_secret_key: Optional[str] = Field(
        default=None,
        description="Stripe API secret key (sk_live_... or sk_test_...)"
    )
    stripe_webhook_secret: Optional[str] = Field(
        default=None,
        description="Stripe webhook signing secret (whsec_...)"
    )
    stripe_currency: str = Field(
        default="usd",
        description="Default currency for payments"
    )
    
    # ==========================================================================
    # GOOGLE MAPS
    # ==========================================================================
    
    google_maps_api_key: Optional[str] = Field(
        default=None,
        description="Google Maps Geocoding API key"
    )
    
    # ==========================================================================
    # VAPI.AI VOICE
    # ==========================================================================
    
    vapi_api_key: Optional[str] = Field(
        default=None,
        description="Vapi.ai API key"
    )
    vapi_webhook_secret: Optional[str] = Field(
        default=None,
        description="Vapi webhook verification secret"
    )
    vapi_assistant_id: Optional[str] = Field(
        default=None,
        description="Vapi assistant ID for outbound calls"
    )
    
        # ==========================================================================
    # TWILIO (SMS)
    # ==========================================================================
    
    twilio_account_sid: Optional[str] = Field(
        default=None,
        description="Twilio Account SID"
    )
    twilio_auth_token: Optional[str] = Field(
        default=None,
        description="Twilio Auth Token"
    )
    twilio_phone_number: Optional[str] = Field(
        default=None,
        description="Twilio phone number for sending SMS"
    )
    
    # ==========================================================================
    # SENDGRID (EMAIL)
    # ==========================================================================
    
    sendgrid_api_key: Optional[str] = Field(
        default=None,
        description="SendGrid API Key"
    )
    sendgrid_from_email: str = Field(
        default="orders@restaurant.com",
        description="From email address for SendGrid"
    )
    
    # ==========================================================================
    # APPLICATION URLs
    # ==========================================================================
    
    app_base_url: str = Field(
        default="http://localhost:8001",
        description="Base URL for the application"
    )
    
    # ==========================================================================
    # HUMAN TRANSFER
    # ==========================================================================
    
    human_transfer_number: Optional[str] = Field(
        default=None,
        description="Phone number to transfer calls to human agents"
    )
    # ==========================================================================
    # BUSINESS CONFIGURATION
    # ==========================================================================
    
    restaurant_name: str = Field(
        default="AI Pizza Palace",
        description="Restaurant display name"
    )
    restaurant_phone: str = Field(
        default="+1-555-123-4567",
        description="Restaurant contact number"
    )
    delivery_radius_miles: float = Field(
        default=5.0,
        description="Maximum delivery distance in miles"
    )
    tax_rate: float = Field(
        default=0.08875,
        description="Tax rate as decimal (NYC = 8.875%)"
    )
    delivery_fee: float = Field(
        default=5.99,
        description="Standard delivery fee"
    )
    estimated_delivery_minutes: int = Field(
        default=40,
        description="Estimated delivery time"
    )
    
    # ==========================================================================
    # FILE STORAGE
    # ==========================================================================
    
    data_directory: str = Field(
        default="data",
        description="Directory for data files"
    )
    excel_filename: str = Field(
        default="orders.xlsx",
        description="Excel export filename"
    )
    excel_lock_timeout: int = Field(
        default=30,
        description="Seconds to wait for file lock"
    )
    
    # ==========================================================================
    # VALID DELIVERY ZONES
    # ==========================================================================
    
    valid_zip_codes: str = Field(
        default="10001,10002,10003,10004,10005,10006,10007,10008,10009,10010,10011,10012,10013,10014,10016,10017,10018,10019,10020,10021",
        description="Comma-separated list of valid delivery zip codes"
    )
    
    # ==========================================================================
    # VALIDATORS
    # ==========================================================================
    
    @field_validator("env_mode", mode="before")
    @classmethod
    def validate_env_mode(cls, v: str) -> EnvironmentMode:
        """Convert string to EnvironmentMode enum."""
        if isinstance(v, EnvironmentMode):
            return v
        try:
            return EnvironmentMode(v.lower())
        except ValueError:
            valid = [e.value for e in EnvironmentMode]
            raise ValueError(f"Invalid env_mode. Must be one of: {valid}")
    
    # ==========================================================================
    # COMPUTED PROPERTIES
    # ==========================================================================
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.env_mode == EnvironmentMode.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.env_mode == EnvironmentMode.PRODUCTION
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging mode."""
        return self.env_mode == EnvironmentMode.STAGING
    
    @property
    def use_real_services(self) -> bool:
        """Check if real external services should be used."""
        return self.env_mode in (EnvironmentMode.PRODUCTION, EnvironmentMode.STAGING)
    
    @property
    def valid_zip_codes_list(self) -> list[str]:
        """Get valid zip codes as a list."""
        return [z.strip() for z in self.valid_zip_codes.split(",")]
    
    # ==========================================================================
    # VALIDATION METHODS
    # ==========================================================================
    
    def validate_production_config(self) -> list[str]:
        """
        Validate that all required production settings are configured.
        
        Returns:
            List of missing configuration keys (empty if all present)
        """
        missing = []
        
        if self.use_real_services:
            if not self.stripe_secret_key:
                missing.append("STRIPE_SECRET_KEY")
            if not self.google_maps_api_key:
                missing.append("GOOGLE_MAPS_API_KEY")
            if not self.vapi_api_key:
                missing.append("VAPI_API_KEY")
        
        return missing


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses LRU cache to ensure settings are loaded only once,
    improving performance and ensuring consistency across
    the application lifecycle.
    
    Returns:
        Settings: Configured application settings
        
    Example:
        >>> settings = get_settings()
        >>> print(settings.env_mode)
        EnvironmentMode.DEVELOPMENT
    """
    return Settings()


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure application-wide logging.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Configured root logger
    """
    settings = get_settings()
    
    # Set level based on debug mode
    if settings.debug:
        level = logging.DEBUG
    
    # Configure format
    log_format = "%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Configure root logger
    logging.basicConfig(
        level=level,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    return logging.getLogger("app")


def get_logger(name: str) -> logging.Logger:
    """
    Get a named logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)