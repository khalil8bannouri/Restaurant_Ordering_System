"""
Voice Service Module

Provides handlers for voice AI integrations, currently supporting Vapi.ai.

Usage:
    from app.services.voice import get_vapi_handler
    
    handler = get_vapi_handler()
    response = await handler.handle_webhook(payload, db)

Author: Your Name
Version: 2.0.0
"""

from app.services.voice.vapi_handler import (
    VapiWebhookHandler,
    get_vapi_handler,
)
from app.services.voice.vapi_schemas import (
    VapiWebhookPayload,
    VapiMessageType,
    VapiFunctionResponse,
    FunctionCallPayload,
    CallInfo,
    CustomerInfo,
    ExtractedOrderData,
    OrderItem,
)

__all__ = [
    # Handler
    "VapiWebhookHandler",
    "get_vapi_handler",
    # Schemas
    "VapiWebhookPayload",
    "VapiMessageType",
    "VapiFunctionResponse",
    "FunctionCallPayload",
    "CallInfo",
    "CustomerInfo",
    "ExtractedOrderData",
    "OrderItem",
]