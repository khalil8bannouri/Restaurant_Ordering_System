"""
SQLAlchemy Database Models

Enhanced for full AI phone ordering system with:
- Pickup/Delivery order types
- Call transcription storage
- Multi-language support
- Human fallback tracking

Author: Khalil Bannouri
Version: 3.0.0
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum, Boolean
from sqlalchemy.sql import func
from app.database import Base
import enum


class OrderStatus(str, enum.Enum):
    """Order status workflow."""
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


class OrderType(str, enum.Enum):
    """Order type - Pickup or Delivery."""
    PICKUP = "pickup"
    DELIVERY = "delivery"


class CallOutcome(str, enum.Enum):
    """Outcome of the phone call."""
    ORDER_COMPLETED = "order_completed"
    ORDER_CANCELLED = "order_cancelled"
    TRANSFERRED_TO_HUMAN = "transferred_to_human"
    CUSTOMER_HANGUP = "customer_hangup"
    AI_FAILED = "ai_failed"
    NO_ORDER = "no_order"  # Customer just left a message


class Order(Base):
    """
    Main Order table - stores all phone orders.
    
    Tracks the complete lifecycle from call initiation to delivery/pickup.
    """
    __tablename__ = "orders"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # =========================================================================
    # ORDER TYPE
    # =========================================================================
    order_type = Column(
        Enum(OrderType),
        default=OrderType.DELIVERY,
        nullable=False,
        index=True
    )
    
    # =========================================================================
    # CUSTOMER INFORMATION
    # =========================================================================
    customer_name = Column(String(100), nullable=False)
    customer_phone = Column(String(20), nullable=False, index=True)
    customer_email = Column(String(255), nullable=True)
    customer_language = Column(String(10), default="en", nullable=False)
    
    # =========================================================================
    # DELIVERY ADDRESS (Only for delivery orders)
    # =========================================================================
    delivery_address = Column(String(255), nullable=True)
    city = Column(String(50), nullable=True, default="New York")
    state = Column(String(50), nullable=True, default="NY")
    zip_code = Column(String(10), nullable=True)
    delivery_instructions = Column(Text, nullable=True)
    
    # =========================================================================
    # PICKUP DETAILS (Only for pickup orders)
    # =========================================================================
    pickup_time = Column(DateTime(timezone=True), nullable=True)
    pickup_confirmed = Column(Boolean, default=False)
    
    # =========================================================================
    # ORDER DETAILS
    # =========================================================================
    items = Column(Text, nullable=False)  # JSON string of ordered items
    special_instructions = Column(Text, nullable=True)
    
    # =========================================================================
    # PRICING
    # =========================================================================
    subtotal = Column(Float, nullable=False)
    tax = Column(Float, nullable=False)
    delivery_fee = Column(Float, nullable=False, default=0.0)
    tip = Column(Float, nullable=True, default=0.0)
    total_amount = Column(Float, nullable=False)
    
    # =========================================================================
    # PAYMENT INFO
    # =========================================================================
    payment_intent_id = Column(String(100), nullable=True)
    payment_status = Column(String(20), default="pending")
    payment_link_sent = Column(Boolean, default=False)
    payment_link_url = Column(String(500), nullable=True)
    payment_method = Column(String(50), nullable=True)  # card, cash, etc.
    
    # =========================================================================
    # ORDER STATUS
    # =========================================================================
    status = Column(
        Enum(OrderStatus),
        default=OrderStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # =========================================================================
    # CALL INFORMATION
    # =========================================================================
    call_id = Column(String(100), nullable=True, index=True)
    call_recording_url = Column(String(500), nullable=True)
    call_transcription = Column(Text, nullable=True)
    call_duration_seconds = Column(Integer, nullable=True)
    call_outcome = Column(
        Enum(CallOutcome),
        default=CallOutcome.ORDER_COMPLETED,
        nullable=True
    )
    
    # =========================================================================
    # AI HANDLING
    # =========================================================================
    handled_by_ai = Column(Boolean, default=True)
    transferred_to_human = Column(Boolean, default=False)
    transfer_reason = Column(Text, nullable=True)
    human_agent_id = Column(String(50), nullable=True)
    
    # =========================================================================
    # KITCHEN INTEGRATION
    # =========================================================================
    sent_to_kitchen = Column(Boolean, default=False)
    sent_to_kitchen_at = Column(DateTime(timezone=True), nullable=True)
    kitchen_confirmed = Column(Boolean, default=False)
    estimated_ready_time = Column(DateTime(timezone=True), nullable=True)
    
    # =========================================================================
    # NOTIFICATIONS
    # =========================================================================
    confirmation_email_sent = Column(Boolean, default=False)
    confirmation_sms_sent = Column(Boolean, default=False)
    
    # =========================================================================
    # TIMESTAMPS
    # =========================================================================
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # =========================================================================
    # EXCEL EXPORT TRACKING
    # =========================================================================
    exported_to_excel = Column(Boolean, default=False)
    exported_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<Order #{self.id} - {self.order_type.value} - {self.customer_name} - {self.status.value}>"


class CallLog(Base):
    """
    Stores all incoming calls, including those that don't result in orders.
    
    Used for:
    - Calls where customer says "No" to ordering
    - Failed AI interactions
    - Transferred calls
    - General message recording
    """
    __tablename__ = "call_logs"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # Call Information
    call_id = Column(String(100), nullable=False, unique=True, index=True)
    caller_phone = Column(String(20), nullable=False, index=True)
    caller_language = Column(String(10), default="en")
    
    # Call Details
    call_started_at = Column(DateTime(timezone=True), nullable=False)
    call_ended_at = Column(DateTime(timezone=True), nullable=True)
    call_duration_seconds = Column(Integer, nullable=True)
    
    # Recording & Transcription
    recording_url = Column(String(500), nullable=True)
    transcription = Column(Text, nullable=True)
    
    # Outcome
    wanted_to_order = Column(Boolean, default=False)
    order_id = Column(Integer, nullable=True)  # Link to order if created
    outcome = Column(
        Enum(CallOutcome),
        default=CallOutcome.NO_ORDER,
        nullable=False
    )
    
    # AI Handling
    handled_by_ai = Column(Boolean, default=True)
    transferred_to_human = Column(Boolean, default=False)
    transfer_reason = Column(Text, nullable=True)
    
    # Customer Message (if they just wanted to leave a message)
    customer_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Excel Export
    exported_to_excel = Column(Boolean, default=False)

    def __repr__(self):
        return f"<CallLog {self.call_id} - {self.outcome.value}>"