import logging
from psycopg import AsyncConnection
from typing import Any, Optional, List, Dict

from services.justcall_service import JustCallService
from workflows.job_management_workflow import manage_job_from_service_request
from agents.info_collector import info_collector_agent, ServiceRequestInfo
from agents.sms_filter import sms_filter_agent
from agents.sms_replier_agent import sms_replier_agent, SMSReplierDeps
from services.telegram_service import TelegramService
from repositories.job_repository import JobRepository
from repositories.client_repository import ClientRepository
from utils.utils import normalize_phone_number

logger = logging.getLogger(__name__)


async def process_incoming_sms(
    conn: AsyncConnection,
    justcall_service: JustCallService,
    telegram_service: TelegramService,
    from_number: str,
    message_body: str,
    external_conversation_history: Optional[List[Dict[str, str]]] = None,
) -> None:
    """
    Processes an incoming SMS, extracts information, manages the job, and sends a reply.

    Args:
        external_conversation_history: Optional conversation history for forwarded SMS.
                                     Should be in format [{"role": "user", "content": "message"}, ...]
    """
    # Normalize the phone number at the entry point
    normalized_from_number = normalize_phone_number(from_number)
    logger.info(
        f"Processing incoming SMS from {from_number} (normalized: {normalized_from_number}): '{message_body}'"
    )

    # 1. Retrieve conversation history (from external source if provided, otherwise from JustCall)
    if external_conversation_history:
        full_conversation = external_conversation_history
        logger.info(
            f"Using external conversation history with {len(full_conversation)} messages"
        )
    else:
        full_conversation = justcall_service.get_conversation_history(
            normalized_from_number, limit=5, last_minutes=30
        )

    # We create a string representation for the agent
    conversation_str = "\n".join(
        f"[{turn['role']}]: {turn['content']}" for turn in full_conversation
    )

    # 2. Check if client already exists in database (bypass filter for existing clients)
    existing_client = await ClientRepository.get_by_phone(conn, normalized_from_number)
    is_existing_client = existing_client is not None

    if is_existing_client:
        logger.info(
            f"Found existing client for phone {normalized_from_number}: {existing_client.get('first_name', 'Unknown')} {existing_client.get('last_name', '')}"
        )
        is_service_request = True  # Bypass filter for existing clients
    else:
        # 3. Filter out non-service requests for new clients
        sms_filter_response = await sms_filter_agent.run(
            user_prompt=f"Full conversation history:\n{conversation_str}"
        )
        is_service_request = sms_filter_response.output.is_service_request

    if not is_service_request:
        logger.info("⛔ SMS conversation is not related to a service request.")
        return

    # 4. Extract structured information from the conversation (only after filtering)
    info_collector_response = await info_collector_agent.run(
        user_prompt=f"Full conversation history:\n{conversation_str}"
    )
    service_info: ServiceRequestInfo = info_collector_response.output
    logger.info(f"Info extracted from SMS conversation: {service_info}")
    service_info.client_phone_number = normalized_from_number

    # 5. Delegate to the central job management workflow
    management_result = await manage_job_from_service_request(
        conn=conn, service_info=service_info.model_dump()
    )
    logger.info(f"Job management result: {management_result}")

    # 6. Fetch the consolidated job view to identify missing fields and status
    job_id = management_result.get("job_id")
    job_status = None
    missing_fields = []
    if job_id:
        consolidated_view = await JobRepository.get_consolidated_view(conn, job_id)
        logger.debug(f"Consolidated view for job {job_id}: {consolidated_view}")
        if consolidated_view:
            job_status = consolidated_view.get("job_status")
            logger.debug(f"Job status: {job_status}")
            if job_status == "pending_client_info":
                # Map database columns to user-friendly names
                field_map = {
                    "client_first_name": "First Name",
                    "client_last_name": "Last Name",
                    "client_email": "Email Address",
                    "event_date": "Event Date",
                    "start_time": "Start Time",
                    "event_address_street": "Event Street",
                    "event_address_postcode": "Event Postcode",
                    "guest_count": "Number of Guests",
                    "event_type": "Event Type (e.g., wedding, corporate, birthday_party)",
                    "photographer_count": "Number of Photographers",
                    "services": "Services required",
                    "event_duration_hours": "Event Duration (hours)",
                }
                for key, friendly_name in field_map.items():
                    # Check if field is missing
                    value = consolidated_view.get(key)
                    logger.debug(
                        f"Checking field {key}: value={value}, type={type(value)}"
                    )

                    # Field is missing if it's None or empty string (but allow 0, False, and empty arrays)
                    # EXCEPTION: services field is missing if None, empty string, OR empty array
                    if key == "services":
                        is_missing = (
                            value is None
                            or (isinstance(value, str) and value.strip() == "")
                            or (isinstance(value, list) and len(value) == 0)
                        )
                    else:
                        is_missing = value is None or (
                            isinstance(value, str) and value.strip() == ""
                        )

                    if is_missing:
                        missing_fields.append(friendly_name)
                        logger.debug(f"Field marked as missing: {key} = {value}")
                    else:
                        logger.debug(f"Field marked as present: {key} = {value}")

                logger.info(f"Missing fields for job {job_id}: {missing_fields}")

    # 7. Prepare context data for the agent (no prompt building)
    user_prompt = f"Full conversation history:\n{conversation_str}"

    # Convert missing fields to user-friendly format if needed
    if job_status == "pending_client_info" and missing_fields:
        missing_info = missing_fields
    else:
        missing_info = None

    # Pass consolidated_view as job_details for ready_to_post status
    job_details = consolidated_view if job_status == "ready_to_post" else None

    # 7.5. Check for escalation tag - if present, bypass SMS replier and sending
    if justcall_service.escalation_tag_id:
        try:
            thread_tags = justcall_service.get_conversation_thread_tags(
                normalized_from_number
            )
            if justcall_service.escalation_tag_id in thread_tags:
                logger.info(
                    f"Escalation tag {justcall_service.escalation_tag_id} found in conversation with {normalized_from_number}. Bypassing SMS replier and sending."
                )
                return
        except Exception as e:
            logger.warning(
                f"Failed to check thread tags for {normalized_from_number}: {e}. Proceeding with normal SMS flow."
            )

    # 8. Call SMS replier agent with context passed via dependencies
    logger.info(
        f"Calling SMS replier agent with job_status: {job_status}, job_id: {job_id}"
    )
    sms_replier_response = await sms_replier_agent.run(
        user_prompt=user_prompt,
        deps=SMSReplierDeps(
            telegram_service=telegram_service,
            justcall_service=justcall_service,
            connection=conn,
            phone_number=normalized_from_number,
            telegram_chat_ids=telegram_service.target_chat_ids,
            job_id=job_id or 0,
            job_status=job_status,
            job_details=job_details,
            missing_info=missing_info,
        ),
    )

    reply_text = sms_replier_response.output

    if reply_text:
        justcall_service.send_sms(to=normalized_from_number, body=reply_text)
        logger.info(
            f"Generated and sent reply for {normalized_from_number}: '{reply_text}'"
        )
