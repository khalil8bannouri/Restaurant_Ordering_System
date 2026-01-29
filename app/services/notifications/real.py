"""
Real Notification Service

Production implementation using:
- Twilio for SMS
- SendGrid for Email
- Stripe for Payment Links

Author: Khalil Bannouri
Version: 3.0.0
"""

import logging
from typing import Optional

import stripe
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioException

from app.services.notifications.base import (
    BaseNotificationService,
    NotificationResult,
    PaymentLinkResult,
)
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RealNotificationService(BaseNotificationService):
    """Production notification service using Twilio, SendGrid, and Stripe."""
    
    def __init__(self):
        # Initialize Twilio
        if settings.twilio_account_sid and settings.twilio_auth_token:
            self.twilio_client = TwilioClient(
                settings.twilio_account_sid,
                settings.twilio_auth_token
            )
            self.twilio_from_number = settings.twilio_phone_number
        else:
            self.twilio_client = None
            logger.warning("Twilio credentials not configured")
        
        # Initialize SendGrid
        if settings.sendgrid_api_key:
            self.sendgrid_client = SendGridAPIClient(settings.sendgrid_api_key)
            self.sendgrid_from_email = settings.sendgrid_from_email
        else:
            self.sendgrid_client = None
            logger.warning("SendGrid credentials not configured")
        
        # Initialize Stripe
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
        
        logger.info("RealNotificationService initialized")
    
    @property
    def provider_name(self) -> str:
        return "real"
    
    async def send_sms(
        self,
        to_phone: str,
        message: str,
    ) -> NotificationResult:
        """Send SMS via Twilio."""
        if not self.twilio_client:
            return NotificationResult(
                success=False,
                error_message="Twilio not configured",
                provider="twilio"
            )
        
        try:
            result = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_from_number,
                to=to_phone
            )
            
            logger.info(f"SMS sent to {to_phone}: {result.sid}")
            
            return NotificationResult(
                success=True,
                message_id=result.sid,
                provider="twilio"
            )
            
        except TwilioException as e:
            logger.error(f"Twilio error: {e}")
            return NotificationResult(
                success=False,
                error_message=str(e),
                provider="twilio"
            )
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> NotificationResult:
        """Send email via SendGrid."""
        if not self.sendgrid_client:
            return NotificationResult(
                success=False,
                error_message="SendGrid not configured",
                provider="sendgrid"
            )
        
        try:
            message = Mail(
                from_email=self.sendgrid_from_email,
                to_emails=to_email,
                subject=subject,
                html_content=body_html,
                plain_text_content=body_text
            )
            
            response = self.sendgrid_client.send(message)
            
            logger.info(f"Email sent to {to_email}: {response.status_code}")
            
            return NotificationResult(
                success=response.status_code in [200, 201, 202],
                message_id=response.headers.get('X-Message-Id'),
                provider="sendgrid"
            )
            
        except Exception as e:
            logger.error(f"SendGrid error: {e}")
            return NotificationResult(
                success=False,
                error_message=str(e),
                provider="sendgrid"
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
        """Send order confirmation via SMS and email."""
        
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
        
        sms_result = await self.send_sms(customer_phone, message)
        
        email_result = None
        if customer_email:
            email_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h1 style="color: #ff4757;">Order Confirmed! 🍕</h1>
                <p>Hi {customer_name},</p>
                <p>Your order <strong>#{order_id}</strong> has been confirmed.</p>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <p><strong>{details}</strong></p>
                    <p>Total: <strong>${total_amount:.2f}</strong></p>
                </div>
                <p>Thank you for ordering from {settings.restaurant_name}!</p>
            </div>
            """
            email_result = await self.send_email(
                to_email=customer_email,
                subject=f"Order Confirmed #{order_id} - {settings.restaurant_name}",
                body_html=email_html,
                body_text=message
            )
        
        return NotificationResult(
            success=sms_result.success or (email_result and email_result.success),
            message_id=sms_result.message_id,
            provider="real"
        )
    
    async def send_payment_link(
        self,
        order_id: int,
        customer_email: Optional[str],
        customer_phone: str,
        amount: float,
        order_summary: str,
    ) -> PaymentLinkResult:
        """Generate Stripe checkout session and send payment link."""
        try:
            # Create Stripe Checkout Session
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': settings.stripe_currency,
                        'product_data': {
                            'name': f'Order #{order_id} - {settings.restaurant_name}',
                            'description': order_summary[:500],
                        },
                        'unit_amount': int(amount * 100),  # Stripe uses cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=f'{settings.app_base_url}/order/success?order_id={order_id}',
                cancel_url=f'{settings.app_base_url}/order/cancel?order_id={order_id}',
                metadata={
                    'order_id': str(order_id),
                },
                customer_email=customer_email,
            )
            
            payment_url = session.url
            
            # Send SMS with payment link
            message = (
                f"Complete your order #{order_id} (${amount:.2f}):\n"
                f"{payment_url}\n"
                f"- {settings.restaurant_name}"
            )
            await self.send_sms(customer_phone, message)
            
            # Send email if available
            if customer_email:
                email_html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h1 style="color: #ff4757;">Complete Your Order 🍕</h1>
                    <p>Order #{order_id}</p>
                    <p>Total: <strong>${amount:.2f}</strong></p>
                    <a href="{payment_url}" style="display: inline-block; background: #ff4757; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; margin: 20px 0;">
                        Pay Now
                    </a>
                    <p style="color: #666; font-size: 12px;">This link expires in 24 hours.</p>
                </div>
                """
                await self.send_email(
                    to_email=customer_email,
                    subject=f"Complete Your Payment - Order #{order_id}",
                    body_html=email_html
                )
            
            logger.info(f"Payment link created for order #{order_id}: {session.id}")
            
            return PaymentLinkResult(
                success=True,
                payment_url=payment_url,
                checkout_session_id=session.id
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return PaymentLinkResult(
                success=False,
                error_message=str(e)
            )
    
    async def health_check(self) -> bool:
        """Check all service connections."""
        try:
            # Check Stripe
            stripe.Account.retrieve()
            return True
        except:
            return False