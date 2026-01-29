"""
Pydantic Schemas for Request/Response Validation

Enhanced for full AI phone ordering system with:
- Pickup/Delivery support
- Call transcription
- Multi-language
- Payment links

Author: Khalil Bannouri
Version: 3.0.0
"""

from pydantic import BaseModel, Field, field_validator, EmailStr
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum
import re


# =============================================================================
# ENUMS
# =============================================================================

class OrderStatusEnum(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    PREPARING = "preparing"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    PICKED_UP = "picked_up"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TRANSFERRED_TO_HUMAN = "transferred_to_human"


class OrderTypeEnum(str, Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"


class CallOutcomeEnum(str, Enum):
    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    TRANSFERRED_TO_HUMAN = "transferred_to_human"
    CUSTOMER_HANGUP = "customer_hangup"
    AI_FAILED = "ai_failed"
    NO_ORDER = "no_order"


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class OrderItemCreate(BaseModel):
    """Single item in an order."""
    name: str = Field(..., min_length=1, max_length=100, examples=["Pizza Margherita"])
    quantity: int = Field(..., ge=1, le=99, examples=[2])
    unit_price: float = Field(..., gt=0, examples=[14.99])
    special_requests: Optional[str] = Field(None, max_length=200)
    
    @property
    def total_price(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class OrderCreate(BaseModel):
    """Request schema for creating a new order."""
    
    # Order Type
    order_type: OrderTypeEnum = Field(
        default=OrderTypeEnum.DELIVERY,
        examples=["delivery"]
    )
    
    # Customer Info
    customer_name: str = Field(..., min_length=2, max_length=100, examples=["John Doe"])
    customer_phone: str = Field(..., min_length=10, max_length=20, examples=["555-123-4567"])
    customer_email: Optional[str] = Field(None, examples=["john@example.com"])
    customer_language: str = Field(default="en", max_length=10, examples=["en", "es", "fr"])
    
    # Delivery Address (required for delivery orders)
    delivery_address: Optional[str] = Field(None, max_length=255, examples=["350 Fifth Avenue"])
    city: str = Field(default="New York", max_length=50)
    state: str = Field(default="NY", max_length=50)
    zip_code: Optional[str] = Field(None, max_length=10, examples=["10001"])
    delivery_instructions: Optional[str] = Field(None, max_length=500)
    
    # Pickup Details (required for pickup orders)
    pickup_time: Optional[datetime] = Field(None, examples=["2024-01-15T18:30:00"])
    
    # Order Items
    items: List[OrderItemCreate] = Field(..., min_length=1)
    special_instructions: Optional[str] = Field(None, max_length=500)
    
    # Payment
    payment_method: str = Field(default="card", examples=["card", "cash"])
    tip: Optional[float] = Field(default=0.0, ge=0)
    
    # Call Info (from Vapi)
    call_id: Optional[str] = Field(None)
    call_transcription: Optional[str] = Field(None)
    call_recording_url: Optional[str] = Field(None)
    
    @field_validator('customer_phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        cleaned = re.sub(r'[^\d]', '', v)
        if len(cleaned) < 10:
            raise ValueError('Phone number must have at least 10 digits')
        return v
    
    @field_validator('zip_code')
    @classmethod
    def validate_zip(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r'^\d{5}(-\d{4})?$', v):
            raise ValueError('Invalid zip code format')
        return v
    
    @field_validator('customer_email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        # Basic email validation
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', v):
            raise ValueError('Invalid email format')
        return v


class CallLogCreate(BaseModel):
    """Schema for logging a call that didn't result in an order."""
    call_id: str
    caller_phone: str
    caller_language: str = "en"
    transcription: Optional[str] = None
    recording_url: Optional[str] = None
    customer_message: Optional[str] = None
    outcome: CallOutcomeEnum = CallOutcomeEnum.NO_ORDER


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class OrderResponse(BaseModel):
    """Response schema for a single order."""
    id: int
    order_type: str
    customer_name: str
    customer_phone: str
    customer_email: Optional[str]
    customer_language: str
    delivery_address: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip_code: Optional[str]
    delivery_instructions: Optional[str]
    pickup_time: Optional[datetime]
    items: str
    special_instructions: Optional[str]
    subtotal: float
    tax: float
    delivery_fee: float
    tip: Optional[float]
    total_amount: float
    payment_intent_id: Optional[str]
    payment_status: str
    payment_link_sent: bool
    payment_link_url: Optional[str]
    status: str
    call_id: Optional[str]
    call_recording_url: Optional[str]
    call_transcription: Optional[str]
    handled_by_ai: bool
    transferred_to_human: bool
    sent_to_kitchen: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class OrderCreateResponse(BaseModel):
    """Response after successfully creating an order."""
    success: bool
    message: str
    order_id: int
    order_type: str
    total_amount: float
    payment_status: str
    payment_link_url: Optional[str] = None
    estimated_time: str
    confirmation_sent: bool = False


class OrderListResponse(BaseModel):
    """Response for listing multiple orders."""
    total: int
    orders: List[OrderResponse]


class CallLogResponse(BaseModel):
    """Response for a call log entry."""
    id: int
    call_id: str
    caller_phone: str
    caller_language: str
    transcription: Optional[str]
    recording_url: Optional[str]
    outcome: str
    wanted_to_order: bool
    order_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    database: str
    redis: str
    payment_service: str
    geo_service: str
    notification_service: str
    timestamp: datetime


# =============================================================================
# NOTIFICATION SCHEMAS
# =============================================================================

class SendPaymentLinkRequest(BaseModel):
    """Request to send payment link to customer."""
    order_id: int
    method: str = Field(default="email", pattern="^(email|sms|both)$")


class NotificationResponse(BaseModel):
    """Response after sending notification."""
    success: bool
    message: str
    email_sent: bool = False
    sms_sent: bool = False
    payment_link: Optional[str] = None


# =============================================================================
# KITCHEN INTEGRATION SCHEMAS
# =============================================================================

class KitchenOrderRequest(BaseModel):
    """Request to send order to kitchen."""
    order_id: int


class KitchenOrderResponse(BaseModel):
    """Response after sending to kitchen."""
    success: bool
    message: str
    order_id: int
    estimated_ready_time: Optional[datetime] = None


# =============================================================================
# TRANSFER SCHEMAS
# =============================================================================

class TransferToHumanRequest(BaseModel):
    """Request to transfer call to human agent."""
    call_id: str
    reason: str
    transcription_so_far: Optional[str] = None


class TransferResponse(BaseModel):
    """Response after transfer request."""
    success: bool
    message: str
    human_agent_id: Optional[str] = None
    transfer_number: Optional[str] = None