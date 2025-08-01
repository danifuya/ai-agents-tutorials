import logging
from psycopg import AsyncConnection
from datetime import datetime

from repositories.job_repository import JobRepository
from repositories.client_repository import ClientRepository
from repositories.service_repository import JobServiceRepository
from utils.service_mapper import ServiceMapper

logger = logging.getLogger(__name__)


async def _handle_services(conn: AsyncConnection, job_id: int, service_info: dict):
    """Handle services for the job."""
    service_codes = service_info.get("services", [])

    # Convert service codes to service IDs
    service_ids = await ServiceMapper.get_service_ids_by_codes(conn, service_codes)

    if not service_ids:
        logger.warning(f"No valid services found for job {job_id}")
        return

    # Prepare service data (no individual service durations)
    service_data = []
    for service_id in service_ids:
        service_data.append(
            {
                "service_id": service_id,
            }
        )

    # Update job services using the enhanced repository method
    await JobServiceRepository.update_job_services(conn, job_id, service_data)
    logger.info(f"Updated services for job {job_id}: {len(service_data)} services")


async def _queue_job_publication(job_id: int):
    """Initializes Celery and queues a job for publication."""
    from services.celery_service import CeleryService

    celery_service = CeleryService()
    await celery_service.initialize()
    celery_service.queue_publish_job(job_id)


async def confirm_job_for_applications(conn: AsyncConnection, job_id: int) -> bool:
    """
    Confirms a job for applications by validating status, generating job_code, publishing, and updating to applications_open.

    Args:
        conn: Database connection
        job_id: ID of the job to confirm

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get current job status and details
        job = await JobRepository.get_by_id(conn, job_id)

        if not job:
            logger.error(
                f"Job {job_id} not found when trying to confirm for applications"
            )
            return False

        current_status = job.get("job_status")

        # Only proceed if job status is ready_to_post
        if current_status != "ready_to_post":
            logger.error(
                f"Job {job_id} status is '{current_status}', expected 'ready_to_post'"
            )
            return False

        # Get consolidated view to access client information
        consolidated_job = await JobRepository.get_consolidated_view(conn, job_id)
        if not consolidated_job:
            logger.error(f"Could not get consolidated view for job {job_id}")
            return False

        # Generate job_code: DDMM + FirstName (e.g., 2201Matt)
        event_date = consolidated_job.get("event_date")
        client_first_name = consolidated_job.get("client_first_name", "")

        if not event_date:
            logger.error(
                f"Cannot confirm job {job_id}: missing event_date required for job_code generation"
            )
            return False

        if not client_first_name:
            logger.error(
                f"Cannot confirm job {job_id}: missing client_first_name required for job_code generation"
            )
            return False

        # Parse event_date and extract day and month
        try:
            if isinstance(event_date, str):
                # Parse string date format (YYYY-MM-DD)
                date_parts = event_date.split("-")
                if len(date_parts) >= 3:
                    day = date_parts[2].zfill(2)  # Ensure 2 digits
                    month = date_parts[1].zfill(2)  # Ensure 2 digits
                else:
                    raise ValueError(f"Invalid date format: {event_date}")
            else:
                # If event_date is already a date/datetime object
                day = event_date.strftime("%d")
                month = event_date.strftime("%m")
        except (ValueError, AttributeError, IndexError) as e:
            logger.error(
                f"Cannot confirm job {job_id}: failed to parse event_date '{event_date}': {str(e)}"
            )
            return False

        # Create job_code: DDMM + FirstName
        base_job_code = f"{day}{month}{client_first_name}"

        # Check if job_code already exists in database
        existing_job = await JobRepository.get_by_code(conn, base_job_code)
        if existing_job and existing_job.get("job_id") != job_id:
            # If duplicate exists and it's not the same job, append client_id
            client_id = consolidated_job.get("client_id") or job.get("client_id")
            job_code = f"{base_job_code}{client_id}"
            logger.info(
                f"Job code '{base_job_code}' already exists, using '{job_code}' instead"
            )
        else:
            job_code = base_job_code

        # Update job with the new job_code
        update_data = {"job_code": job_code}
        await JobRepository.update(conn, job_id, update_data)
        logger.info(f"Updated job {job_id} with job_code: {job_code}")

        # Queue job for publication
        await _queue_job_publication(job_id)
        logger.info(f"Job {job_id} queued for publication")

        return True

    except Exception as e:
        logger.error(f"Error confirming job {job_id} for applications: {str(e)}")
        return False


async def manage_job_from_service_request(
    conn: AsyncConnection, service_info: dict
) -> dict:
    """
    Handles the core business logic for creating or updating a job from a service request.
    This workflow is channel-agnostic (works for email, SMS, etc.).

    Args:
        conn: An active database connection.
        service_info: A dictionary containing structured data extracted from the user's message.
                      Expected keys include: client_email, client_first_name, event_date, etc.


    Returns:
        A dictionary containing the result of the operation (e.g., job_id, status).
    """
    logger.info(
        f"Managing job based on service info for client: {service_info.get('client_email')}"
    )

    # === Step 1: Identify the job to update ===
    job_to_update = None
    if service_info.get("service_id"):
        logger.info(f"🔎 Found Reference ID: {service_info['service_id']}")
        job_to_update = await JobRepository.get_by_id(
            conn, job_id=service_info["service_id"]
        )
    else:
        client_jobs = await JobRepository.get_by_client_phone_or_email(
            conn,
            phone_number=service_info.get("client_phone_number"),
            email=service_info.get("client_email"),
        )
        if client_jobs:
            try:
                service_event_date = service_info.get("event_date")

                # If all existing jobs for the client are completed, we should create a new one.
                if all(job.get("job_status") == "completed" for job in client_jobs):
                    job_to_update = None
                    logger.info(
                        "All existing jobs are completed. A new job will be created."
                    )
                else:
                    # If an event date is provided, try to match with it first.
                    if service_event_date:
                        for job in client_jobs:
                            job_date = job.get("event_date")
                            if (
                                job.get("job_status") == "pending_client_info"
                                and str(job_date) == service_event_date
                            ):
                                job_to_update = job
                                logger.info(
                                    f"🗓️ Matched pending job {job['job_id']} by event date: {service_event_date}"
                                )
                                break

                    # If no specific job was matched by date, fall back to finding the first pending job.
                    if not job_to_update:
                        for job in client_jobs:
                            if job.get("job_status") == "pending_client_info":
                                job_to_update = job
                                logger.info(
                                    f"🗓️ Matched first available pending job {job['job_id']} (no date match)."
                                )
                                break

                        # If there's still no pending job, re-open the one with the highest ID
                        # unless it is already completed.
                        if not job_to_update and client_jobs:
                            latest_job = max(
                                client_jobs, key=lambda job: job.get("job_id", 0)
                            )
                            if latest_job.get("job_status") != "completed":
                                job_to_update = latest_job
                                logger.info(
                                    f"Re-opening latest job {job_to_update['job_id']} as no pending job was found."
                                )

            except (ValueError, TypeError, KeyError):
                logger.warning("Could not parse event date from provided info.")

    # === Step 2: Handle job based on status ===
    if job_to_update:
        job_status = job_to_update.get("job_status")

        # We still proceed to update the job with any new information provided.
        if job_status not in ["pending_client_info", "ready_to_post"]:
            logger.info(
                f"⏭️ Job {job_to_update['job_id']} has status '{job_status}'. No action needed."
            )
            return {
                "job_status": job_status,  # Return the job's actual status
                "job_id": job_to_update["job_id"],
            }

    # === Step 3: Find or create client ===
    client = await ClientRepository.get_by_phone_or_email(
        conn,
        phone=service_info.get("client_phone_number"),
        email=service_info.get("client_email"),
    )

    client_id = client["client_id"] if client else None
    if not client:
        client_id = await ClientRepository.create(
            conn,
            first_name=service_info.get("client_first_name"),
            last_name=service_info.get("client_last_name"),
            email=service_info.get("client_email"),
            phone=service_info.get("client_phone_number"),
        )
        logger.info(f"Created new client with ID: {client_id}")
    elif client:
        logger.info(f"Found existing client with ID: {client_id}")

        # Update client details if new information is provided by info collector
        client_update_data = {}
        if service_info.get("client_first_name"):
            client_update_data["first_name"] = service_info.get("client_first_name")
        if service_info.get("client_last_name"):
            client_update_data["last_name"] = service_info.get("client_last_name")
        if service_info.get("client_email"):
            client_update_data["email_address"] = service_info.get("client_email")
        if service_info.get("client_phone_number"):
            client_update_data["phone_number"] = service_info.get("client_phone_number")

        if client_update_data:
            await ClientRepository.update(conn, client_id, client_update_data)
            logger.info(
                f"Updated client {client_id} with new information: {list(client_update_data.keys())}"
            )

    # === Step 4: Create or Update Job and determine reply ===
    update_data = {}
    if service_info.get("event_date"):
        update_data["event_date"] = service_info.get("event_date")
    if service_info.get("start_time"):
        update_data["event_start_time"] = service_info.get("start_time")
    if service_info.get("event_address_street"):
        update_data["event_address_street"] = service_info.get("event_address_street")
    if service_info.get("event_address_suburb"):
        update_data["event_address_suburb"] = service_info.get("event_address_suburb")
    if service_info.get("event_address_state"):
        update_data["event_address_state"] = service_info.get("event_address_state")
    if service_info.get("event_address_postcode"):
        update_data["event_address_postcode"] = service_info.get(
            "event_address_postcode"
        )
    if service_info.get("guest_count"):
        update_data["guest_count"] = service_info.get("guest_count")
    if service_info.get("event_type"):
        update_data["event_type"] = service_info.get("event_type")
    if service_info.get("photographer_count"):
        update_data["photographer_count"] = service_info.get("photographer_count")
    if service_info.get("event_duration_hours"):
        update_data["event_duration_hours"] = service_info.get("event_duration_hours")

    # Check if all required fields are present instead of relying on AI
    if (
        service_info.get("client_first_name")
        and service_info.get("client_last_name")
        and service_info.get("client_email")
        and service_info.get("event_date")
        and service_info.get("start_time")
        and (
            service_info.get("event_address_suburb")
            or service_info.get("event_address_state")
        )
        and service_info.get("guest_count")
        and service_info.get("event_type")
        and service_info.get("photographer_count")
        and service_info.get("services")
    ):
        logger.info(f"✅ Service request is complete.")
        update_data["job_status"] = "ready_to_post"
        if job_to_update:
            job_id = job_to_update["job_id"]
            await JobRepository.update(conn, job_id, update_data)
            logger.info(f"✅ Updated job {job_id} to 'ready_to_post'.")
        else:
            job_code = f"{datetime.now().strftime('%Y%m%d%H%M%S')}"
            update_data["job_code"] = job_code
            update_data["client_id"] = client_id
            job_id = await JobRepository.create(conn, update_data)
            logger.info(f"✅ Created new job {job_id} with status 'ready_to_post'.")

        # Handle services - convert service codes to service IDs and persist to job_services table with durations
        if service_info.get("services"):
            try:
                await _handle_services(conn, job_id, service_info)
                logger.info(
                    f"✅ Updated services for job {job_id}: {len(service_info['services'])} services"
                )
            except Exception as e:
                logger.error(f"Error updating services for job {job_id}: {str(e)}")

        # In a real scenario, you'd call a shared "send_confirmation" function here
        # that could handle email or SMS. For now, we return the state.
        return {"job_status": "ready_to_post", "job_id": job_id}

    else:
        logger.info("ℹ️ Service request is not complete.")
        update_data["job_status"] = "pending_client_info"
        job_id_for_reply = None
        if job_to_update:
            job_id_for_reply = job_to_update["job_id"]
            await JobRepository.update(conn, job_id_for_reply, update_data)
            logger.info(
                f"✅ Updated pending job {job_id_for_reply} with new partial info."
            )
        else:
            job_code = f"{datetime.now().strftime('%Y%m%d%H%M')}"
            update_data["job_code"] = job_code
            update_data["client_id"] = client_id
            job_id_for_reply = await JobRepository.create(conn, update_data)
            logger.info(
                f"✅ Created new job {job_id_for_reply} with status 'pending_client_info'."
            )

        # Handle services even for pending jobs - store partial service information
        if service_info.get("services"):
            try:
                await _handle_services(conn, job_id_for_reply, service_info)
                logger.info(
                    f"✅ Updated services for pending job {job_id_for_reply}: {len(service_info['services'])} services"
                )
            except Exception as e:
                logger.error(
                    f"Error updating services for pending job {job_id_for_reply}: {str(e)}"
                )

        # In a real scenario, you'd call a shared "request_more_info" function.
        return {"job_status": "pending_client_info", "job_id": job_id_for_reply}
