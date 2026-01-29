"""
FastAPI Application Entry Point

AI Restaurant Phone Ordering System with:
- Multi-language voice AI support
- Pickup and Delivery orders
- Human fallback transfer
- Call recording and transcription
- Payment link generation
- Excel logging for all orders and calls

Author: Khalil Bannouri
Version: 3.0.0
"""

import asyncio
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query, Request, Header, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import redis

# Windows event loop fix
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Internal imports
from app.core.config import get_settings, setup_logging
from app.database import get_db, init_db, engine
from app.models import Order, OrderStatus, OrderType, CallLog, CallOutcome
from app.schemas import (
    OrderCreate,
    OrderResponse,
    OrderCreateResponse,
    OrderListResponse,
    CallLogCreate,
    CallLogResponse,
    ErrorResponse,
    HealthResponse,
    SendPaymentLinkRequest,
    NotificationResponse,
    KitchenOrderRequest,
    KitchenOrderResponse,
)
from app.services.payment import get_payment_service
from app.services.geo import get_geo_service
from app.services.notifications import get_notification_service
from app.services.voice import get_vapi_handler, VapiWebhookPayload
from app.tasks import export_order_to_excel, export_call_log_to_excel, send_to_kitchen

# Initialize
settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown."""
    # Startup
    logger.info("=" * 70)
    logger.info(f"🍕 Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"   Environment: {settings.env_mode.value}")
    logger.info(f"   Debug: {settings.debug}")
    logger.info("=" * 70)
    
    await init_db()
    logger.info("✅ Database initialized")
    
    # Log services
    payment = get_payment_service()
    geo = get_geo_service()
    notifications = get_notification_service()
    
    logger.info(f"✅ Payment Service: {payment.provider_name}")
    logger.info(f"✅ Geo Service: {geo.provider_name}")
    logger.info(f"✅ Notification Service: {notifications.provider_name}")
    
    if settings.use_real_services:
        missing = settings.validate_production_config()
        if missing:
            logger.warning(f"⚠️ Missing config: {missing}")
    
    logger.info("=" * 70)
    logger.info("✅ Application ready!")
    logger.info("=" * 70)
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await engine.dispose()
    logger.info("✅ Cleanup complete")


# =============================================================================
# APPLICATION INSTANCE
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    description="AI-powered restaurant phone ordering system with voice AI, payment processing, and kitchen integration.",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_totals(items: list, order_type: str = "delivery", tip: float = 0) -> dict:
    """Calculate order totals."""
    subtotal = sum(item.quantity * item.unit_price for item in items)
    tax = round(subtotal * settings.tax_rate, 2)
    delivery_fee = settings.delivery_fee if order_type == "delivery" else 0
    total = round(subtotal + tax + delivery_fee + tip, 2)
    
    return {
        "subtotal": round(subtotal, 2),
        "tax": tax,
        "delivery_fee": delivery_fee,
        "tip": tip,
        "total_amount": total,
    }


# =============================================================================
# ROOT & HEALTH
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    """API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.env_mode.value,
        "docs": "/docs",
        "dashboard": "/dashboard",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """System health check."""
    
    # Database
    db_status = "healthy"
    try:
        await db.execute(select(func.now()))
    except Exception as e:
        db_status = f"unhealthy: {str(e)[:50]}"
    
    # Redis
    redis_status = "healthy"
    try:
        r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
        r.ping()
        r.close()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)[:50]}"
    
    # Services
    payment = get_payment_service()
    geo = get_geo_service()
    notifications = get_notification_service()
    
    payment_status = "healthy" if await payment.health_check() else "unhealthy"
    geo_status = "healthy" if await geo.health_check() else "unhealthy"
    notification_status = "healthy" if await notifications.health_check() else "unhealthy"
    
    overall = "operational" if all(
        s == "healthy" for s in [db_status, redis_status, payment_status]
    ) else "degraded"
    
    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        payment_service=payment_status,
        geo_service=geo_status,
        notification_service=notification_status,
        timestamp=datetime.now(),
    )


# =============================================================================
# VAPI WEBHOOKS
# =============================================================================

@app.post("/webhook/vapi", tags=["Vapi Webhook"])
async def vapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_vapi_signature: Optional[str] = Header(None, alias="x-vapi-signature"),
):
    """
    Production Vapi.ai webhook endpoint.
    
    Configure in Vapi Dashboard: https://your-domain.com/webhook/vapi
    """
    try:
        body = await request.body()
        payload_dict = await request.json()
        
        logger.info(f"Vapi webhook: {payload_dict.get('type', 'unknown')}")
        
        payload = VapiWebhookPayload(**payload_dict)
        handler = get_vapi_handler()
        response = await handler.handle_webhook(payload, db)
        
        return response
        
    except Exception as e:
        logger.exception(f"Vapi webhook error: {e}")
        return {
            "result": {
                "success": False,
                "message": "Sorry, there was an error. Please try again.",
            }
        }


@app.post("/webhook/simulation", tags=["Simulation"])
async def simulation_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Local testing endpoint (development only).
    Accepts same payload format as Vapi webhook.
    """
    if not settings.is_development:
        raise HTTPException(status_code=403, detail="Only available in development")
    
    try:
        payload_dict = await request.json()
        logger.info(f"Simulation: {payload_dict.get('type', 'unknown')}")
        
        payload = VapiWebhookPayload(**payload_dict)
        handler = get_vapi_handler()
        response = await handler.handle_webhook(payload, db)
        
        return response
        
    except Exception as e:
        logger.exception(f"Simulation error: {e}")
        return {"error": str(e)}


@app.post("/webhook/stripe", tags=["Stripe Webhook"])
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
):
    """
    Stripe payment webhook.
    Handles payment confirmations and updates order status.
    """
    try:
        body = await request.body()
        
        payment_service = get_payment_service()
        event = await payment_service.verify_webhook(body, stripe_signature or "")
        
        if not event:
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        event_type = event.get("type", "")
        
        if event_type == "checkout.session.completed":
            session = event.get("data", {}).get("object", {})
            order_id = session.get("metadata", {}).get("order_id")
            
            if order_id:
                result = await db.execute(
                    select(Order).where(Order.id == int(order_id))
                )
                order = result.scalar_one_or_none()
                
                if order:
                    order.payment_status = "paid"
                    order.payment_intent_id = session.get("payment_intent")
                    order.status = OrderStatus.PAID
                    order.sent_to_kitchen = True
                    order.sent_to_kitchen_at = datetime.now()
                    await db.commit()
                    
                    # Send to kitchen
                    send_to_kitchen.delay({
                        "order_id": order.id,
                        "items": order.items,
                        "order_type": order.order_type.value,
                    })
                    
                    logger.info(f"Order #{order_id} payment confirmed")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.exception(f"Stripe webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ORDER ENDPOINTS
# =============================================================================

@app.post("/api/orders", response_model=OrderCreateResponse, tags=["Orders"])
async def create_order(
    order_data: OrderCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create a new order (direct API)."""
    logger.info(f"Creating {order_data.order_type.value} order for {order_data.customer_name}")
    
    try:
        # Validate address for delivery
        if order_data.order_type == OrderTypeEnum.DELIVERY:
            geo = get_geo_service()
            geo_result = await geo.validate_address(
                address=order_data.delivery_address or "",
                city=order_data.city,
                zip_code=order_data.zip_code or "",
                state=order_data.state,
            )
            
            if not geo_result.is_valid:
                raise HTTPException(status_code=400, detail=geo_result.error_message)
            
            if not geo_result.is_in_delivery_zone:
                raise HTTPException(status_code=400, detail=geo_result.error_message)
            
            formatted_address = geo_result.formatted_address
        else:
            formatted_address = None
        
        # Calculate totals
        totals = calculate_totals(
            order_data.items,
            order_data.order_type.value,
            order_data.tip or 0
        )
        
        # Determine order type enum
        order_type = OrderType.PICKUP if order_data.order_type.value == "pickup" else OrderType.DELIVERY
        
        # Create order
        items_json = json.dumps([
            {"name": i.name, "quantity": i.quantity, "unit_price": i.unit_price}
            for i in order_data.items
        ])
        
        new_order = Order(
            order_type=order_type,
            customer_name=order_data.customer_name,
            customer_phone=order_data.customer_phone,
            customer_email=order_data.customer_email,
            customer_language=order_data.customer_language,
            delivery_address=formatted_address,
            city=order_data.city,
            state=order_data.state,
            zip_code=order_data.zip_code,
            delivery_instructions=order_data.delivery_instructions,
            pickup_time=order_data.pickup_time,
            items=items_json,
            special_instructions=order_data.special_instructions,
            subtotal=totals["subtotal"],
            tax=totals["tax"],
            delivery_fee=totals["delivery_fee"],
            tip=totals["tip"],
            total_amount=totals["total_amount"],
            payment_method=order_data.payment_method,
            status=OrderStatus.PENDING,
            call_id=order_data.call_id,
            call_transcription=order_data.call_transcription,
            call_recording_url=order_data.call_recording_url,
        )
        
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
        
        logger.info(f"Order #{new_order.id} created")
        
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
            "payment_status": new_order.payment_status,
            "order_status": new_order.status.value,
            "call_id": new_order.call_id,
            "call_transcription": new_order.call_transcription,
            "handled_by_ai": new_order.handled_by_ai,
            "created_at": new_order.created_at.isoformat(),
        })
        
        # Calculate estimated time
        if order_type == OrderType.PICKUP:
            estimated = "20-30 minutes"
        else:
            estimated = f"{settings.estimated_delivery_minutes} minutes"
        
        return OrderCreateResponse(
            success=True,
            message="Order created successfully!",
            order_id=new_order.id,
            order_type=new_order.order_type.value,
            total_amount=new_order.total_amount,
            payment_status=new_order.payment_status,
            estimated_time=estimated,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/orders", response_model=OrderListResponse, tags=["Orders"])
async def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    order_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List orders with filters."""
    query = select(Order).order_by(Order.created_at.desc())
    count_query = select(func.count(Order.id))
    
    # Filter by order type
    if order_type:
        try:
            ot = OrderType(order_type.lower())
            query = query.where(Order.order_type == ot)
            count_query = count_query.where(Order.order_type == ot)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid order_type")
    
    # Filter by status
    if status:
        try:
            st = OrderStatus(status.upper())
            query = query.where(Order.status == st)
            count_query = count_query.where(Order.status == st)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    
    # Count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()
    
    return OrderListResponse(
        total=total,
        orders=[OrderResponse.model_validate(o) for o in orders],
    )


@app.get("/api/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    """Get order by ID."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Order #{order_id} not found")
    
    return OrderResponse.model_validate(order)


@app.patch("/api/orders/{order_id}/status", response_model=OrderResponse, tags=["Orders"])
async def update_order_status(
    order_id: int,
    new_status: str,
    db: AsyncSession = Depends(get_db),
):
    """Update order status."""
    try:
        status_enum = OrderStatus(new_status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Order #{order_id} not found")
    
    order.status = status_enum
    
    # Set completion time for final statuses
    if status_enum in [OrderStatus.DELIVERED, OrderStatus.PICKED_UP]:
        order.completed_at = datetime.now()
    
    await db.commit()
    await db.refresh(order)
    
    logger.info(f"Order #{order_id} status updated to {new_status}")
    
    return OrderResponse.model_validate(order)


# =============================================================================
# PAYMENT & NOTIFICATIONS
# =============================================================================

@app.post("/api/orders/{order_id}/send-payment-link", response_model=NotificationResponse, tags=["Payments"])
async def send_payment_link(
    order_id: int,
    request: SendPaymentLinkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send payment link to customer via email/SMS."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Order #{order_id} not found")
    
    notifications = get_notification_service()
    
    items = json.loads(order.items) if order.items else []
    summary = ", ".join([f"{i['quantity']}x {i['name']}" for i in items])
    
    result = await notifications.send_payment_link(
        order_id=order.id,
        customer_email=order.customer_email,
        customer_phone=order.customer_phone,
        amount=order.total_amount,
        order_summary=summary,
    )
    
    if result.success:
        order.payment_link_sent = True
        order.payment_link_url = result.payment_url
        order.status = OrderStatus.PAYMENT_PENDING
        await db.commit()
    
    return NotificationResponse(
        success=result.success,
        message="Payment link sent!" if result.success else "Failed to send",
        email_sent=bool(order.customer_email),
        sms_sent=True,
        payment_link=result.payment_url,
    )


@app.post("/api/orders/{order_id}/send-to-kitchen", response_model=KitchenOrderResponse, tags=["Kitchen"])
async def send_order_to_kitchen(
    order_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Send order to kitchen system."""
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Order #{order_id} not found")
    
    if order.payment_status != "paid" and order.payment_method != "cash":
        raise HTTPException(status_code=400, detail="Order not paid yet")
    
    # Queue kitchen task
    send_to_kitchen.delay({
        "order_id": order.id,
        "order_type": order.order_type.value,
        "items": order.items,
        "special_instructions": order.special_instructions,
    })
    
    order.sent_to_kitchen = True
    order.sent_to_kitchen_at = datetime.now()
    order.status = OrderStatus.PREPARING
    
    # Estimate ready time
    estimated_ready = datetime.now() + timedelta(minutes=20)
    order.estimated_ready_time = estimated_ready
    
    await db.commit()
    
    logger.info(f"Order #{order_id} sent to kitchen")
    
    return KitchenOrderResponse(
        success=True,
        message="Order sent to kitchen!",
        order_id=order.id,
        estimated_ready_time=estimated_ready,
    )


# =============================================================================
# CALL LOGS
# =============================================================================

@app.get("/api/call-logs", tags=["Call Logs"])
async def list_call_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    outcome: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List call logs."""
    query = select(CallLog).order_by(CallLog.created_at.desc())
    
    if outcome:
        try:
            oc = CallOutcome(outcome.lower())
            query = query.where(CallLog.outcome == oc)
        except ValueError:
            pass
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return {
        "total": len(logs),
        "call_logs": [CallLogResponse.model_validate(log) for log in logs],
    }


# =============================================================================
# DASHBOARD
# =============================================================================

@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def dashboard_page(request: Request):
    """Professional dashboard UI."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/dashboard-data", tags=["Dashboard"])
async def dashboard_data(db: AsyncSession = Depends(get_db)):
    """Dashboard statistics."""
    
    # Order counts
    total_result = await db.execute(select(func.count(Order.id)))
    total_orders = total_result.scalar() or 0
    
    # By type
    pickup_result = await db.execute(
        select(func.count(Order.id)).where(Order.order_type == OrderType.PICKUP)
    )
    pickup_orders = pickup_result.scalar() or 0
    
    delivery_result = await db.execute(
        select(func.count(Order.id)).where(Order.order_type == OrderType.DELIVERY)
    )
    delivery_orders = delivery_result.scalar() or 0
    
    # Pending
    pending_result = await db.execute(
        select(func.count(Order.id)).where(
            Order.status.in_([OrderStatus.PENDING, OrderStatus.PAID, OrderStatus.PREPARING])
        )
    )
    pending_orders = pending_result.scalar() or 0
    
    # Completed
    completed_result = await db.execute(
        select(func.count(Order.id)).where(
            Order.status.in_([OrderStatus.DELIVERED, OrderStatus.PICKED_UP])
        )
    )
    completed_orders = completed_result.scalar() or 0
    
    # Today's revenue
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    revenue_result = await db.execute(
        select(func.sum(Order.total_amount)).where(Order.created_at >= today_start)
    )
    today_revenue = revenue_result.scalar() or 0.0
    
    # Average order
    avg_result = await db.execute(select(func.avg(Order.total_amount)))
    avg_order_value = avg_result.scalar() or 0.0
    
    # Call logs count
    calls_result = await db.execute(select(func.count(CallLog.id)))
    total_calls = calls_result.scalar() or 0
    
    # Transferred calls
    transferred_result = await db.execute(
        select(func.count(Order.id)).where(Order.transferred_to_human == True)
    )
    transferred_calls = transferred_result.scalar() or 0
    
    # AI success rate
    ai_handled = total_orders - transferred_calls
    success_rate = round((ai_handled / total_orders * 100) if total_orders > 0 else 100, 1)
    
    # Recent orders
    recent_result = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(10)
    )
    recent_orders = recent_result.scalars().all()
    
    return {
        "total_orders": total_orders,
        "pickup_orders": pickup_orders,
        "delivery_orders": delivery_orders,
        "pending_orders": pending_orders,
        "completed_orders": completed_orders,
        "today_revenue": round(today_revenue, 2),
        "avg_order_value": round(avg_order_value, 2),
        "total_calls": total_calls,
        "transferred_calls": transferred_calls,
        "ai_success_rate": success_rate,
        "environment": settings.env_mode.value,
        "recent_orders": [
            {
                "id": o.id,
                "order_type": o.order_type.value,
                "customer_name": o.customer_name,
                "customer_phone": o.customer_phone,
                "items": o.items,
                "total_amount": o.total_amount,
                "status": o.status.value,
                "handled_by_ai": o.handled_by_ai,
                "created_at": o.created_at.isoformat(),
            }
            for o in recent_orders
        ],
    }


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all error handler."""
    logger.exception(f"Unhandled error: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "detail": str(exc) if settings.debug else "An error occurred",
        },
    )