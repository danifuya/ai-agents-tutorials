import os

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel, Field
from dataclasses import dataclass
from typing import Union, Literal, Optional, Any

from services.telegram_service import TelegramService
from services.justcall_service import JustCallService, JustCallServiceError
from workflows.job_management_workflow import confirm_job_for_applications

import logging

logger = logging.getLogger(__name__)

import logfire

logfire.configure()


@dataclass
class SMSReplierDeps:
    telegram_service: TelegramService
    justcall_service: JustCallService
    connection: Any
    phone_number: str
    job_id: Optional[int] = None
    job_status: Optional[str] = None
    job_details: Optional[dict] = None
    missing_info: Optional[list[str]] = None


class ServiceScenario(BaseModel):
    scenario_type: Literal["information_provided", "about_services", "other"] = Field(
        description="The scenario type of the conversation"
    )


# Define the email classification agent
sms_replier_agent = Agent(
    # You'll need to specify an LLM here, e.g., 'openai:gpt-3.5-turbo'
    # For now, I'll leave it as a placeholder.
    model="openai:gpt-4o",
    deps_type=SMSReplierDeps,
    output_type=str,
    instructions="""You are an AI assistant that helps clients book professional photography services for their events.
    You will receive an SMS conversation between a client and an agent representative of the photography agency.
    You will also received the job_id of the service request and additional information about the service request.
    Your task is to reply to the client based on the conversation history.
    When conversation is starting, mention that you are the PhotoPro AI Assistant so that the client knows that you are the AI assistant and not a human agent and that you are here to help them book their photography service.
    Your primary goal is to be helpful. Always prioritize answering the client's most recent question directly before asking for missing information.
    Crucially, NEVER invent, assume, or hallucinate any information not present in the conversation history or provided data (e.g., booking details, pricing, photographer availability, platform features like an app). If you do not know the answer to a question, you MUST escalate to a human agent using the escalate_request tool.
    When jobStatus is pending_client_info, your task is to help the client get his questions answered, and only then, ask for the missing information.
    When jobStatus is ready_to_post, if the user provides clear confirmation (e.g. "yes", "confirm the booking"), you must call the confirm_service_request tool and then tell the client they will receive photographer applications shortly. Do not ask for confirmation again.If the client expresses hesitation (e.g., "let me think about it"), acknowledge this and wait for their next message. Do not pressure them to confirm.
    When client asks questions that are not related, escalate service request to a human agent using the escalate_request tool and tell the client that you will get back to them shortly. Do not ask for confirmation again.
    You MUST escalate to a human agent using escalate_request tool when the client asks complex questions (e.g. about pricing, cancellation policy, a previous complaint, specific photographer availability, or technical platform questions), makes inquiries that seem suspicious, or explicitly asks for a human. When escalating, tell the client that a human will get in touch. Do not tell the client to check a website or contact support themselves.
    If confirmation details have been sent in previous messages, do not repeat them. Just ask the client to confirm the details.
    If tool confirm_service_request fails, escalate to a human agent and tell the client that you will get back to them shortly.
    
    When you tell the client that you have escalated the request to a human agent, you MUST use the escalate_request tool.
    Keep your responses concise and avoid using markdown formatting like asterisks. When asking for multiple pieces of information, always present them as a list. For addresses, use the format: Street, Suburb, State, Postcode.

""",
    instrument=True,
)


@sms_replier_agent.instructions
def add_job_details_to_prompt(ctx: RunContext[SMSReplierDeps]) -> str:
    """Build detailed context prompt for the SMS replier agent."""
    prompt_parts = []

    # Add job status information
    if ctx.deps.job_status:
        prompt_parts.append(
            f"Current job status is '{ctx.deps.job_status}' for reference ID {ctx.deps.job_id}."
        )

    # Add missing fields information for pending_client_info cases
    if ctx.deps.job_status == "pending_client_info" and ctx.deps.missing_info:
        missing_fields_str = ", ".join(ctx.deps.missing_info)
        prompt_parts.append(f"Missing booking information: {missing_fields_str}.")

    # Add formatted job details for ready_to_post cases
    elif ctx.deps.job_status == "ready_to_post" and ctx.deps.job_details:
        job_details_prompt = _format_job_details_for_prompt(ctx.deps.job_details)
        if job_details_prompt:
            prompt_parts.append(job_details_prompt)

    return "\n\n".join(prompt_parts) if prompt_parts else ""


def _format_job_details_for_prompt(job_details):
    """Format job details for the agent prompt, similar to SMS workflow."""
    if not job_details:
        return ""

    formatted_details = []

    # Client details
    if job_details.get("client_first_name"):
        client_name = job_details["client_first_name"]
        if job_details.get("client_last_name"):
            client_name += f" {job_details['client_last_name']}"
        formatted_details.append(f"Client: {client_name}")

    if job_details.get("client_email"):
        formatted_details.append(f"Email: {job_details['client_email']}")
    if job_details.get("client_phone_number"):
        formatted_details.append(f"Phone: {job_details['client_phone_number']}")

    # Event details
    if job_details.get("event_date"):
        formatted_details.append(f"Event Date: {job_details['event_date']}")
    if job_details.get("start_time"):
        formatted_details.append(f"Start Time: {job_details['start_time']}")
    if job_details.get("guest_count"):
        formatted_details.append(f"Number of Guests: {job_details['guest_count']}")
    if job_details.get("event_type"):
        formatted_details.append(
            f"Event Type (wedding, corporate, party, etc.): {job_details['event_type']}"
        )
    if job_details.get("performer_count"):
        formatted_details.append(
            f"Number of Photographers Needed: {job_details['performer_count']}"
        )

    # Address
    address_parts = []
    if job_details.get("event_address_street"):
        address_parts.append(job_details["event_address_street"])
    if job_details.get("event_address_suburb"):
        address_parts.append(job_details["event_address_suburb"])
    if job_details.get("event_address_state"):
        address_parts.append(job_details["event_address_state"])
    if job_details.get("event_address_postcode"):
        address_parts.append(job_details["event_address_postcode"])
    if address_parts:
        formatted_details.append(f"Address: {', '.join(address_parts)}")

    # Services
    if job_details.get("services") and job_details["services"]:
        services_str = ", ".join(job_details["services"])
        formatted_details.append(f"Services: {services_str}")

    # Service durations
    if job_details.get("service_durations") and job_details["service_durations"]:
        durations_list = []
        for service, duration in job_details["service_durations"].items():
            durations_list.append(f"{service}: {duration} hours")
        if durations_list:
            formatted_details.append(f"Service Durations: {', '.join(durations_list)}")

    if formatted_details:
        return f"Booking details:\n" + "\n".join(formatted_details)

    return ""


@sms_replier_agent.tool
def escalate_request(ctx: RunContext[SMSReplierDeps], escalation_message: str) -> str:
    """
    Escalate the request to a human agent.

    escalation_message: short message send to the human agent to explain the situation.
    """
    if ctx.deps.telegram_service is None:
        logger.error(
            "Cannot escalate request: telegram_service is None (evaluation mode)"
        )
        return "Request escalated to a human agent."

    try:
        # Send Telegram notification
        ctx.deps.telegram_service.send_message(
            chat_id="1706006925",
            text=f"🚨 Request escalated for client number: {ctx.deps.phone_number} \n\n Escalation message: {escalation_message}",
        )

        # Mark conversation as escalated in JustCall if service is available
        if ctx.deps.justcall_service is not None:
            try:
                escalate_success = ctx.deps.justcall_service.escalate_conversation(
                    ctx.deps.phone_number
                )
                if escalate_success:
                    logger.info(
                        f"Successfully marked conversation as escalated: {ctx.deps.phone_number}"
                    )
                else:
                    logger.warning(
                        f"Failed to mark conversation as escalated: {ctx.deps.phone_number}"
                    )
            except Exception as escalate_error:
                logger.error(
                    f"Error marking conversation as escalated for {ctx.deps.phone_number}: {str(escalate_error)}"
                )
        else:
            logger.warning(
                "Cannot mark conversation as escalated: justcall_service is None (evaluation mode)"
            )

        logger.info(f"Successfully escalated request for {ctx.deps.phone_number}")
        return "Request escalated to a human agent."
    except Exception as e:
        logger.error(
            f"Failed to escalate request for {ctx.deps.phone_number}: {str(e)}"
        )
        # Still return success message to avoid confusing the agent
        # The error is logged for debugging but we don't want the agent to know about technical failures
        return "Request escalated to a human agent."


@sms_replier_agent.tool
async def confirm_service_request(ctx: RunContext[SMSReplierDeps]) -> str:
    """
    This tool is used to confirm the service request after the client has confirmed the details.

    return: "Service request confirmed." or "Could not confirm service request"
    """
    if ctx.deps.job_id is None:
        return "Could not confirm service request"

    try:
        success = await confirm_job_for_applications(
            ctx.deps.connection, ctx.deps.job_id
        )

        if success:
            return "Service request confirmed."
        else:
            return "Could not confirm service request"
    except Exception as e:
        logger.error(
            f"Error confirming service request for job {ctx.deps.job_id}: {str(e)}"
        )
        return "Could not confirm service request"


@sms_replier_agent.tool
async def send_services_info(ctx: RunContext[SMSReplierDeps]) -> str:
    """
    This tool is used to send 3 photography service infographics to the client with the services and prices that can be booked.

    return: "Services information sent." or "Could not send services information"
    """
    if ctx.deps.job_id is None:
        logger.error("Cannot send services info: job_id is None")
        return "Could not send services information"

    if ctx.deps.justcall_service is None:
        logger.error(
            "Cannot send services info: justcall_service is None (evaluation mode)"
        )
        return "Could not send services information"

    try:
        # Define the paths to the 3 service images (relative to app directory)
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        image_paths = [os.path.join(app_dir, "assets", "services", "service1.jpeg")]

        # Check if all images exist (this check is now also done in JustCallService)
        missing_images = [path for path in image_paths if not os.path.exists(path)]
        if missing_images:
            logger.error(f"Service images not found: {missing_images}")
            return "Could not send services information"

        # Send MMS with service images and body text
        message_id = ctx.deps.justcall_service.send_mms(
            to=ctx.deps.phone_number,
            body="Photography Services:",
            attachments=image_paths,
        )

        logger.info(
            f"Successfully sent service infographics to {ctx.deps.phone_number}, message_id: {message_id}"
        )
        return "Services information sent."

    except JustCallServiceError as e:
        logger.error(
            f"JustCall service error sending infographics to {ctx.deps.phone_number}: {str(e)}"
        )
        return "Could not send services information"
    except Exception as e:
        logger.error(
            f"Unexpected error sending service infographics to {ctx.deps.phone_number}: {str(e)}"
        )
        return "Could not send services information"
