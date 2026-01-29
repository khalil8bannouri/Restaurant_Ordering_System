"""
Pydantic Schemas for Request/Response Validation
Ensures all API data is properly structured and validated.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import re


class OrderStatusEnum(str, Enum):
    """Order status options"""
    PENDING = "pending"
    VALIDATED = "validated"
    PAID = "paid"
    PREPARING = "preparing"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============ REQUEST SCHEMAS ============

class OrderItemCreate(BaseModel):
    """Single item in an order"""
    name: str = Field(..., min_length=1, max_length=100, examples=["Pizza Margherita"])
    quantity: int = Field(..., ge=1, le=99, examples=[2])
    unit_price: float = Field(..., gt=0, examples=[12.99])
    
    @property
    def total_price(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class OrderCreate(BaseModel):
    """
    Request schema for creating a new order.
    This is what the phone system sends to our API.
    """
    # Customer Info
    customer_name: str = Field(
        ..., 
        min_length=2, 
        max_length=100,
        examples=["John Doe"]
    )
    customer_phone: str = Field(
        ..., 
        min_length=10, 
        max_length=20,
        examples=["555-123-4567"]
    )
    
    # Delivery Address
    delivery_address: str = Field(
        ..., 
        min_length=5, 
        max_length=255,
        examples=["350 Fifth Avenue, Apt 4B"]
    )
    city: str = Field(
        default="New York", 
        max_length=50,
        examples=["New York"]
    )
    zip_code: str = Field(
        ..., 
        min_length=5, 
        max_length=10,
        examples=["10001"]
    )
    
    # Order Items
    items: List[OrderItemCreate] = Field(
        ..., 
        min_length=1,
        examples=[[{"name": "Pizza Margherita", "quantity": 2, "unit_price": 12.99}]]
    )
    
    # Optional
    special_instructions: Optional[str] = Field(
        default=None, 
        max_length=500,
        examples=["Extra cheese, no onions"]
    )
    
    # Payment (simplified - in real world, use Stripe tokens)
    card_last_four: str = Field(
        default="4242", 
        min_length=4, 
        max_length=4,
        examples=["4242"]
    )
    
    @field_validator('customer_phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        """Remove non-numeric chars and validate"""
        cleaned = re.sub(r'[^\d]', '', v)
        if len(cleaned) < 10:
            raise ValueError('Phone number must have at least 10 digits')
        return v
    
    @field_validator('zip_code')
    @classmethod
    def validate_zip(cls, v: str) -> str:
        """Ensure zip code is numeric"""
        if not re.match(r'^\d{5}(-\d{4})?$', v):
            raise ValueError('Invalid zip code format (use 12345 or 12345-6789)')
        return v


# ============ RESPONSE SCHEMAS ============

class OrderResponse(BaseModel):
    """Response schema for a single order"""
    id: int
    customer_name: str
    customer_phone: str
    delivery_address: str
    city: str
    zip_code: str
    items: str  # JSON string
    special_instructions: Optional[str]
    subtotal: float
    tax: float
    delivery_fee: float
    total_amount: float
    payment_intent_id: Optional[str]
    payment_status: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True  # Allows ORM model conversion


class OrderCreateResponse(BaseModel):
    """Response after successfully creating an order"""
    success: bool
    message: str
    order_id: int
    total_amount: float
    estimated_delivery: str
    payment_status: str


class OrderListResponse(BaseModel):
    """Response for listing multiple orders"""
    total: int
    orders: List[OrderResponse]


class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    database: str
    redis: str
    timestamp: datetime