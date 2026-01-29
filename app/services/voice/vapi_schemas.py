"""
Vapi.ai Webhook Payload Schemas

Defines Pydantic models for parsing and validating Vapi webhook payloads.
These schemas match the structure documented in Vapi's API documentation.

Vapi Webhook Events:
    - function-call: AI requests to execute a tool (e.g., check_address)
    - end-of-call-report: Call completed with transcript
    - status-update: Call status changes
    - transcript: Real-time transcription updates

Reference:
    https://docs.vapi.ai/webhooks

Author: Your Name
Version: 2.0.0
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
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


class VapiCallStatus(str, Enum):
    """Possible call statuses."""
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    FORWARDING = "forwarding"
    ENDED = "ended"


class FunctionCallPayload(BaseModel):
    """
    Payload for function-call webhook events.
    
    Sent when the AI assistant wants to execute a tool/function.
    Our server must execute the function and return the result.
    
    Example payload:
        {
            "type": "function-call",
            "functionCall": {
                "name": "check_delivery_address",
                "parameters": {
                    "address": "350 Fifth Avenue",
                    "city": "New York",
                    "zip_code": "10001"
                }
            },
            "call": {
                "id": "call_abc123",
                "customer": {
                    "number": "+15551234567"
                }
            }
        }
    """
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
    """
    Payload for end-of-call-report webhook events.
    
    Sent when a call ends, containing the full transcript
    and call summary.
    """
    call: CallInfo
    transcript: Optional[str] = Field(None, description="Full transcript text")
    messages: list[TranscriptMessage] = Field(
        default_factory=list,
        description="Structured transcript messages"
    )
    summary: Optional[str] = Field(None, description="AI-generated call summary")
    recording_url: Optional[str] = Field(None, alias="recordingUrl")
    
    class Config:
        populate_by_name = True


class VapiWebhookPayload(BaseModel):
    """
    Main Vapi webhook payload structure.
    
    This is the root model that all Vapi webhooks conform to.
    The `type` field determines which sub-payload is present.
    
    Usage:
        payload = VapiWebhookPayload(**request_json)
        if payload.type == VapiMessageType.FUNCTION_CALL:
            # Handle function call
            func_name = payload.function_call.name
    """
    type: VapiMessageType = Field(..., alias="type")
    
    # Function call specific
    function_call: Optional[FunctionCallPayload] = Field(
        None, 
        alias="functionCall"
    )
    
    # Call information (present in most events)
    call: Optional[CallInfo] = None
    
    # End of call report specific
    transcript: Optional[str] = None
    messages: list[TranscriptMessage] = Field(default_factory=list)
    summary: Optional[str] = None
    recording_url: Optional[str] = Field(None, alias="recordingUrl")
    
    # Status update specific
    status: Optional[VapiCallStatus] = None
    
    class Config:
        populate_by_name = True
        use_enum_values = True


class VapiFunctionResponse(BaseModel):
    """
    Response format for Vapi function calls.
    
    When Vapi calls a function, we must respond with this structure
    so the AI can continue the conversation with the result.
    
    Example response:
        {
            "result": {
                "success": true,
                "message": "Address validated successfully",
                "data": {"formatted_address": "350 5th Ave, New York, NY 10001"}
            }
        }
    """
    result: dict[str, Any] = Field(
        ...,
        description="Result data to return to the AI assistant"
    )


# =============================================================================
# ORDER DATA SCHEMAS (Extracted from Vapi conversation)
# =============================================================================

class OrderItem(BaseModel):
    """A single item in an order."""
    name: str
    quantity: int = 1
    unit_price: float
    special_instructions: Optional[str] = None
    
    @property
    def total_price(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class ExtractedOrderData(BaseModel):
    """
    Order data extracted from Vapi conversation.
    
    This is constructed from the function call parameters
    during the order placement flow.
    """
    customer_name: str
    customer_phone: str
    delivery_address: str
    city: str = "New York"
    zip_code: str
    items: list[OrderItem]
    special_instructions: Optional[str] = None
    payment_method: str = "card"
    
    @property
    def subtotal(self) -> float:
        return round(sum(item.total_price for item in self.items), 2)