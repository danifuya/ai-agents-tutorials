"""
Service to queue Celery tasks - integrates with your existing FastAPI routes
"""

import logging
from celery_app import (
    celery_app,
    process_incoming_sms_task,
    publish_job_task,
)
from celery.exceptions import OperationalError

logger = logging.getLogger(__name__)


class CeleryService:
    """Service to handle SMS notification task queueing"""

    def __init__(self, redis_service=None):
        self._celery_app = celery_app
        self._process_incoming_sms_task = process_incoming_sms_task
        self._publish_job_task = publish_job_task
        self._redis_service = redis_service
        self._is_connected = False

    async def initialize(self):
        """Initialize Celery service and test broker connection."""
        logger.info("Celery service initialized, verifying broker connection...")

        try:
            with self._celery_app.broker_connection() as conn:
                conn.ensure_connection(max_retries=3)
            self._is_connected = True
            logger.info("✅ Celery service connected to broker successfully.")

        except OperationalError as e:
            logger.error(f"❌ Celery service failed to connect to broker: {e}")
            self._is_connected = False
        except Exception as e:
            logger.error(
                f"❌ An unexpected error occurred during Celery initialization: {e}"
            )
            self._is_connected = False

    def is_available(self):
        """Check if Celery service is initialized and connected to the broker."""
        return self._celery_app is not None and self._is_connected

    async def queue_sms_processing_debounced(
        self, from_number: str, message_body: str, delay_seconds: int = 22
    ):
        """
        Queues SMS processing with debouncing - cancels previous pending tasks for the same number.
        Waits delay_seconds after the last message before processing.
        """
        if not self.is_available():
            raise RuntimeError("Celery service not initialized")

        try:
            # Create Redis key for tracking pending tasks by phone number
            pending_task_key = f"sms_pending_task:{from_number}"

            # Check if there's already a pending task for this number
            existing_task_id = await self._redis_service.get(pending_task_key)

            if existing_task_id:
                # Revoke without terminating - let both messages be processed naturally
                logger.info(
                    f"🔄 Revoking previous SMS task {existing_task_id} for {from_number} (without terminating)"
                )
                self._celery_app.control.revoke(existing_task_id, terminate=False)

            # Schedule new task with delay
            task = self._process_incoming_sms_task.apply_async(
                args=[from_number, message_body], countdown=delay_seconds
            )

            # Store the new task ID in Redis with expiration
            await self._redis_service.set(
                pending_task_key,
                task.id,
                ex=delay_seconds + 10,  # Expire slightly after the task should execute
            )

            logger.info(
                f"📤 Queued debounced SMS processing task {task.id} from {from_number} (delay: {delay_seconds}s)"
            )
            return {
                "task_id": task.id,
                "status": "queued_debounced",
                "delay_seconds": delay_seconds,
            }

        except Exception as e:
            logger.error(f"Failed to queue debounced SMS processing task: {str(e)}")
            raise

    def queue_publish_job(self, job_id: int):
        """
        Queues a job to be published.
        """
        if not self.is_available():
            raise RuntimeError("Celery service not initialized")

        try:
            task = self._publish_job_task.delay(job_id=job_id)
            logger.info(f"📤 Queued job publishing task {task.id} for job {job_id}")
            return {"task_id": task.id, "status": "queued"}
        except Exception as e:
            logger.error(f"Failed to queue job publishing task: {str(e)}")
            raise

    def get_task_status(self, task_id: str):
        """Get status of a queued task (useful for debugging)"""
        if not self.is_available():
            raise RuntimeError("Celery service not initialized")

        task = self._celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": task.status,
            "result": task.result if task.ready() else None,
            "info": task.info,
        }
