"""
FastAPI Application Entry Point

AI Restaurant Ordering System - Hybrid Architecture
Supports both Mock services (development) and Real APIs (production).

Endpoints:
    - POST /webhook/vapi: Real Vapi.ai webhook endpoint
    - POST /webhook/simulation: Local testing endpoint
    - POST /api/orders: Direct order creation
    - GET /api/orders: List orders
    - GET /dashboard: Professional dashboard UI
    - GET /health: System health check

Author: Your Name
Version: 2.0.0
"""

import asyncio
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Query, Request, Header
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import redis

# Windows-specific event loop policy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Internal imports
from app.core.config import get_settings, setup_logging
from app.database import get_db, init_db, engine
from app.models import Order, OrderStatus
from app.schemas import (
    OrderCreate,
    OrderResponse,
    OrderCreateResponse,
    OrderListResponse,
    ErrorResponse,
    HealthResponse,
)
from app.services.payment import get_payment_service
from app.services.geo import get_geo_service
from app.services.voice import get_vapi_handler, VapiWebhookPayload
from app.tasks import export_order_to_excel

# Initialize configuration and logging
settings = get_settings()
setup_logging()
logger = logging.getLogger(__name__)

# Template configuration
templates = Jinja2Templates(directory="app/templates")


# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.
    """
    # Startup
    logger.info("=" * 60)
    logger.info(f"🚀 Starting {settings.app_name}")
    logger.info(f"   Version: {settings.app_version}")
    logger.info(f"   Environment: {settings.env_mode.value}")
    logger.info(f"   Debug: {settings.debug}")
    logger.info("=" * 60)
    
    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")
    
    # Log service configuration
    payment_service = get_payment_service()
    geo_service = get_geo_service()
    logger.info(f"✅ Payment Service: {payment_service.provider_name}")
    logger.info(f"✅ Geo Service: {geo_service.provider_name}")
    
    # Validate production config
    if settings.use_real_services:
        missing = settings.validate_production_config()
        if missing:
            logger.warning(f"⚠️ Missing production config: {missing}")
    
    logger.info("=" * 60)
    logger.info("✅ Application ready!")
    logger.info("=" * 60)
    
    yield  # Application runs
    
    # Shutdown
    logger.info("Shutting down...")
    await engine.dispose()
    logger.info("✅ Cleanup complete")


# =============================================================================
# APPLICATION INSTANCE
# =============================================================================

app = FastAPI(
    title=settings.app_name,
    description=(
        "High-concurrency AI voice ordering system with hybrid architecture. "
        "Supports both mock services for development and real APIs for production."
    ),
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_order_totals(items: list) -> dict[str, float]:
    """Calculate order subtotal, tax, and total."""
    subtotal = sum(item.quantity * item.unit_price for item in items)
    tax = round(subtotal * settings.tax_rate, 2)
    total = round(subtotal + tax + settings.delivery_fee, 2)
    
    return {
        "subtotal": round(subtotal, 2),
        "tax": tax,
        "delivery_fee": settings.delivery_fee,
        "total_amount": total,
    }


# =============================================================================
# ROOT & HEALTH ENDPOINTS
# =============================================================================

@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """API root with navigation links."""
    return {
        "message": f"🍕 Welcome to {settings.app_name}",
        "version": settings.app_version,
        "environment": settings.env_mode.value,
        "documentation": "/docs",
        "dashboard": "/dashboard",
        "health": "/health",
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="System Health Check",
)
async def health_check(
    db: AsyncSession = Depends(get_db)
) -> HealthResponse:
    """Verify all system components are operational."""
    
    # Check database
    db_status = "healthy"
    try:
        await db.execute(select(func.now()))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
        logger.error(f"Database health check failed: {e}")
    
    # Check Redis
    redis_status = "healthy"
    try:
        r = redis.Redis(host="localhost", port=6379, socket_timeout=2)
        r.ping()
        r.close()
    except Exception as e:
        redis_status = f"unhealthy: {str(e)}"
        logger.error(f"Redis health check failed: {e}")
    
    # Check payment service
    payment_service = get_payment_service()
    payment_status = "healthy" if await payment_service.health_check() else "unhealthy"
    
    # Check geo service
    geo_service = get_geo_service()
    geo_status = "healthy" if await geo_service.health_check() else "unhealthy"
    
    overall = "operational" if all(
        s == "healthy" for s in [db_status, redis_status, payment_status, geo_status]
    ) else "degraded"
    
    return HealthResponse(
        status=overall,
        database=db_status,
        redis=redis_status,
        timestamp=datetime.now(),
    )


# =============================================================================
# VAPI WEBHOOK ENDPOINTS
# =============================================================================

@app.post(
    "/webhook/vapi",
    tags=["Vapi Webhook"],
    summary="Vapi.ai Webhook Endpoint",
)
async def vapi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_vapi_signature: Optional[str] = Header(None, alias="x-vapi-signature"),
) -> dict[str, Any]:
    """
    Handle incoming webhooks from Vapi.ai.
    
    This is the production endpoint that Vapi calls when:
    - AI needs to execute a function (check_address, process_payment, etc.)
    - Call ends (end-of-call-report)
    - Call status changes
    
    Configure this URL in your Vapi dashboard:
        https://your-domain.com/webhook/vapi
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Parse payload
        payload_dict = await request.json()
        
        logger.info(f"Vapi webhook received: {payload_dict.get('type', 'unknown')}")
        logger.debug(f"Payload: {json.dumps(payload_dict, indent=2)}")
        
        # Parse into schema
        try:
            payload = VapiWebhookPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Failed to parse Vapi payload: {e}")
            return {"error": "Invalid payload format"}
        
        # Handle the webhook
        handler = get_vapi_handler()
        response = await handler.handle_webhook(payload, db)
        
        logger.debug(f"Vapi response: {response}")
        return response
        
    except Exception as e:
        logger.exception(f"Error processing Vapi webhook: {e}")
        return {
            "result": {
                "success": False,
                "message": "Sorry, there was an error processing your request.",
            }
        }


@app.post(
    "/webhook/simulation",
    tags=["Simulation"],
    summary="Simulation Webhook (Development)",
)
async def simulation_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Simulation endpoint for local testing.
    
    Accepts the same payload format as the real Vapi webhook,
    allowing you to test the complete flow locally without
    needing a real Vapi account.
    
    Use simulation.py to send test payloads to this endpoint.
    """
    if not settings.is_development:
        raise HTTPException(
            status_code=403,
            detail="Simulation endpoint only available in development mode"
        )
    
    try:
        payload_dict = await request.json()
        
        logger.info(f"Simulation webhook: {payload_dict.get('type', 'unknown')}")
        
        payload = VapiWebhookPayload(**payload_dict)
        handler = get_vapi_handler()
        response = await handler.handle_webhook(payload, db)
        
        return response
        
    except Exception as e:
        logger.exception(f"Simulation error: {e}")
        return {"error": str(e)}


# =============================================================================
# ORDER API ENDPOINTS
# =============================================================================

@app.post(
    "/api/orders",
    response_model=OrderCreateResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["Orders"],
    summary="Create Order (Direct API)",
)
async def create_order(
    order_data: OrderCreate,
    db: AsyncSession = Depends(get_db),
) -> OrderCreateResponse:
    """
    Create a new order via direct API call.
    
    This endpoint is for direct integrations (web app, mobile app).
    For voice orders, use the /webhook/vapi endpoint.
    """
    logger.info(f"Creating order for: {order_data.customer_name}")
    
    try:
        # Validate address
        geo_service = get_geo_service()
        geo_result = await geo_service.validate_address(
            address=order_data.delivery_address,
            city=order_data.city,
            zip_code=order_data.zip_code,
        )
        
        if not geo_result.is_valid:
            raise HTTPException(
                status_code=400,
                detail=geo_result.error_message or "Invalid address"
            )
        
        if not geo_result.is_in_delivery_zone:
            raise HTTPException(
                status_code=400,
                detail=geo_result.error_message or "Address outside delivery zone"
            )
        
        # Calculate totals
        totals = calculate_order_totals(order_data.items)
        
        # Process payment
        payment_service = get_payment_service()
        payment_result = await payment_service.process_payment(
            amount=totals["total_amount"],
            customer_name=order_data.customer_name,
            customer_email=None,
        )
        
        if not payment_result.success:
            raise HTTPException(
                status_code=400,
                detail=payment_result.error_message or "Payment failed"
            )
        
        # Create order
        items_json = json.dumps([
            {
                "name": item.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in order_data.items
        ])
        
        new_order = Order(
            customer_name=order_data.customer_name,
            customer_phone=order_data.customer_phone,
            delivery_address=geo_result.formatted_address or order_data.delivery_address,
            city=order_data.city,
            zip_code=order_data.zip_code,
            items=items_json,
            special_instructions=order_data.special_instructions,
            subtotal=totals["subtotal"],
            tax=totals["tax"],
            delivery_fee=totals["delivery_fee"],
            total_amount=totals["total_amount"],
            payment_intent_id=payment_result.payment_intent_id,
            payment_status="paid",
            status=OrderStatus.PAID,
        )
        
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
        
        logger.info(f"Order #{new_order.id} created successfully")
        
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
        
        estimated = datetime.now() + timedelta(minutes=settings.estimated_delivery_minutes)
        
        return OrderCreateResponse(
            success=True,
            message="Order placed successfully!",
            order_id=new_order.id,
            total_amount=new_order.total_amount,
            estimated_delivery=estimated.strftime("%I:%M %p"),
            payment_status="paid",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/orders",
    response_model=OrderListResponse,
    tags=["Orders"],
    summary="List Orders",
)
async def list_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> OrderListResponse:
    """Retrieve paginated list of orders."""
    
    query = select(Order).order_by(Order.created_at.desc())
    count_query = select(func.count(Order.id))
    
    if status:
        try:
            status_enum = OrderStatus(status.upper())
            query = query.where(Order.status == status_enum)
            count_query = count_query.where(Order.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Options: {[s.value for s in OrderStatus]}"
            )
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    orders = result.scalars().all()
    
    return OrderListResponse(
        total=total,
        orders=[OrderResponse.model_validate(order) for order in orders],
    )


@app.get(
    "/api/orders/{order_id}",
    response_model=OrderResponse,
    tags=["Orders"],
)
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    """Get a specific order by ID."""
    
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail=f"Order #{order_id} not found")
    
    return OrderResponse.model_validate(order)


# =============================================================================
# DASHBOARD ENDPOINTS
# =============================================================================

@app.get(
    "/dashboard",
    response_class=HTMLResponse,
    tags=["Dashboard"],
)
async def dashboard_page(request: Request) -> HTMLResponse:
    """Serve the professional dashboard UI."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get(
    "/api/dashboard-data",
    tags=["Dashboard"],
)
async def dashboard_data(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get aggregated dashboard statistics."""
    
    # Counts
    total_result = await db.execute(select(func.count(Order.id)))
    total_orders = total_result.scalar() or 0
    
    pending_result = await db.execute(
        select(func.count(Order.id)).where(
            Order.status.in_([OrderStatus.PENDING, OrderStatus.PAID])
        )
    )
    pending_orders = pending_result.scalar() or 0
    
    delivered_result = await db.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatus.DELIVERED)
    )
    delivered_orders = delivered_result.scalar() or 0
    
    # Today's revenue
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    revenue_result = await db.execute(
        select(func.sum(Order.total_amount)).where(Order.created_at >= today_start)
    )
    today_revenue = revenue_result.scalar() or 0.0
    
    # Average order value
    avg_result = await db.execute(select(func.avg(Order.total_amount)))
    avg_order_value = avg_result.scalar() or 0.0
    
    # Success rate
    failed_result = await db.execute(
        select(func.count(Order.id)).where(Order.status == OrderStatus.FAILED)
    )
    failed_orders = failed_result.scalar() or 0
    success_rate = (
        round(((total_orders - failed_orders) / total_orders * 100), 1)
        if total_orders > 0 else 100.0
    )
    
    # Recent orders
    recent_result = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(10)
    )
    recent_orders = recent_result.scalars().all()
    
    return {
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "delivered_orders": delivered_orders,
        "today_revenue": round(today_revenue, 2),
        "avg_order_value": round(avg_order_value, 2),
        "success_rate": success_rate,
        "environment": settings.env_mode.value,
        "recent_orders": [
            {
                "id": o.id,
                "customer_name": o.customer_name,
                "customer_phone": o.customer_phone,
                "items": o.items,
                "total_amount": o.total_amount,
                "status": o.status.value,
                "created_at": o.created_at.isoformat(),
            }
            for o in recent_orders
        ],
    }


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all exception handler."""
    logger.exception(f"Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )