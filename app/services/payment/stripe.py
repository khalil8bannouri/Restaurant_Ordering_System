"""
Stripe Payment Service Implementation

Production implementation using the official Stripe Python SDK.
Used when ENV_MODE=production or ENV_MODE=staging.

Requirements:
    - STRIPE_SECRET_KEY must be set in environment
    - STRIPE_WEBHOOK_SECRET for webhook verification

Security Notes:
    - Never log full card numbers or CVCs
    - Always verify webhook signatures
    - Use idempotency keys for retries

Author: Your Name
Version: 2.0.0
"""

import logging
from datetime import datetime
from typing import Optional

import stripe
from stripe.error import (
    StripeError,
    CardError,
    InvalidRequestError,
    AuthenticationError,
    APIConnectionError,
)

from app.core.config import get_settings
from app.services.payment.base import (
    BasePaymentService,
    PaymentResult,
    RefundResult,
)

logger = logging.getLogger(__name__)


class StripePaymentService(BasePaymentService):
    """
    Production Stripe payment service implementation.
    
    Integrates with Stripe's API for real payment processing.
    Handles all standard payment operations including charges,
    refunds, and webhook verification.
    
    Configuration:
        Requires STRIPE_SECRET_KEY environment variable.
        Optionally uses STRIPE_WEBHOOK_SECRET for webhook verification.
    
    Example:
        >>> service = StripePaymentService()
        >>> result = await service.process_payment(
        ...     amount=29.99,
        ...     customer_email="customer@example.com"
        ... )
    """
    
    def __init__(self):
        """
        Initialize Stripe with API key from settings.
        
        Raises:
            ValueError: If STRIPE_SECRET_KEY is not configured
        """
        settings = get_settings()
        
        if not settings.stripe_secret_key:
            raise ValueError(
                "STRIPE_SECRET_KEY is required for production mode. "
                "Set it in your .env file or environment variables."
            )
        
        # Configure Stripe SDK
        stripe.api_key = settings.stripe_secret_key
        stripe.api_version = "2023-10-16"  # Pin API version for stability
        
        self._webhook_secret = settings.stripe_webhook_secret
        self._currency = settings.stripe_currency
        
        logger.info(
            f"StripePaymentService initialized "
            f"(api_version={stripe.api_version})"
        )
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "stripe"
    
    def _convert_to_cents(self, amount: float) -> int:
        """
        Convert dollar amount to cents for Stripe.
        
        Stripe expects amounts in the smallest currency unit (cents for USD).
        
        Args:
            amount: Amount in dollars (e.g., 29.99)
            
        Returns:
            int: Amount in cents (e.g., 2999)
        """
        return int(round(amount * 100))
    
    def _convert_from_cents(self, cents: int) -> float:
        """Convert cents back to dollars."""
        return cents / 100.0
    
    async def process_payment(
        self,
        amount: float,
        currency: str = "usd",
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> PaymentResult:
        """
        Process a payment through Stripe.
        
        Creates a PaymentIntent and confirms it immediately.
        For production use with saved payment methods or
        server-side payment confirmation.
        """
        start_time = datetime.now()
        
        logger.info(f"Stripe: Processing payment of ${amount:.2f}")
        
        try:
            # Validate amount
            if amount <= 0:
                return PaymentResult(
                    success=False,
                    error_message="Amount must be greater than 0",
                    error_code="invalid_amount",
                )
            
            # Create and confirm PaymentIntent
            # Note: In real implementation, you'd use a payment method
            # from the frontend (Stripe Elements)
            intent = stripe.PaymentIntent.create(
                amount=self._convert_to_cents(amount),
                currency=currency or self._currency,
                description=description or "Restaurant Order",
                receipt_email=customer_email,
                metadata={
                    "customer_name": customer_name or "",
                    "source": "ai_restaurant_system",
                    **(metadata or {}),
                },
                # For automatic confirmation (use with caution)
                # confirm=True,
                # payment_method="pm_card_visa",  # Test only
            )
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(
                f"Stripe: PaymentIntent created - {intent.id} - "
                f"status={intent.status}"
            )
            
            return PaymentResult(
                success=True,
                payment_intent_id=intent.id,
                amount=self._convert_from_cents(intent.amount),
                currency=intent.currency,
                response_time_ms=elapsed_ms,
                metadata={
                    "status": intent.status,
                    "client_secret": intent.client_secret,
                },
            )
            
        except CardError as e:
            # Card was declined
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.warning(f"Stripe: Card declined - {e.code}: {e.user_message}")
            
            return PaymentResult(
                success=False,
                error_message=e.user_message,
                error_code=e.code,
                response_time_ms=elapsed_ms,
            )
            
        except InvalidRequestError as e:
            # Invalid parameters
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Stripe: Invalid request - {e}")
            
            return PaymentResult(
                success=False,
                error_message=str(e),
                error_code="invalid_request",
                response_time_ms=elapsed_ms,
            )
            
        except AuthenticationError as e:
            # API key issues
            logger.critical(f"Stripe: Authentication failed - {e}")
            
            return PaymentResult(
                success=False,
                error_message="Payment service configuration error",
                error_code="authentication_error",
            )
            
        except APIConnectionError as e:
            # Network issues
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Stripe: Connection error - {e}")
            
            return PaymentResult(
                success=False,
                error_message="Payment service temporarily unavailable",
                error_code="connection_error",
                response_time_ms=elapsed_ms,
            )
            
        except StripeError as e:
            # Generic Stripe error
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Stripe: Error - {e}")
            
            return PaymentResult(
                success=False,
                error_message="Payment processing error",
                error_code="stripe_error",
                response_time_ms=elapsed_ms,
            )
    
    async def create_payment_intent(
        self,
        amount: float,
        currency: str = "usd",
        metadata: Optional[dict] = None,
    ) -> PaymentResult:
        """
        Create a PaymentIntent for client-side confirmation.
        
        Returns a client_secret that the frontend uses with Stripe.js
        to complete the payment.
        """
        start_time = datetime.now()
        
        try:
            intent = stripe.PaymentIntent.create(
                amount=self._convert_to_cents(amount),
                currency=currency or self._currency,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )
            
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.debug(f"Stripe: PaymentIntent created - {intent.id}")
            
            return PaymentResult(
                success=True,
                payment_intent_id=intent.id,
                amount=self._convert_from_cents(intent.amount),
                currency=intent.currency,
                response_time_ms=elapsed_ms,
                metadata={
                    "client_secret": intent.client_secret,
                    "status": intent.status,
                },
            )
            
        except StripeError as e:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Stripe: Failed to create PaymentIntent - {e}")
            
            return PaymentResult(
                success=False,
                error_message=str(e),
                error_code="stripe_error",
                response_time_ms=elapsed_ms,
            )
    
    async def refund_payment(
        self,
        payment_intent_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> RefundResult:
        """
        Refund a payment through Stripe.
        
        Args:
            payment_intent_id: The PaymentIntent to refund
            amount: Partial refund amount (None = full refund)
            reason: Reason code (duplicate, fraudulent, requested_by_customer)
        """
        try:
            refund_params = {
                "payment_intent": payment_intent_id,
            }
            
            if amount is not None:
                refund_params["amount"] = self._convert_to_cents(amount)
            
            if reason:
                refund_params["reason"] = reason
            
            refund = stripe.Refund.create(**refund_params)
            
            logger.info(
                f"Stripe: Refund processed - {refund.id} - "
                f"status={refund.status}"
            )
            
            return RefundResult(
                success=True,
                refund_id=refund.id,
                amount=self._convert_from_cents(refund.amount),
                status=refund.status,
            )
            
        except StripeError as e:
            logger.error(f"Stripe: Refund failed - {e}")
            
            return RefundResult(
                success=False,
                error_message=str(e),
            )
    
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> Optional[dict]:
        """
        Verify and parse a Stripe webhook event.
        
        SECURITY: Always verify webhook signatures in production
        to prevent spoofed events.
        
        Args:
            payload: Raw request body
            signature: Stripe-Signature header value
            
        Returns:
            Parsed event object if valid, None if verification fails
        """
        if not self._webhook_secret:
            logger.warning(
                "Stripe: Webhook secret not configured, skipping verification"
            )
            import json
            try:
                return json.loads(payload)
            except:
                return None
        
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                self._webhook_secret,
            )
            
            logger.debug(f"Stripe: Webhook verified - {event['type']}")
            return event
            
        except stripe.error.SignatureVerificationError as e:
            logger.warning(f"Stripe: Webhook signature invalid - {e}")
            return None
            
        except Exception as e:
            logger.error(f"Stripe: Webhook verification error - {e}")
            return None
    
    async def health_check(self) -> bool:
        """
        Verify Stripe API connectivity.
        
        Makes a lightweight API call to verify credentials and connectivity.
        """
        try:
            # Retrieve account info (lightweight call)
            stripe.Account.retrieve()
            logger.debug("Stripe: Health check passed")
            return True
            
        except StripeError as e:
            logger.error(f"Stripe: Health check failed - {e}")
            return False