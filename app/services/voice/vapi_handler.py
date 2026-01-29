"""
Vapi.ai Webhook Handler

Enhanced for full restaurant ordering system with:
- Multi-language detection and response
- Pickup vs Delivery order flow
- Human fallback transfer
- Call recording and transcription storage
- Payment link generation

Author: Khalil Bannouri
Version: 3.0.0
"""

import json
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.services.payment import get_payment_service
from app.services.geo import get_geo_service
from app.services.notifications import get_notification_service
from app.services.voice.vapi_schemas import (
    VapiWebhookPayload,
    VapiMessageType,
    VapiFunctionResponse,
    OrderItem,
    TransferRequest,
)
from app.models import Order, OrderStatus, OrderType, CallLog, CallOutcome
from app.tasks import export_order_to_excel, export_call_log_to_excel

logger = logging.getLogger(__name__)
settings = get_settings()


class VapiWebhookHandler:
    """
    Handles all Vapi.ai webhook events for restaurant ordering.
    
    Supported Functions:
        - check_wants_to_order: Initial "Would you like to place an order?"
        - select_order_type: "Is this pickup or delivery?"
        - check_delivery_address: Validate delivery address
        - get_menu: Return available menu items
        - add_items_to_order: Add items to the order
        - confirm_order: Confirm order details
        - process_payment: Process or send payment link
        - create_order: Finalize and create the order
        - transfer_to_human: Transfer call to human agent
        - record_message: Record customer message (no order)
    """
    
    # Restaurant Menu
    MENU_ITEMS = {
        "pizza_margherita": {"name": "Pizza Margherita", "price": 14.99, "category": "pizza"},
        "pizza_pepperoni": {"name": "Pepperoni Pizza", "price": 16.99, "category": "pizza"},
        "pizza_veggie": {"name": "Veggie Supreme Pizza", "price": 15.99, "category": "pizza"},
        "pizza_hawaiian": {"name": "Hawaiian Pizza", "price": 16.99, "category": "pizza"},
        "pasta_carbonara": {"name": "Pasta Carbonara", "price": 13.99, "category": "pasta"},
        "pasta_bolognese": {"name": "Pasta Bolognese", "price": 12.99, "category": "pasta"},
        "pasta_alfredo": {"name": "Chicken Alfredo", "price": 14.99, "category": "pasta"},
        "caesar_salad": {"name": "Caesar Salad", "price": 8.99, "category": "salad"},
        "garden_salad": {"name": "Garden Salad", "price": 7.99, "category": "salad"},
        "garlic_bread": {"name": "Garlic Bread", "price": 5.99, "category": "sides"},
        "mozzarella_sticks": {"name": "Mozzarella Sticks", "price": 7.99, "category": "sides"},
        "chicken_wings": {"name": "Chicken Wings (10pc)", "price": 12.99, "category": "sides"},
        "tiramisu": {"name": "Tiramisu", "price": 7.99, "category": "dessert"},
        "cheesecake": {"name": "New York Cheesecake", "price": 6.99, "category": "dessert"},
        "coke": {"name": "Coca-Cola", "price": 2.99, "category": "drinks"},
        "sprite": {"name": "Sprite", "price": 2.99, "category": "drinks"},
        "water": {"name": "Bottled Water", "price": 1.99, "category": "drinks"},
        "iced_tea": {"name": "Iced Tea", "price": 2.49, "category": "drinks"},
    }
    
    # Language-specific greetings
    GREETINGS = {
        "en": "Thank you for calling {restaurant}! Would you like to place an order?",
        "es": "¡Gracias por llamar a {restaurant}! ¿Le gustaría hacer un pedido?",
        "fr": "Merci d'avoir appelé {restaurant}! Souhaitez-vous passer une commande?",
        "zh": "感谢致电{restaurant}！您想下订单吗？",
        "ar": "شكراً لاتصالك بـ {restaurant}! هل ترغب في تقديم طلب؟",
        "pt": "Obrigado por ligar para {restaurant}! Gostaria de fazer um pedido?",
        "de": "Danke für Ihren Anruf bei {restaurant}! Möchten Sie eine Bestellung aufgeben?",
        "it": "Grazie per aver chiamato {restaurant}! Vuole fare un ordine?",
        "ja": "{restaurant}にお電話いただきありがとうございます！ご注文されますか？",
        "ko": "{restaurant}에 전화해 주셔서 감사합니다! 주문하시겠습니까?",
    }
    
    def __init__(self):
        """Initialize handler with service dependencies."""
        self.payment_service = get_payment_service()
        self.geo_service = get_geo_service()
        self.notification_service = get_notification_service()
        
        logger.info(
            f"VapiWebhookHandler initialized "
            f"(payment={self.payment_service.provider_name}, "
            f"geo={self.geo_service.provider_name}, "
            f"notifications={self.notification_service.provider_name})"
        )
    
    async def handle_webhook(
        self,
        payload: VapiWebhookPayload,
        db: Optional[AsyncSession] = None,
    ) -> dict[str, Any]:
        """Main entry point for processing Vapi webhooks."""
        logger.info(f"Processing Vapi webhook: type={payload.type}")
        
        if payload.type == VapiMessageType.FUNCTION_CALL:
            return await self._handle_function_call(payload, db)
        
        elif payload.type == VapiMessageType.END_OF_CALL_REPORT:
            return await self._handle_end_of_call(payload, db)
        
        elif payload.type == VapiMessageType.STATUS_UPDATE:
            return await self._handle_status_update(payload)
        
        elif payload.type == VapiMessageType.TRANSFER_REQUEST:
            return await self._handle_transfer_request(payload, db)
        
        else:
            logger.debug(f"Unhandled webhook type: {payload.type}")
            return {"status": "acknowledged"}
    
    async def _handle_function_call(
        self,
        payload: VapiWebhookPayload,
        db: Optional[AsyncSession],
    ) -> dict[str, Any]:
        """Route function calls to appropriate handlers."""
        if not payload.function_call:
            return self._error_response("Invalid function call payload")
        
        func_name = payload.function_call.name
        params = payload.function_call.parameters
        
        logger.info(f"Function call: {func_name}")
        logger.debug(f"Parameters: {params}")
        
        # Get detected language
        language = params.get("detected_language", payload.detected_language or "en")
        
        # Route to handler
        handlers = {
            # Initial flow
            "check_wants_to_order": self._func_check_wants_to_order,
            "select_order_type": self._func_select_order_type,
            
            # Address validation
            "check_delivery_address": self._func_check_address,
            "validate_address": self._func_check_address,
            
            # Menu and ordering
            "get_menu": self._func_get_menu,
            "add_items_to_order": self._func_add_items,
            "remove_item_from_order": self._func_remove_item,
            
            # Order confirmation
            "confirm_order": self._func_confirm_order,
            "get_order_summary": self._func_get_order_summary,
            
            # Payment
            "process_payment": self._func_process_payment,
            "create_payment_link": self._func_create_payment_link,
            
            # Order creation
            "create_order": self._func_create_order,
            "place_order": self._func_create_order,
            
            # Human transfer
            "transfer_to_human": self._func_transfer_to_human,
            "request_human_agent": self._func_transfer_to_human,
            
            # No order - just message
            "record_message": self._func_record_message,
            "leave_message": self._func_record_message,
            
            # Order status
            "get_order_status": self._func_get_order_status,
        }
        
        handler = handlers.get(func_name)
        
        if handler:
            # Pass db session for handlers that need it
            if func_name in ("create_order", "place_order", "record_message", "leave_message"):
                return await handler(params, db, payload.call, language)
            return await handler(params, language)
        else:
            logger.warning(f"Unknown function: {func_name}")
            return self._error_response(f"Unknown function: {func_name}")
    
    # =========================================================================
    # FUNCTION HANDLERS
    # =========================================================================
    
    async def _func_check_wants_to_order(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Handle initial 'Would you like to place an order?' response."""
        wants_to_order = params.get("wants_to_order", params.get("response", "")).lower()
        
        if wants_to_order in ("yes", "yeah", "sure", "ok", "okay", "please", "si", "oui", "ja"):
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "wants_to_order": True,
                    "message": "Great! Is this order for pickup or delivery?",
                    "next_action": "select_order_type",
                }
            ).model_dump()
        else:
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "wants_to_order": False,
                    "message": "No problem! Would you like to leave a message?",
                    "next_action": "record_message",
                }
            ).model_dump()
    
    async def _func_select_order_type(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Handle pickup vs delivery selection."""
        order_type = params.get("order_type", "").lower()
        
        if order_type in ("pickup", "pick up", "pick-up", "carryout", "carry out"):
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "order_type": "pickup",
                    "message": "Perfect! What time would you like to pick up your order?",
                    "next_action": "get_pickup_time",
                }
            ).model_dump()
        
        elif order_type in ("delivery", "deliver", "delivered"):
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "order_type": "delivery",
                    "message": "Sure! What's your delivery address?",
                    "next_action": "check_delivery_address",
                }
            ).model_dump()
        
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": "I'm sorry, I didn't catch that. Would you like pickup or delivery?",
                    "next_action": "select_order_type",
                }
            ).model_dump()
    
    async def _func_check_address(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Validate delivery address."""
        address = params.get("address", "")
        city = params.get("city", "New York")
        zip_code = params.get("zip_code", params.get("zipCode", ""))
        state = params.get("state", "NY")
        
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
                    "message": f"Great! We can deliver to {result.formatted_address}. What would you like to order?",
                    "formatted_address": result.formatted_address,
                    "delivery_available": True,
                    "estimated_delivery_time": f"{settings.estimated_delivery_minutes} minutes",
                    "next_action": "get_menu",
                }
            ).model_dump()
        
        elif result.is_valid and not result.is_in_delivery_zone:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": f"I'm sorry, we don't deliver to {zip_code}. Would you like to do a pickup order instead?",
                    "delivery_available": False,
                    "suggest_pickup": True,
                }
            ).model_dump()
        
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": "I couldn't find that address. Could you please repeat it?",
                    "delivery_available": False,
                }
            ).model_dump()
    
    async def _func_get_menu(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Return restaurant menu."""
        category = params.get("category", "all").lower()
        
        menu_items = []
        for key, item in self.MENU_ITEMS.items():
            if category == "all" or item["category"] == category:
                menu_items.append({
                    "id": key,
                    "name": item["name"],
                    "price": item["price"],
                    "category": item["category"],
                })
        
        # Group by category for voice response
        categories = {}
        for item in menu_items:
            cat = item["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(f"{item['name']} for ${item['price']}")
        
        menu_text = ""
        for cat, items in categories.items():
            menu_text += f"\n{cat.title()}: {', '.join(items)}."
        
        return VapiFunctionResponse(
            result={
                "success": True,
                "menu": menu_items,
                "menu_text": menu_text,
                "message": f"Here's our menu:{menu_text}\n\nWhat would you like to order?",
            }
        ).model_dump()
    
    async def _func_add_items(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Add items to the order."""
        items = params.get("items", [])
        current_order = params.get("current_order", [])
        
        added_items = []
        for item in items:
            item_name = item.get("name", "").lower().replace(" ", "_")
            quantity = item.get("quantity", 1)
            
            # Find matching menu item
            for menu_key, menu_item in self.MENU_ITEMS.items():
                if item_name in menu_key or menu_key in item_name or \
                   item_name in menu_item["name"].lower():
                    added_items.append({
                        "name": menu_item["name"],
                        "quantity": quantity,
                        "unit_price": menu_item["price"],
                        "total": round(quantity * menu_item["price"], 2),
                    })
                    break
        
        # Calculate totals
        all_items = current_order + added_items
        subtotal = sum(item["total"] for item in all_items)
        
        if added_items:
            item_names = ", ".join([f"{i['quantity']}x {i['name']}" for i in added_items])
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "added_items": added_items,
                    "current_order": all_items,
                    "subtotal": round(subtotal, 2),
                    "message": f"I've added {item_names} to your order. Would you like anything else?",
                }
            ).model_dump()
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": "I'm sorry, I couldn't find that item on our menu. Could you repeat that?",
                }
            ).model_dump()
    
    async def _func_remove_item(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Remove item from order."""
        item_to_remove = params.get("item_name", "").lower()
        current_order = params.get("current_order", [])
        
        new_order = []
        removed = False
        
        for item in current_order:
            if item_to_remove in item["name"].lower() and not removed:
                removed = True
                continue
            new_order.append(item)
        
        if removed:
            subtotal = sum(item.get("total", item.get("unit_price", 0) * item.get("quantity", 1)) for item in new_order)
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "current_order": new_order,
                    "subtotal": round(subtotal, 2),
                    "message": f"I've removed that item. Your subtotal is now ${subtotal:.2f}. Anything else?",
                }
            ).model_dump()
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": "I couldn't find that item in your order.",
                }
            ).model_dump()
    
    async def _func_get_order_summary(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Get order summary with totals."""
        items = params.get("items", params.get("current_order", []))
        order_type = params.get("order_type", "delivery")
        
        subtotal = sum(
            item.get("total", item.get("unit_price", 0) * item.get("quantity", 1))
            for item in items
        )
        tax = round(subtotal * settings.tax_rate, 2)
        delivery_fee = settings.delivery_fee if order_type == "delivery" else 0
        tip = params.get("tip", 0)
        total = round(subtotal + tax + delivery_fee + tip, 2)
        
        items_text = ", ".join([
            f"{item.get('quantity', 1)}x {item.get('name')}"
            for item in items
        ])
        
        summary = f"Your order: {items_text}. "
        summary += f"Subtotal: ${subtotal:.2f}, Tax: ${tax:.2f}"
        if delivery_fee > 0:
            summary += f", Delivery: ${delivery_fee:.2f}"
        summary += f". Total: ${total:.2f}"
        
        return VapiFunctionResponse(
            result={
                "success": True,
                "items": items,
                "subtotal": subtotal,
                "tax": tax,
                "delivery_fee": delivery_fee,
                "tip": tip,
                "total": total,
                "summary_text": summary,
                "message": summary + ". Is this correct?",
            }
        ).model_dump()
    
    async def _func_confirm_order(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Confirm order details before payment."""
        confirmed = params.get("confirmed", "").lower()
        
        if confirmed in ("yes", "yeah", "correct", "right", "ok", "okay", "confirm", "si", "oui"):
            payment_method = params.get("payment_method", "card")
            
            if payment_method == "cash":
                return VapiFunctionResponse(
                    result={
                        "success": True,
                        "confirmed": True,
                        "payment_method": "cash",
                        "message": "Great! Your order will be ready for cash payment. Can I get your name for the order?",
                        "next_action": "create_order",
                    }
                ).model_dump()
            else:
                return VapiFunctionResponse(
                    result={
                        "success": True,
                        "confirmed": True,
                        "payment_method": "card",
                        "message": "Perfect! I'll send you a secure payment link via text message. Can I confirm your phone number?",
                        "next_action": "process_payment",
                    }
                ).model_dump()
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "confirmed": False,
                    "message": "No problem. What would you like to change?",
                }
            ).model_dump()
    
    async def _func_process_payment(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Process payment or generate payment link."""
        amount = params.get("amount", params.get("total", 0))
        customer_phone = params.get("customer_phone", "")
        customer_email = params.get("customer_email")
        order_summary = params.get("order_summary", "Restaurant Order")
        
        # For phone orders, we send a payment link
        result = await self.notification_service.send_payment_link(
            order_id=0,  # Will be updated when order is created
            customer_email=customer_email,
            customer_phone=customer_phone,
            amount=amount,
            order_summary=order_summary,
        )
        
        if result.success:
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "message": "I've sent a payment link to your phone. Once you complete the payment, your order will be confirmed and sent to the kitchen.",
                    "payment_url": result.payment_url,
                    "payment_link_sent": True,
                }
            ).model_dump()
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": "I'm having trouble sending the payment link. Would you like to pay with cash instead?",
                }
            ).model_dump()
    
    async def _func_create_payment_link(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Generate and send payment link."""
        return await self._func_process_payment(params, language)
    
    async def _func_create_order(
        self,
        params: dict[str, Any],
        db: Optional[AsyncSession],
        call_info: Optional[Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Create the order in the system."""
        if not db:
            return self._error_response("Database unavailable")
        
        try:
            # Extract order data
            order_type_str = params.get("order_type", "delivery").lower()
            order_type = OrderType.PICKUP if order_type_str == "pickup" else OrderType.DELIVERY
            
            customer_name = params.get("customer_name", "Voice Customer")
            customer_phone = params.get("customer_phone", "")
            if not customer_phone and call_info and call_info.customer:
                customer_phone = call_info.customer.number or ""
            
            customer_email = params.get("customer_email")
            
            # Parse items
            items_raw = params.get("items", params.get("current_order", []))
            items = []
            for item in items_raw:
                if isinstance(item, dict):
                    items.append({
                        "name": item.get("name", "Unknown"),
                        "quantity": item.get("quantity", 1),
                        "unit_price": item.get("unit_price", item.get("price", 0)),
                    })
            
            if not items:
                return VapiFunctionResponse(
                    result={
                        "success": False,
                        "message": "I don't have any items in your order. What would you like to order?",
                    }
                ).model_dump()
            
            # Calculate totals
            subtotal = sum(i["quantity"] * i["unit_price"] for i in items)
            tax = round(subtotal * settings.tax_rate, 2)
            delivery_fee = settings.delivery_fee if order_type == OrderType.DELIVERY else 0
            tip = params.get("tip", 0)
            total = round(subtotal + tax + delivery_fee + tip, 2)
            
            # Create order
            items_json = json.dumps(items)
            payment_id = params.get("payment_id", params.get("payment_intent_id"))
            
            new_order = Order(
                order_type=order_type,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
                customer_language=language,
                delivery_address=params.get("delivery_address") if order_type == OrderType.DELIVERY else None,
                city=params.get("city", "New York"),
                state=params.get("state", "NY"),
                zip_code=params.get("zip_code"),
                delivery_instructions=params.get("delivery_instructions"),
                pickup_time=None,  # Parse pickup_time if provided
                items=items_json,
                special_instructions=params.get("special_instructions"),
                subtotal=subtotal,
                tax=tax,
                delivery_fee=delivery_fee,
                tip=tip,
                total_amount=total,
                payment_intent_id=payment_id,
                payment_status="paid" if payment_id else "pending",
                payment_method=params.get("payment_method", "card"),
                status=OrderStatus.PAID if payment_id else OrderStatus.PAYMENT_PENDING,
                call_id=call_info.id if call_info else None,
                call_transcription=params.get("transcription"),
                call_recording_url=params.get("recording_url"),
                handled_by_ai=True,
                transferred_to_human=False,
            )
            
            db.add(new_order)
            await db.commit()
            await db.refresh(new_order)
            
            logger.info(f"Order #{new_order.id} created via voice")
            
            # Queue Excel export
            export_order_to_excel.delay({
                "order_id": new_order.id,
                "order_type": new_order.order_type.value,
                "customer_name": new_order.customer_name,
                "customer_phone": new_order.customer_phone,
                "customer_email": new_order.customer_email,
                "customer_language": new_order.customer_language,
                "delivery_address": new_order.delivery_address,
                "city": new_order.city,
                "zip_code": new_order.zip_code,
                "items": new_order.items,
                "special_instructions": new_order.special_instructions,
                "subtotal": new_order.subtotal,
                "tax": new_order.tax,
                "delivery_fee": new_order.delivery_fee,
                "tip": new_order.tip,
                "total_amount": new_order.total_amount,
                "payment_intent_id": new_order.payment_intent_id,
                "payment_status": new_order.payment_status,
                "order_status": new_order.status.value,
                "call_id": new_order.call_id,
                "call_transcription": new_order.call_transcription,
                "handled_by_ai": new_order.handled_by_ai,
                "created_at": new_order.created_at.isoformat(),
            })
            
            # Send confirmation
            if customer_phone or customer_email:
                await self.notification_service.send_order_confirmation(
                    order_id=new_order.id,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    order_summary=", ".join([f"{i['quantity']}x {i['name']}" for i in items]),
                    total_amount=total,
                    order_type=order_type.value,
                    pickup_time=params.get("pickup_time"),
                    delivery_address=new_order.delivery_address,
                )
            
            # Calculate estimated time
            if order_type == OrderType.PICKUP:
                estimated_time = params.get("pickup_time", "20-30 minutes")
            else:
                estimated_time = f"{settings.estimated_delivery_minutes} minutes"
            
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "message": f"Your order number is {new_order.id}. Your total is ${total:.2f}. Estimated time: {estimated_time}. Thank you for ordering from {settings.restaurant_name}!",
                    "order_id": new_order.id,
                    "total_amount": total,
                    "estimated_time": estimated_time,
                }
            ).model_dump()
            
        except Exception as e:
            logger.exception(f"Error creating order: {e}")
            return self._error_response("I'm sorry, there was a problem placing your order.")
    
    async def _func_transfer_to_human(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Request transfer to human agent."""
        reason = params.get("reason", "Customer requested human agent")
        
        transfer_number = settings.human_transfer_number
        
        if transfer_number:
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "transfer": True,
                    "transfer_number": transfer_number,
                    "message": "I'll transfer you to one of our team members. Please hold.",
                }
            ).model_dump()
        else:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "transfer": False,
                    "message": "I apologize, but all our team members are currently busy. Can I take your number and have someone call you back?",
                }
            ).model_dump()
    
    async def _func_record_message(
        self,
        params: dict[str, Any],
        db: Optional[AsyncSession],
        call_info: Optional[Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Record a message when customer doesn't want to order."""
        if not db:
            return self._error_response("Database unavailable")
        
        try:
            message = params.get("message", params.get("customer_message", ""))
            caller_phone = params.get("caller_phone", "")
            if not caller_phone and call_info and call_info.customer:
                caller_phone = call_info.customer.number or ""
            
            # Create call log
            call_log = CallLog(
                call_id=call_info.id if call_info else f"manual_{datetime.now().timestamp()}",
                caller_phone=caller_phone,
                caller_language=language,
                transcription=params.get("transcription"),
                recording_url=params.get("recording_url"),
                wanted_to_order=False,
                outcome=CallOutcome.NO_ORDER,
                customer_message=message,
                handled_by_ai=True,
            )
            
            db.add(call_log)
            await db.commit()
            
            logger.info(f"Call log created: {call_log.call_id}")
            
            # Queue Excel export for call log
            export_call_log_to_excel.delay({
                "call_id": call_log.call_id,
                "caller_phone": call_log.caller_phone,
                "caller_language": call_log.caller_language,
                "transcription": call_log.transcription,
                "recording_url": call_log.recording_url,
                "outcome": call_log.outcome.value,
                "customer_message": call_log.customer_message,
                "created_at": call_log.created_at.isoformat() if call_log.created_at else datetime.now().isoformat(),
            })
            
            return VapiFunctionResponse(
                result={
                    "success": True,
                    "message": "I've recorded your message. Someone from our team will get back to you. Thank you for calling!",
                }
            ).model_dump()
            
        except Exception as e:
            logger.exception(f"Error recording message: {e}")
            return self._error_response("I'm sorry, I couldn't record your message.")
    
    async def _func_get_order_status(
        self,
        params: dict[str, Any],
        language: str = "en",
    ) -> dict[str, Any]:
        """Check status of an existing order."""
        order_id = params.get("order_id")
        
        if not order_id:
            return VapiFunctionResponse(
                result={
                    "success": False,
                    "message": "What's your order number?",
                }
            ).model_dump()
        
        # In production, query the database
        return VapiFunctionResponse(
            result={
                "success": True,
                "order_id": order_id,
                "status": "preparing",
                "message": f"Order {order_id} is currently being prepared. It should be ready soon!",
            }
        ).model_dump()
    
    # =========================================================================
    # END OF CALL HANDLING
    # =========================================================================
    
    async def _handle_end_of_call(
        self,
        payload: VapiWebhookPayload,
        db: Optional[AsyncSession],
    ) -> dict[str, Any]:
        """Handle end-of-call-report - save transcription and recording."""
        call_id = payload.call.id if payload.call else "unknown"
        
        logger.info(f"Call ended: {call_id}")
        logger.info(f"Duration: {payload.duration_seconds}s")
        logger.info(f"Recording: {payload.recording_url}")
        
        if db and payload.call:
            try:
                # Check if there's an order for this call
                result = await db.execute(
                    select(Order).where(Order.call_id == call_id)
                )
                order = result.scalar_one_or_none()
                
                if order:
                    order.call_transcription = payload.transcript
                    order.call_recording_url = payload.recording_url
                    order.call_duration_seconds = payload.duration_seconds
                    await db.commit()
                    logger.info(f"Updated order #{order.id} with call data")
                
                # Also check call logs
                result = await db.execute(
                    select(CallLog).where(CallLog.call_id == call_id)
                )
                call_log = result.scalar_one_or_none()
                
                if call_log:
                    call_log.transcription = payload.transcript
                    call_log.recording_url = payload.recording_url
                    call_log.call_duration_seconds = payload.duration_seconds
                    call_log.call_ended_at = datetime.now()
                    await db.commit()
                    logger.info(f"Updated call log {call_id}")
                
            except Exception as e:
                logger.error(f"Error updating call data: {e}")
        
        return {"status": "acknowledged"}
    
    async def _handle_status_update(
        self,
        payload: VapiWebhookPayload,
    ) -> dict[str, Any]:
        """Handle call status updates."""
        call_id = payload.call.id if payload.call else "unknown"
        status = payload.status
        
        logger.info(f"Call status: {call_id} -> {status}")
        
        return {"status": "acknowledged"}
    
    async def _handle_transfer_request(
        self,
        payload: VapiWebhookPayload,
        db: Optional[AsyncSession],
    ) -> dict[str, Any]:
        """Handle transfer to human agent."""
        call_id = payload.call.id if payload.call else "unknown"
        
        logger.info(f"Transfer requested for call: {call_id}")
        
        # Update order/call log if exists
        if db:
            try:
                result = await db.execute(
                    select(Order).where(Order.call_id == call_id)
                )
                order = result.scalar_one_or_none()
                
                if order:
                    order.transferred_to_human = True
                    order.status = OrderStatus.TRANSFERRED_TO_HUMAN
                    order.transfer_reason = "AI requested transfer"
                    await db.commit()
                    
            except Exception as e:
                logger.error(f"Error updating transfer status: {e}")
        
        return {
            "transfer": True,
            "transfer_number": settings.human_transfer_number,
        }
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _error_response(self, message: str) -> dict[str, Any]:
        """Create standard error response."""
        return VapiFunctionResponse(
            result={
                "success": False,
                "message": message,
            }
        ).model_dump()


# Singleton instance
_handler_instance: Optional[VapiWebhookHandler] = None


def get_vapi_handler() -> VapiWebhookHandler:
    """Get the Vapi webhook handler instance."""
    global _handler_instance
    
    if _handler_instance is None:
        _handler_instance = VapiWebhookHandler()
    
    return _handler_instance