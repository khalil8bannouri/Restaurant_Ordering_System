"""
Mock Payment Service Implementation

Simulates Stripe-like payment processing without making real API calls.
Used in development mode (ENV_MODE=development) to:
    - Test the complete order flow locally
    - Run load tests without incurring costs
    - Develop without internet connectivity
    - Create portfolio demonstrations

Behavior:
    - Simulates realistic response times (200-800ms)
    - Randomly fails ~10% of payments (simulates real-world declines)
    - Generates Stripe-like IDs (pi_xxx, ch_xxx)
    - Supports all interface methods

Author: Your Name
Version: 2.0.0
"""

import asyncio
import random
import uuid
import logging
from datetime import datetime
from typing import Optional

from app.services.payment.base import (
    BasePaymentService,
    PaymentResult,
    RefundResult,
)

logger = logging.getLogger(__name__)


class MockPaymentService(BasePaymentService):
    """
    Mock implementation of the payment service.
    
    Simulates payment processing with configurable behavior for testing
    different scenarios (success, failure, timeout, etc.).
    
    Attributes:
        failure_rate: Probability of simulated payment failure (0.0-1.0)
        min_latency: Minimum simulated response time in seconds
        max_latency: Maximum simulated response time in seconds
        
    Example:
        >>> service = MockPaymentService(failure_rate=0.1)
        >>> result = await service.process_payment(29.99)
        >>> print(result.success)  # True ~90% of the time
    """
    
    # Simulated failure reasons (mimics real Stripe decline codes)
    DECLINE_REASONS = [
        ("card_declined", "Your card was declined."),
        ("insufficient_funds", "Your card has insufficient funds."),
        ("expired_card", "Your card has expired."),
        ("incorrect_cvc", "Your card's security code is incorrect."),
        ("processing_error", "An error occurred while processing your card."),
    ]
    
    def __init__(
        self,
        failure_rate: float = 0.10,
        min_latency: float = 0.2,
        max_latency: float = 0.8,
    ):
        """
        Initialize the mock payment service.
        
        Args:
            failure_rate: Probability of payment failure (default: 10%)
            min_latency: Minimum response time in seconds
            max_latency: Maximum response time in seconds
        """
        self.failure_rate = failure_rate
        self.min_latency = min_latency
        self.max_latency = max_latency
        
        logger.info(
            f"MockPaymentService initialized "
            f"(failure_rate={failure_rate:.0%}, "
            f"latency={min_latency}-{max_latency}s)"
        )
    
    @property
    def provider_name(self) -> str:
        """Return the provider name."""
        return "mock"
    
    def _generate_payment_intent_id(self) -> str:
        """Generate a Stripe-like payment intent ID."""
        return f"pi_mock_{uuid.uuid4().hex[:24]}"
    
    def _generate_charge_id(self) -> str:
        """Generate a Stripe-like charge ID."""
        return f"ch_mock_{uuid.uuid4().hex[:24]}"
    
    def _generate_refund_id(self) -> str:
        """Generate a Stripe-like refund ID."""
        return f"re_mock_{uuid.uuid4().hex[:24]}"
    
    async def _simulate_latency(self) -> float:
        """
        Simulate network latency.
        
        Returns:
            float: Actual latency in milliseconds
        """
        latency = random.uniform(self.min_latency, self.max_latency)
        await asyncio.sleep(latency)
        return latency * 1000  # Convert to milliseconds
    
    def _should_fail(self) -> bool:
        """Determine if this request should simulate a failure."""
        return random.random() < self.failure_rate
    
    def _get_random_decline(self) -> tuple[str, str]:
        """Get a random decline reason."""
        return random.choice(self.DECLINE_REASONS)
    
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
        Simulate processing a payment.
        
        Behavior:
            - Validates amount is positive
            - Simulates network latency
            - Randomly fails based on failure_rate
            - Returns Stripe-like response structure
        """
        start_time = datetime.now()
        
        logger.debug(f"Mock: Processing payment of ${amount:.2f} {currency.upper()}")
        
        # Validate amount
        if amount <= 0:
            return PaymentResult(
                success=False,
                error_message="Amount must be greater than 0",
                error_code="invalid_amount",
                response_time_ms=0,
            )
        
        # Simulate network latency
        latency_ms = await self._simulate_latency()
        
        # Simulate random failure
        if self._should_fail():
            error_code, error_message = self._get_random_decline()
            logger.debug(f"Mock: Payment declined - {error_code}")
            
            return PaymentResult(
                success=False,
                amount=amount,
                currency=currency,
                error_message=error_message,
                error_code=error_code,
                response_time_ms=latency_ms,
            )
        
        # Simulate successful payment
        payment_intent_id = self._generate_payment_intent_id()
        charge_id = self._generate_charge_id()
        
        logger.info(
            f"Mock: Payment successful - {payment_intent_id} - ${amount:.2f}"
        )
        
        return PaymentResult(
            success=True,
            payment_intent_id=payment_intent_id,
            charge_id=charge_id,
            amount=amount,
            currency=currency,
            response_time_ms=latency_ms,
            metadata={
                "customer_email": customer_email,
                "customer_name": customer_name,
                "description": description,
                "mock": True,
                **(metadata or {}),
            },
        )
    
    async def create_payment_intent(
        self,
        amount: float,
        currency: str = "usd",
        metadata: Optional[dict] = None,
    ) -> PaymentResult:
        """
        Simulate creating a payment intent.
        
        In real Stripe, this returns a client_secret for frontend confirmation.
        The mock returns a fake client_secret that won't work with Stripe.js.
        """
        latency_ms = await self._simulate_latency()
        
        if amount <= 0:
            return PaymentResult(
                success=False,
                error_message="Amount must be greater than 0",
                error_code="invalid_amount",
                response_time_ms=latency_ms,
            )
        
        payment_intent_id = self._generate_payment_intent_id()
        
        logger.debug(f"Mock: Created payment intent {payment_intent_id}")
        
        return PaymentResult(
            success=True,
            payment_intent_id=payment_intent_id,
            amount=amount,
            currency=currency,
            response_time_ms=latency_ms,
            metadata={
                "client_secret": f"{payment_intent_id}_secret_mock",
                **(metadata or {}),
            },
        )
    
    async def refund_payment(
        self,
        payment_intent_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> RefundResult:
        """Simulate refunding a payment."""
        await self._simulate_latency()
        
        if not payment_intent_id.startswith("pi_"):
            return RefundResult(
                success=False,
                error_message="Invalid payment intent ID",
            )
        
        refund_id = self._generate_refund_id()
        
        logger.info(f"Mock: Refund processed - {refund_id}")
        
        return RefundResult(
            success=True,
            refund_id=refund_id,
            amount=amount,
            status="succeeded",
        )
    
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> Optional[dict]:
        """
        Simulate webhook verification.
        
        In mock mode, always returns the parsed payload without
        cryptographic verification.
        """
        import json
        
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Mock: Invalid webhook payload")
            return None
    
    async def health_check(self) -> bool:
        """
        Mock health check always returns True.
        
        In development, we assume the mock service is always available.
        """
        logger.debug("Mock: Health check passed")
        return True