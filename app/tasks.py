"""
Celery Background Tasks

Handles asynchronous tasks for:
- Excel export of orders
- Excel export of call logs
- Sending notifications
- Kitchen order forwarding

Author: Khalil Bannouri
Version: 3.0.0
"""

from typing import Any
from datetime import datetime
import time
import logging

from app.celery_worker import celery_app
from app.services.excel_manager import ExcelManager

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="tasks.export_order_to_excel",
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def export_order_to_excel(
    self,
    order_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Export order to Excel file.
    Uses FileLock to prevent race conditions.
    """
    task_id = self.request.id or "unknown"
    order_id = order_data.get("order_id", 0)
    start_time = time.time()
    
    logger.info(f"Task {task_id}: Exporting Order #{order_id} to Excel")
    
    try:
        result = ExcelManager.export_order(order_data)
        
        elapsed = round(time.time() - start_time, 3)
        result["task_id"] = task_id
        result["processing_time_seconds"] = elapsed
        
        if result["success"]:
            logger.info(f"Task {task_id}: Order #{order_id} exported in {elapsed}s")
        else:
            logger.warning(f"Task {task_id}: Order #{order_id} failed - {result.get('message')}")
        
        return result
        
    except Exception as exc:
        logger.exception(f"Task {task_id}: Order #{order_id} error - {exc}")
        raise


@celery_app.task(
    bind=True,
    name="tasks.export_call_log_to_excel",
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(Exception,),
    retry_backoff=True,
)
def export_call_log_to_excel(
    self,
    call_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Export call log to Excel file.
    For calls that don't result in orders.
    """
    task_id = self.request.id or "unknown"
    call_id = call_data.get("call_id", "unknown")
    start_time = time.time()
    
    logger.info(f"Task {task_id}: Exporting Call Log {call_id} to Excel")
    
    try:
        result = ExcelManager.export_call_log(call_data)
        
        elapsed = round(time.time() - start_time, 3)
        result["task_id"] = task_id
        result["processing_time_seconds"] = elapsed
        
        if result["success"]:
            logger.info(f"Task {task_id}: Call Log {call_id} exported in {elapsed}s")
        else:
            logger.warning(f"Task {task_id}: Call Log {call_id} failed")
        
        return result
        
    except Exception as exc:
        logger.exception(f"Task {task_id}: Call Log {call_id} error - {exc}")
        raise


@celery_app.task(name="tasks.health_check")
def health_check() -> dict[str, Any]:
    """Verify Celery worker is running."""
    return {
        "status": "healthy",
        "worker": "celery",
        "timestamp": datetime.now().isoformat()
    }


@celery_app.task(name="tasks.send_to_kitchen")
def send_to_kitchen(order_data: dict[str, Any]) -> dict[str, Any]:
    """
    Forward order to kitchen system.
    In production, this would integrate with POS/KDS.
    """
    order_id = order_data.get("order_id")
    
    logger.info(f"Sending Order #{order_id} to kitchen")
    
    # Mock kitchen integration
    # In production: Call POS API, send to printer, etc.
    
    return {
        "success": True,
        "order_id": order_id,
        "sent_at": datetime.now().isoformat(),
        "message": "Order sent to kitchen"
    }