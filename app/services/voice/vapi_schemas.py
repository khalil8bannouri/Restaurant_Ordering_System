"""
Vapi.ai Webhook Payload Schemas

Enhanced for full restaurant ordering with:
- Multi-language detection
- Pickup/Delivery selection
- Human transfer support
- Call transcription storage

Author: Khalil Bannouri
Version: 3.0.0
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List
from datetime import datetime
from enum import Enum


class VapiMessageType(str, Enum):
    """Types of messages Vapi sends to webhooks."""
    FUNCTION_CALL = "function-call"
    END_OF_CALL_REPORT = "end-of-call-report"
    STATUS_UPDATE = "status-update"
    TRANSCRIPT = "transcript"
    HANG = "hang"
    SPEECH_UPDATE = "speech-update"
    CONVERSATION_UPDATE = "conversation-update"
    TRANSFER_REQUEST = "transfer-request"


class VapiCallStatus(str, Enum):
    """Possible call statuses."""
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    FORWARDING = "forwarding"
    ENDED = "ended"


class DetectedLanguage(str, Enum):
    """Supported languages for auto-detection."""
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    CHINESE = "zh"
    ARABIC = "ar"
    PORTUGUESE = "pt"
    RUSSIAN = "ru"
    JAPANESE = "ja"
    KOREAN = "ko"
    GERMAN = "de"
    ITALIAN = "it"


class FunctionCallPayload(BaseModel):
    """Payload for function-call webhook events."""
    name: str = Field(..., description="Name of the function to call")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters passed to the function"
    )


class CustomerInfo(BaseModel):
    """Customer information from the call."""
    number: Optional[str] = Field(None, description="Customer phone number")
    name: Optional[str] = Field(None, description="Customer name if known")


class CallInfo(BaseModel):
    """Information about the current call."""
    id: str = Field(..., description="Unique call identifier")
    org_id: Optional[str] = Field(None, alias="orgId")
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    started_at: Optional[datetime] = Field(None, alias="startedAt")
    ended_at: Optional[datetime] = Field(None, alias="endedAt")
    customer: Optional[CustomerInfo] = None
    status: Optional[VapiCallStatus] = None
    ended_reason: Optional[str] = Field(None, alias="endedReason")
    
    class Config:
        populate_by_name = True


class TranscriptMessage(BaseModel):
    """A single message in the conversation transcript."""
    role: str = Field(..., description="Speaker role: 'user' or 'assistant'")
    message: str = Field(..., description="The spoken text")
    time: Optional[float] = Field(None, description="Timestamp in seconds")
    seconds_from_start: Optional[float] = Field(None, alias="secondsFromStart")
    
    class Config:
        populate_by_name = True


class EndOfCallReport(BaseModel):
    """Payload for end-of-call-report webhook events."""
    call: CallInfo
    transcript: Optional[str] = Field(None, description="Full transcript text")
    messages: List[TranscriptMessage] = Field(
        default_factory=list,
        description="Structured transcript messages"
    )
    summary: Optional[str] = Field(None, description="AI-generated call summary")
    recording_url: Optional[str] = Field(None, alias="recordingUrl")
    duration_seconds: Optional[int] = Field(None, alias="durationSeconds")
    detected_language: Optional[str] = Field(None, alias="detectedLanguage")
    
    class Config:
        populate_by_name = True


class VapiWebhookPayload(BaseModel):
    """Main Vapi webhook payload structure."""
    type: VapiMessageType = Field(..., alias="type")
    
    # Function call specific
    function_call: Optional[FunctionCallPayload] = Field(None, alias="functionCall")
    
    # Call information
    call: Optional[CallInfo] = None
    
    # End of call report specific
    transcript: Optional[str] = None
    messages: List[TranscriptMessage] = Field(default_factory=list)
    summary: Optional[str] = None
    recording_url: Optional[str] = Field(None, alias="recordingUrl")
    duration_seconds: Optional[int] = Field(None, alias="durationSeconds")
    
    # Language detection
    detected_language: Optional[str] = Field(None, alias="detectedLanguage")
    
    # Status update specific
    status: Optional[VapiCallStatus] = None
    
    # Transfer specific
    transfer_destination: Optional[str] = Field(None, alias="transferDestination")
    
    class Config:
        populate_by_name = True
        use_enum_values = True


class VapiFunctionResponse(BaseModel):
    """Response format for Vapi function calls."""
    result: dict[str, Any] = Field(..., description="Result data to return to AI")


# =============================================================================
# ORDER DATA SCHEMAS
# =============================================================================

class OrderItem(BaseModel):
    """A single item in an order."""
    name: str
    quantity: int = 1
    unit_price: float
    special_requests: Optional[str] = None
    
    @property
    def total_price(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class ExtractedOrderData(BaseModel):
    """Order data extracted from Vapi conversation."""
    order_type: str = "delivery"  # pickup or delivery
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    customer_language: str = "en"
    
    # Delivery fields
    delivery_address: Optional[str] = None
    city: str = "New York"
    state: str = "NY"
    zip_code: Optional[str] = None
    delivery_instructions: Optional[str] = None
    
    # Pickup fields
    pickup_time: Optional[str] = None
    
    # Order
    items: List[OrderItem] = []
    special_instructions: Optional[str] = None
    
    # Payment
    payment_method: str = "card"
    tip: float = 0.0
    
    @property
    def subtotal(self) -> float:
        return round(sum(item.total_price for item in self.items), 2)


class TransferRequest(BaseModel):
    """Request to transfer call to human agent."""
    call_id: str
    reason: str
    transcription_so_far: Optional[str] = None
    customer_phone: Optional[str] = None
    detected_language: str = "en"