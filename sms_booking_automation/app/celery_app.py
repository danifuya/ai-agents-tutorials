from celery import Celery
import os
import logging
from services.database_service import DatabaseService
from dotenv import load_dotenv
import asyncio

# Imports for SMS task
from services.justcall_service import JustCallService
from workflows.sms_workflow import process_incoming_sms
from services.telegram_service import TelegramService
from repositories.job_repository import JobRepository
from repositories.service_repository import JobServiceRepository


load_dotenv()
logger = logging.getLogger(__name__)


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_DB = os.getenv("REDIS_DB", 0)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Construct Redis URL based on whether a password is provided
if REDIS_PASSWORD:
    REDIS_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
else:
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"


# Celery app configuration
celery_app = Celery("photography_booking_processor")

celery_app.conf.update(
    broker_url=REDIS_URL,
    result_backend=REDIS_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=1,  # Sequential processing - no race conditions
    task_routes={
        "sms_processor.*": {"queue": "sms_queue"},
        "job_publishing.*": {"queue": "job_publishing_queue"},
    },
)


@celery_app.task(bind=True, name="sms_processor.process_incoming_message")
def process_incoming_sms_task(self, from_number: str, message_body: str):
    """
    Celery task to process an incoming SMS message. It creates its own
    service instances to run reliably in a worker.
    """

    async def async_task_logic():
        db_service = DatabaseService()
        justcall_service = JustCallService()
        telegram_service = TelegramService()
        try:
            # Initialize services at the start of the task.
            await db_service.initialize(max_size=1)

            logger.info(
                f"💬 Starting Celery task for SMS from: {from_number}, message: {message_body}"
            )

            # Get a database connection and run the core logic in a transaction
            async with db_service.get_connection() as conn:
                async with conn.transaction():
                    await process_incoming_sms(
                        conn=conn,
                        justcall_service=justcall_service,
                        telegram_service=telegram_service,
                        from_number=from_number,
                        message_body=message_body,
                    )

            logger.info("✅ Celery task completed for SMS")
            return {"status": "success", "from_number": from_number}

        except Exception as e:
            logger.error(f"❌ Celery SMS task failed: {e}", exc_info=True)
            # Retry with exponential backoff on failure.
            raise self.retry(exc=e, countdown=60, max_retries=3)
        finally:
            # CRITICAL: Ensure connections are closed to prevent leaks.
            if db_service.is_available():
                await db_service.close()
            logger.info("SMS task finished, resources closed.")

    try:
        return asyncio.run(async_task_logic())
    except Exception as e:
        logger.error(f"Celery task 'process_incoming_sms_task' failed: {e}")
        raise


@celery_app.task(bind=True, name="job_publishing.publish_job")
def publish_job_task(self, job_id: int):
    """
    Celery task to publish a job to Telegram.
    """

    async def async_task_logic():
        db_service = DatabaseService()
        telegram_service = TelegramService()
        try:
            await db_service.initialize(max_size=1)
            logger.info(f"📢 Starting job publishing task for job_id: {job_id}")

            async with db_service.get_connection() as conn:
                async with conn.transaction():
                    job = await JobRepository.get_by_id(conn, job_id)
                    if not job:
                        logger.error(f"Job with id {job_id} not found.")
                        return

                    if job.get("job_status") != "ready_to_post":
                        logger.warning(
                            f"Job {job_id} is not ready to post. Status: {job.get('job_status')}"
                        )
                        return

                    event_date = job.get("event_date")
                    formatted_date = (
                        event_date.strftime("%A, %dTH %B %Y").upper()
                        if event_date
                        else "N/A"
                    )

                    # Format time without seconds
                    event_time = job.get("event_start_time")
                    formatted_time = (
                        event_time.strftime("%H:%M") if event_time else "N/A"
                    )

                    # Format event type - remove underscores and use proper case
                    event_type_raw = job.get("event_type", "").lower()
                    if event_type_raw == "wedding":
                        event_type_formatted = "Wedding"
                    elif event_type_raw == "corporate":
                        event_type_formatted = "Corporate Event"
                    elif event_type_raw == "birthday_party":
                        event_type_formatted = "Birthday Party"
                    else:
                        event_type_formatted = event_type_raw.replace("_", " ").title()

                    people_label = "Attendees"

                    # Get photographer count for display
                    photographer_count = job.get("photographer_count", 1)

                    # Format photographer count label
                    photographer_label = f"{photographer_count} Photographer{'s' if photographer_count > 1 else ''}"

                    # Fetch services and pricing from job_services table
                    job_services = await JobServiceRepository.get_by_job_id(
                        conn, job_id
                    )

                    services_with_pricing = []

                    for job_service in job_services:
                        service_name = job_service.get(
                            "service_name", "Unknown Service"
                        )
                        base_price = job_service.get("base_price") or 0.0

                        # Calculate service price (base_price * photographer_count)
                        service_total = base_price * photographer_count
                        services_with_pricing.append(
                            f"{service_name} - ${service_total:.0f} + each"
                        )

                    services_str = (
                        "\n".join(services_with_pricing)
                        if services_with_pricing
                        else "N/A"
                    )

                    # Format event duration if available
                    event_duration = job.get("event_duration_hours")
                    duration_str = ""
                    if event_duration:
                        hours = int(event_duration)
                        minutes = int((event_duration - hours) * 60)
                        if hours > 0 and minutes > 0:
                            duration_str = f"⏱️ Duration: {hours}h {minutes}min\n"
                        elif hours > 0:
                            duration_str = f"⏱️ Duration: {hours}h\n"
                        elif minutes > 0:
                            duration_str = f"⏱️ Duration: {minutes}min\n"

                    message = (
                        f"🗓️ {formatted_date}\n"
                        f"📍 {job.get('event_address_suburb', 'N/A').capitalize()}\n"
                        f"⏰ {formatted_time}\n"
                        f"{duration_str}"
                        f"📸 {photographer_label}\n\n"
                        f"✨ Services:\n{services_str}\n\n"
                        f"{event_type_formatted} | {job.get('guest_count', 'N/A')} {people_label}\n"
                        f"🆔 {job.get('job_code', 'N/A')} - Portfolio Required\n"
                        f"@photoproagency\n\n"
                    )

                    telegram_service.send_message_to_targets(text=message)
                    logger.info(f"✅ Job {job_id} published to Telegram.")

                    # Update job status to 'applications_open'
                    await JobRepository.update(
                        conn, job_id, {"job_status": "applications_open"}
                    )
                    logger.info(
                        f"✅ Job {job_id} status updated to 'applications_open'."
                    )

        except Exception as e:
            logger.error(f"❌ Job publishing task failed: {e}", exc_info=True)
            raise self.retry(exc=e, countdown=300, max_retries=3)
        finally:
            if db_service.is_available():
                await db_service.close()
            logger.info("Job publishing task finished, resources closed.")

    try:
        return asyncio.run(async_task_logic())
    except Exception as e:
        logger.error(f"Celery task 'publish_job_task' failed: {e}")
        raise
