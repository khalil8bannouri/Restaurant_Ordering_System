"""
Vapi.ai Webhook Handler

Processes incoming webhooks from Vapi.ai voice assistant.
Handles function calls for address validation, payment processing,
and order creation.

Supported Functions:
    - check_delivery_address: Validate address and check delivery zone
    - process_payment: Charge the customer's card
    - create_order: Create the order in the system
    - get_menu: Return available menu items
    - get_order_status: Check status of an existing order

Author: Your Name
Version: 2.0.0
"""

import json
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.payment import get_payment_service
from app.services.geo import get_geo_service
from app.services.voice.vapi_schemas import (
    VapiWebhookPayload,
    VapiMessageType,
    VapiFunctionResponse,
    ExtractedOrderData,
    OrderItem,
)
from app.models import Order, OrderStatus
from app.tasks import export_order_to_excel

logger = logging.getLogger(__name__)
settings = get_settings()


class VapiWebhookHandler:
    """
    Handles all Vapi.ai webhook events.
    
    This class processes incoming webhooks from Vapi, executes
    the requested functions, and returns responses that the
    AI assistant can use to continue the conversation.
    
    Attributes:
        payment_service: Payment processor (Mock or Stripe)
        geo_service: Address validator (Mock or Google)
        
    Example:
        >>> handler = VapiWebhookHandler()
        >>> response = await handler.handle_webhook(payload, db_session)
    """
    
    # Menu items (in production, this would come from a database)
    MENU_ITEMS = {
        "pizza_margherita": {"name": "Pizza Margherita", "price": 14.99},
        "pizza_pepperoni": {"name": "Pepperoni Pizza", "price": 16.99},
        "pizza_veggie": {"name": "Veggie Supreme Pizza", "price": 15.99},
        "pasta_carbonara": {"name": "Pasta Carbonara", "price": 13.99},
        "pasta_bolognese": {"name": "Pasta Bolognese", "price": 12.99},
        "caesar_salad": {"name": "Caesar Salad", "price": 8.99},
        "garlic_bread": {"name": "Garlic Bread", "price": 5.99},
        "tiramisu": {"name": "Tiramisu", "price": 7.99},
        "coke": {"name": "Coca-Cola", "price": 2.99},
        "water": {"name": "Sparkling Water", "price": 2.49},
    }
    
    def __init__(self):
        """Initialize handler with service dependencies."""
        self.payment_service = get_payment_service()
        self.geo_service = get_geo_service()
        
        logger.info(
            f"VapiWebhookHandler initialized "
            f"(payment={self.payment_service.provider_name}, "
            f"geo={self.geo_service.provider_name})"
        )
    
    async def handle_webhook(
        self,
        payload: VapiWebhookPayload,
        db: Optional[AsyncSession] = None,
    ) -> dict[str, Any]:
        """
        Main entry point for processing Vapi webhooks.
        
        Routes the webhook to the appropriate handler based on
        the message type.
        
        Args:
            payload: Parsed Vapi webhook payload
            db: Database session (required for order creation)
            
        Returns:
            dict: Response to send back to Vapi
        """
        logger.info(f"Processing Vapi webhook: type={payload.type}")
        
        if payload.type == VapiMessageType.FUNCTION_CALL:
            return await self._handle_function_call(payload, db)
        
        elif payload.type == VapiMessageType.END_OF_CALL_REPORT:
            return await self._handle_end_of_call(payload)
        
        elif payload.type == VapiMessageType.STATUS_UPDATE:
            return await self._handle_status_update(payload)
        
        else:
            logger.debug(f"Unhandled webhook type: {payload.type}")
            return {"status": "acknowledged"}
    
    async def _handle_function_call(
        self,
        payload: VapiWebhookPayload,
        db: Optional[AsyncSession],
    ) -> dict[str, Any]:
        """
        Handle function-call webhook events.
        
        Routes to the appropriate function based on the function name.
        """
        if not payload.function_call:
            logger.error("Function call payload missing")
            return self._error_response("Invalid function call payload")
        
        func_name = payload.function_call.name
        params = payload.function_call.parameters
        
        logger.info(f"Function call: {func_name} with params: {params}")
        
        # Route to appropriate handler
        handlers = {
            "check_delivery_address": self._func_check_address,
            "validate_address": self._func_check_address,
            "process_payment": self._func_process_payment,
            "create_payment": self._func_process_payment,
            "create_order": self._func_create_order,
            "place_order": self._func_create_order,
            "get_menu": self._func_get_menu,
            "get_order_status": self._func_get_order_status,
        }
        
        handler = handlers.get(func_name)
        
        if handler:
            if func_name in ("create_order", "place_order"):
                return await handler(params, db, payload.call)
            return await handler(params)
        else:
            logger.warning(f"Unknown function: {func_name}")
            return self._error_response(f"Unknown function: {func_name}")
    
    async def _func_check_address(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate a delivery address.
        
        Called by Vapi when customer provides their address.
        """
        address = params.get("address", "")
        city = params.get("city", "New York")
        zip_code = params.get("zip_code", params.get("zipCode", ""))
        state = params.get("state", "NY")
        
        logger.debug(f"Validating address: {address}, {city}, {zip_code}")
        
        result = await self.geo_service.validate_address(
            address=address,
            city=city,
            zip_code=zip_code,
            state=state,
        )
        
        if result.is_valid and result.is_in_delivery_zone:
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "message": "Great! We can deliver to your address.",
                    "formatted_address": result.formatted_address,
                    "delivery_available": True,
                    "estimated_delivery_time": f"{settings.estimated_delivery_minutes} minutes",
                }
            ).model_dump()
        
        elif result.is_valid and not result.is_in_delivery_zone:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": result.error_message or "Sorry, we don't deliver to that area.",
                    "delivery_available": False,
                }
            ).model_dump()
        
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": result.error_message or "We couldn't validate that address. Could you please repeat it?",
                    "delivery_available": False,
                }
            ).model_dump()
    
    async def _func_process_payment(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process a payment for the order.
        
        In a real implementation, this would use Stripe Elements
        on the frontend. For voice orders, we'd need a different
        PCI-compliant approach (e.g., IVR card capture).
        """
        amount = params.get("amount", 0)
        customer_email = params.get("email", params.get("customer_email"))
        customer_name = params.get("name", params.get("customer_name"))
        
        if amount <= 0:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": "Invalid order amount.",
                }
            ).model_dump()
        
        logger.debug(f"Processing payment: ${amount:.2f}")
        
        result = await self.payment_service.process_payment(
            amount=amount,
            customer_email=customer_email,
            customer_name=customer_name,
            description=f"Order for {customer_name}",
        )
        
        if result.success:
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "message": "Payment processed successfully!",
                    "payment_id": result.payment_intent_id,
                    "amount_charged": result.amount,
                }
            ).model_dump()
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": result.error_message or "Payment failed. Please try again.",
                    "error_code": result.error_code,
                }
            ).model_dump()
    
    async def _func_create_order(
        self,
        params: dict[str, Any],
        db: Optional[AsyncSession],
        call_info: Optional[Any] = None,
    ) -> dict[str, Any]:
        """
        Create an order in the system.
        
        This is the final step in the order flow, called after
        address validation and payment processing.
        """
        if not db:
            logger.error("Database session required for order creation")
            return self._error_response("System error: database unavailable")
        
        try:
            # Extract order data from params
            customer_name = params.get("customer_name", "Voice Customer")
            customer_phone = params.get("customer_phone", "")
            
            # If phone not in params, try to get from call info
            if not customer_phone and call_info and call_info.customer:
                customer_phone = call_info.customer.number or ""
            
            delivery_address = params.get("delivery_address", "")
            city = params.get("city", "New York")
            zip_code = params.get("zip_code", "")
            
            # Parse items
            items_raw = params.get("items", [])
            items = []
            for item in items_raw:
                if isinstance(item, dict):
                    items.append(OrderItem(
                        name=item.get("name", "Unknown Item"),
                        quantity=item.get("quantity", 1),
                        unit_price=item.get("unit_price", item.get("price", 0)),
                    ))
            
            if not items:
                return VapiFunctionResponse(
                    result={
                        "success": False,
                        "message": "No items in the order. What would you like to order?",
                    }
                ).model_dump()
            
            # Calculate totals
            subtotal = sum(item.total_price for item in items)
            tax = round(subtotal * settings.tax_rate, 2)
            delivery_fee = settings.delivery_fee
            total = round(subtotal + tax + delivery_fee, 2)
            
            # Get payment ID if provided
            payment_id = params.get("payment_id", params.get("payment_intent_id"))
            
            # Create order in database
            items_json = json.dumps([
                {
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                }
                for item in items
            ])
            
            new_order = Order(
                customer_name=customer_name,
                customer_phone=customer_phone,
                delivery_address=delivery_address,
                city=city,
                zip_code=zip_code,
                items=items_json,
                special_instructions=params.get("special_instructions"),
                subtotal=subtotal,
                tax=tax,
                delivery_fee=delivery_fee,
                total_amount=total,
                payment_intent_id=payment_id,
                payment_status="paid" if payment_id else "pending",
                status=OrderStatus.PAID if payment_id else OrderStatus.PENDING,
            )
            
            db.add(new_order)
            await db.commit()
            await db.refresh(new_order)
            
            logger.info(f"Order created: #{new_order.id} for {customer_name}")
            
            # Queue Excel export
            export_order_to_excel.delay({
                "order_id": new_order.id,
                "customer_name": new_order.customer_name,
                "customer_phone": new_order.customer_phone,
                "delivery_address": new_order.delivery_address,
                "city": new_order.city,
                "zip_code": new_order.zip_code,
                "items": new_order.items,
                "special_instructions": new_order.special_instructions,
                "subtotal": new_order.subtotal,
                "tax": new_order.tax,
                "delivery_fee": new_order.delivery_fee,
                "total_amount": new_order.total_amount,
                "payment_intent_id": new_order.payment_intent_id,
                "payment_status": new_order.payment_status,
                "order_status": new_order.status.value,
                "created_at": new_order.created_at.isoformat(),
            })
            
            # Calculate estimated delivery
            estimated_time = datetime.now() + timedelta(
                minutes=settings.estimated_delivery_minutes
            )
            
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "message": f"Your order has been placed! Order number is {new_order.id}.",
                    "order_id": new_order.id,
                    "total_amount": total,
                    "estimated_delivery": estimated_time.strftime("%I:%M %p"),
                    "items_count": len(items),
                }
            ).model_dump()
            
        except Exception as e:
            logger.exception(f"Error creating order: {e}")
            return self._error_response(
                "Sorry, there was a problem placing your order. Please try again."
            )
    
    async def _func_get_menu(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Return the restaurant menu."""
        category = params.get("category", "all")
        
        menu_items = []
        for key, item in self.MENU_ITEMS.items():
            menu_items.append({
                "id": key,
                "name": item["name"],
                "price": item["price"],
            })
        
        return VapiFunctionResponse(
            result={
                "success": True,
                "menu": menu_items,
                "message": "Here's our menu. What would you like to order?",
            }
        ).model_dump()
    
    async def _func_get_order_status(
        self,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Check the status of an existing order."""
        order_id = params.get("order_id")
        
        if not order_id:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": "Please provide your order number.",
                }
            ).model_dump()
        
        # In a real implementation, we'd query the database
        # For now, return a mock response
        return VapiFunctionResponse(
            result={
                "success": True,
                "order_id": order_id,
                "status": "preparing",
                "message": f"Order {order_id} is being prepared and will be delivered soon!",
            }
        ).model_dump()
    
    async def _handle_end_of_call(
        self,
        payload: VapiWebhookPayload,
    ) -> dict[str, Any]:
        """Handle end-of-call-report events."""
        call_id = payload.call.id if payload.call else "unknown"
        
        logger.info(
            f"Call ended: {call_id}, "
            f"summary: {payload.summary or 'No summary'}"
        )
        
        # In production, you might:
        # - Store the transcript
        # - Update CRM
        # - Send follow-up email
        
        return {"status": "acknowledged"}
    
    async def _handle_status_update(
        self,
        payload: VapiWebhookPayload,
    ) -> dict[str, Any]:
        """Handle status-update events."""
        call_id = payload.call.id if payload.call else "unknown"
        status = payload.status
        
        logger.info(f"Call status update: {call_id} -> {status}")
        
        return {"status": "acknowledged"}
    
    def _error_response(self, message: str) -> dict[str, Any]:
        """Create a standard error response."""
        return VapiFunctionResponse(
            result={
                "success": False,
                "message": message,
            }
        ).model_dump()


# Singleton instance
_handler_instance: Optional[VapiWebhookHandler] = None


def get_vapi_handler() -> VapiWebhookHandler:
    """
    Get the Vapi webhook handler instance.
    
    Uses singleton pattern for efficiency.
    """
    global _handler_instance
    
    if _handler_instance is None:
        _handler_instance = VapiWebhookHandler()
    
    return _handler_instance