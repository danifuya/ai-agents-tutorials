from pydantic_ai import Agent
from pydantic import BaseModel, Field

import logfire

logfire.configure()


class SMSClassification(BaseModel):
    is_service_request: bool = Field(
        description="True if the SMS is a request from a client to book a photography service, False otherwise"
    )


# Define the email classification agent
sms_filter_agent = Agent(
    # You'll need to specify an LLM here, e.g., 'openai:gpt-3.5-turbo'
    # For now, I'll leave it as a placeholder.
    model="openai:gpt-4o-mini",
    output_type=SMSClassification,
    system_prompt="""You are an AI assistant that routes SMS conversations to the appropriate workflow.
    You are receiving SMS messages sent to the contact number of a professional photography agency.
    Your task is to filter conversations from clients who want to book photography services from those contacting for other purposes (e.g. spam, marketing, wrong numbers, etc.).
    If the conversation is related to a photography service request, respond with is_service_request as true otherwise set it as false.
    When it's not clear what the conversation is about and could potentially be a photography service request, respond with is_service_request as true.
""",
    instrument=True,
)
