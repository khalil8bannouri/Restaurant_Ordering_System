"""
Celery Tasks
Background tasks for processing orders asynchronously.
"""

from app.celery_worker import celery_app
from app.services.excel_manager import ExcelManager
from datetime import datetime
import time


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    autoretry_for=(Exception,),
    retry_backoff=True
)
def export_order_to_excel(self, order_data: dict) -> dict:
    """
    Export order to Excel file.
    This task runs asynchronously via Celery worker.
    
    Args:
        order_data: Dictionary containing order information
        
    Returns:
        dict: Result of the export operation
    """
    task_id = self.request.id
    order_id = order_data.get('order_id', 'unknown')
    
    print(f"📋 Task {task_id}: Processing order #{order_id}")
    start_time = time.time()
    
    try:
        # Export to Excel using the manager
        result = ExcelManager.export_order(order_data)
        
        elapsed = round(time.time() - start_time, 3)
        result['task_id'] = task_id
        result['processing_time_seconds'] = elapsed
        
        if result['success']:
            print(f"✅ Task {task_id}: Order #{order_id} completed in {elapsed}s")
        else:
            print(f"⚠️ Task {task_id}: Order #{order_id} failed - {result['message']}")
        
        return result
        
    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        print(f"❌ Task {task_id}: Order #{order_id} error after {elapsed}s - {str(e)}")
        
        # Celery will auto-retry based on configuration
        raise


@celery_app.task
def health_check() -> dict:
    """
    Simple health check task to verify Celery is working.
    """
    return {
        'status': 'healthy',
        'worker': 'celery',
        'timestamp': datetime.now().isoformat()
    }


@celery_app.task
def clear_excel_file() -> dict:
    """
    Clear the Excel file (for testing/reset purposes).
    """
    success = ExcelManager.clear_all_orders()
    return {
        'success': success,
        'message': 'Excel file cleared' if success else 'Failed to clear Excel file',
        'timestamp': datetime.now().isoformat()
    }