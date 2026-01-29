"""
Mock Notification Service

Simulates SMS and Email sending for development.
No actual messages are sent - just logged.

Author: Khalil Bannouri
Version: 3.0.0
"""

import asyncio
import random
import uuid
import logging
from typing import Optional

from app.services.notifications.base import (
    BaseNotificationService,
    NotificationResult,
    PaymentLinkResult,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MockNotificationService(BaseNotificationService):
    """Mock notification service for development."""
    
    def __init__(self, failure_rate: float = 0.05):
        self.failure_rate = failure_rate
        logger.info(f"MockNotificationService initialized (failure_rate={failure_rate:.0%})")
    
    @property
    def provider_name(self) -> str:
        return "mock"
    
    async def _simulate_latency(self) -> None:
        """Simulate network latency."""
        await asyncio.sleep(random.uniform(0.1, 0.3))
    
    def _should_fail(self) -> bool:
        return random.random() < self.failure_rate
    
    async def send_sms(
        self,
        to_phone: str,
        message: str,
    ) -> NotificationResult:
        """Simulate sending SMS."""
        await self._simulate_latency()
        
        if self._should_fail():
            logger.warning(f"Mock SMS failed (simulated) to {to_phone}")
            return NotificationResult(
                success=False,
                error_message="Simulated SMS failure",
                provider="mock"
            )
        
        message_id = f"sms_mock_{uuid.uuid4().hex[:12]}"
        logger.info(f"Mock SMS sent to {to_phone}: {message[:50]}... (ID: {message_id})")
        
        return NotificationResult(
            success=True,
            message_id=message_id,
            provider="mock"
        )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> NotificationResult:
        """Simulate sending email."""
        await self._simulate_latency()
        
        if self._should_fail():
            logger.warning(f"Mock email failed (simulated) to {to_email}")
            return NotificationResult(
                success=False,
                error_message="Simulated email failure",
                provider="mock"
            )
        
        message_id = f"email_mock_{uuid.uuid4().hex[:12]}"
        logger.info(f"Mock email sent to {to_email}: {subject} (ID: {message_id})")
        
        return NotificationResult(
            success=True,
            message_id=message_id,
            provider="mock"
        )
    
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
        """Send order confirmation."""
        
        # Build confirmation message
        if order_type == "pickup":
            details = f"Pickup Time: {pickup_time}"
        else:
            details = f"Delivery to: {delivery_address}"
        
        message = (
            f"Hi {customer_name}! Your order #{order_id} has been confirmed.\n"
            f"{details}\n"
            f"Total: ${total_amount:.2f}\n"
            f"Thank you for ordering from {settings.restaurant_name}!"
        )
        
        # Send SMS
        sms_result = await self.send_sms(customer_phone, message)
        
        # Send email if available
        email_result = None
        if customer_email:
            email_result = await self.send_email(
                to_email=customer_email,
                subject=f"Order Confirmation #{order_id} - {settings.restaurant_name}",
                body_html=f"<h1>Order Confirmed!</h1><p>{message}</p>",
                body_text=message
            )
        
        return NotificationResult(
            success=sms_result.success or (email_result and email_result.success),
            message_id=sms_result.message_id,
            provider="mock"
        )
    
    async def send_payment_link(
        self,
        order_id: int,
        customer_email: Optional[str],
        customer_phone: str,
        amount: float,
        order_summary: str,
    ) -> PaymentLinkResult:
        """Generate and send mock payment link."""
        await self._simulate_latency()
        
        # Generate mock payment URL
        checkout_id = f"cs_mock_{uuid.uuid4().hex[:24]}"
        payment_url = f"https://checkout.stripe.com/mock/{checkout_id}"
        
        # Send SMS with payment link
        message = (
            f"Complete your order #{order_id} (${amount:.2f}):\n"
            f"{payment_url}\n"
            f"- {settings.restaurant_name}"
        )
        await self.send_sms(customer_phone, message)
        
        # Send email if available
        if customer_email:
            await self.send_email(
                to_email=customer_email,
                subject=f"Complete Your Payment - Order #{order_id}",
                body_html=f'<h1>Complete Your Order</h1><p><a href="{payment_url}">Click here to pay ${amount:.2f}</a></p>',
            )
        
        logger.info(f"Mock payment link generated for order #{order_id}: {payment_url}")
        
        return PaymentLinkResult(
            success=True,
            payment_url=payment_url,
            checkout_session_id=checkout_id
        )
    
    async def health_check(self) -> bool:
        """Mock always returns healthy."""
        return True