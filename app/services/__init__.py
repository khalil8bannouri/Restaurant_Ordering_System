"""
                        Services Module

Contains all business logic services with the hybrid architecture pattern.
Each service has Mock (development) and Real (production) implementations.

Services:
    - payment: Stripe payment processing
    - geo: Google Maps address validation
    - voice: Vapi.ai voice webhook handling
    - excel_manager: Thread-safe Excel operations
"""

from app.services.excel_manager import ExcelManager

__all__ = ["ExcelManager"]