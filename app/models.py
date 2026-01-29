"""
SQLAlchemy Database Models
Defines the structure of our database tables.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class OrderStatus(str, enum.Enum):
    """Order status workflow"""
    PENDING = "pending"           # Just received
    VALIDATED = "validated"       # Address confirmed
    PAID = "paid"                 # Payment successful
    PREPARING = "preparing"       # Kitchen working on it
    DELIVERED = "delivered"       # Completed
    FAILED = "failed"             # Something went wrong
    CANCELLED = "cancelled"       # Customer cancelled


class Order(Base):
    """
    Main Order table - stores all phone orders.
    """
    __tablename__ = "orders"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Customer Information
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False, index=True)
    
    # Delivery Address
    delivery_address = Column(String(255), nullable=False)
    city = Column(String(50), nullable=False, default="New York")
    zip_code = Column(String(10), nullable=False)
    
    # Order Details
    items = Column(Text, nullable=False)  # JSON string of ordered items
    special_instructions = Column(Text, nullable=True)
    
    # Pricing
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    delivery_fee = Column(Float, nullable=False, default=5.99)
    total_amount = Column(Float, nullable=False)
    
    # Payment Info (from mock Stripe)
    payment_intent_id = Column(String(100), nullable=True)
    payment_status = Column(String(20), default="pending")
    
    # Order Status
    status = Column(
        Enum(OrderStatus),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Tracking (for Excel export)
    exported_to_excel = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Order #{self.id} - {self.customer_name} - {self.status.value}>"