"""
Notification Service Abstract Base Class

Defines interface for sending SMS and Email notifications.
Supports both Mock (development) and Real (production) implementations.

Author: Khalil Bannouri
Version: 3.0.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class NotificationResult:
    """Result from sending a notification."""
    success: bool
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    provider: str = "unknown"


@dataclass 
class PaymentLinkResult:
    """Result from generating a payment link."""
    success: bool
    payment_url: Optional[str] = None
    checkout_session_id: Optional[str] = None
    error_message: Optional[str] = None


class BaseNotificationService(ABC):
    """Abstract base class for notification services."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name."""
        pass
    
    @abstractmethod
    async def send_sms(
        self,
        to_phone: str,
        message: str,
    ) -> NotificationResult:
        """Send an SMS message."""
        pass
    
    @abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> NotificationResult:
        """Send an email."""
        pass
    
    @abstractmethod
    async def send_order_confirmation(
        self,
        order_id: int,
        customer_name: str,
        customer_email: Optional[str],
        customer_phone: str,
        order_summary: str,
        total_amount: float,
        order_type: str,
        pickup_time: Optional[str] = None,
        delivery_address: Optional[str] = None,
    ) -> NotificationResult:
        """Send order confirmation via email and/or SMS."""
        pass
    
    @abstractmethod
    async def send_payment_link(
        self,
        order_id: int,
        customer_email: Optional[str],
        customer_phone: str,
        amount: float,
        order_summary: str,
    ) -> PaymentLinkResult:
        """Generate and send payment link."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check service connectivity."""
        pass