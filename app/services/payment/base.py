"""
Payment Service Abstract Base Class

Defines the interface contract for all payment service implementations.
Both MockPaymentService and StripePaymentService must implement these methods,
ensuring consistent behavior regardless of which service is active.

Design Pattern: Strategy Pattern
    - Allows runtime switching between payment providers
    - New providers can be added without modifying existing code
    - Facilitates testing with mock implementations

Author: Your Name
Version: 2.0.0
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class PaymentResult:
    """
    Standardized result from payment processing.
    
    Both Mock and Real implementations return this same structure,
    allowing the rest of the application to work identically
    regardless of which service is active.
    
    Attributes:
        success: Whether the payment was successful
        payment_intent_id: Unique identifier for the payment (Stripe format: pi_xxx)
        charge_id: Charge identifier if applicable (Stripe format: ch_xxx)
        amount: Amount charged in dollars
        currency: Currency code (e.g., "usd")
        error_message: Error description if payment failed
        error_code: Machine-readable error code
        response_time_ms: Time taken to process the payment
        metadata: Additional data from the payment provider
    """
    success: bool
    payment_intent_id: Optional[str] = None
    charge_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "usd"
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    response_time_ms: float = 0.0
    metadata: Optional[dict] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "payment_intent_id": self.payment_intent_id,
            "charge_id": self.charge_id,
            "amount": self.amount,
            "currency": self.currency,
            "error_message": self.error_message,
            "error_code": self.error_code,
            "response_time_ms": self.response_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class RefundResult:
    """
    Standardized result from refund processing.
    
    Attributes:
        success: Whether the refund was successful
        refund_id: Unique identifier for the refund
        amount: Amount refunded in dollars
        status: Refund status (pending, succeeded, failed)
        error_message: Error description if refund failed
    """
    success: bool
    refund_id: Optional[str] = None
    amount: Optional[float] = None
    status: str = "pending"
    error_message: Optional[str] = None


class BasePaymentService(ABC):
    """
    Abstract base class for payment services.
    
    All payment service implementations (Mock, Stripe, etc.) must
    inherit from this class and implement all abstract methods.
    
    This ensures:
        1. Consistent interface across all payment providers
        2. Easy swapping between providers via configuration
        3. Type safety and IDE autocompletion
        4. Clear documentation of expected behavior
    
    Example:
        >>> service = get_payment_service()  # Returns Mock or Stripe
        >>> result = await service.process_payment(
        ...     amount=29.99,
        ...     customer_email="john@example.com"
        ... )
        >>> if result.success:
        ...     print(f"Payment ID: {result.payment_intent_id}")
    """
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Return the name of the payment provider.
        
        Returns:
            str: Provider name (e.g., "mock", "stripe")
        """
        pass
    
    @abstractmethod
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
        Process a payment transaction.
        
        Args:
            amount: Amount to charge in dollars (e.g., 29.99)
            currency: Three-letter currency code (default: "usd")
            customer_email: Customer's email for receipt
            customer_name: Customer's name for records
            description: Description of the charge
            metadata: Additional key-value data to attach
            
        Returns:
            PaymentResult: Standardized result object
            
        Note:
            - Amount should be in dollars, not cents
            - Implementation handles conversion if needed
        """
        pass
    
    @abstractmethod
    async def create_payment_intent(
        self,
        amount: float,
        currency: str = "usd",
        metadata: Optional[dict] = None,
    ) -> PaymentResult:
        """
        Create a payment intent for client-side confirmation.
        
        Used for Stripe Elements or similar client-side payment flows.
        
        Args:
            amount: Amount in dollars
            currency: Currency code
            metadata: Additional data to attach
            
        Returns:
            PaymentResult: Contains client_secret for frontend
        """
        pass
    
    @abstractmethod
    async def refund_payment(
        self,
        payment_intent_id: str,
        amount: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> RefundResult:
        """
        Refund a previous payment.
        
        Args:
            payment_intent_id: The payment to refund
            amount: Amount to refund (None = full refund)
            reason: Reason for the refund
            
        Returns:
            RefundResult: Standardized refund result
        """
        pass
    
    @abstractmethod
    async def verify_webhook(
        self,
        payload: bytes,
        signature: str,
    ) -> Optional[dict]:
        """
        Verify and parse a webhook from the payment provider.
        
        Args:
            payload: Raw request body bytes
            signature: Signature header from the request
            
        Returns:
            dict: Parsed webhook event if valid, None if invalid
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify connectivity to the payment service.
        
        Returns:
            bool: True if service is reachable and operational
        """
        pass