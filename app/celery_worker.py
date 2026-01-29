"""
Celery Worker Configuration
Sets up Celery with Redis as message broker and result backend.
"""

from celery import Celery
import os

# Redis connection URL
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
celery_app = Celery(
    'restaurant_worker',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks']  # Module containing our tasks
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Process one task at a time
    worker_concurrency=4,  # Number of worker processes
    
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    
    # Task execution settings
    task_acks_late=True,  # Acknowledge task after completion
    task_reject_on_worker_lost=True,  # Requeue task if worker dies
    
    # Fix for Celery 6.0 warning
    broker_connection_retry_on_startup=True,
)


if __name__ == '__main__':
    celery_app.start()