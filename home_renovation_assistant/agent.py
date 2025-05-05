import os
import base64
import logfire
from typing import Optional, List

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage

# Load environment variables
from dotenv import load_dotenv
import nest_asyncio

load_dotenv()

# Langfuse configuration (commented out but moved here)
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")

LANGFUSE_AUTH = base64.b64encode(
    f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}".encode()
).decode()
os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"{LANGFUSE_HOST}/api/public/otel"
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {LANGFUSE_AUTH}"

nest_asyncio.apply()

# Configure Logfire
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))


# Pydantic model for agent output
class RenovationAssistantOutput(BaseModel):
    next_question: Optional[str] = Field(
        description="Next question to ask the user, or None if the conversation should end"
    )
    is_complete: bool = Field(
        description="Whether the assessment is complete (True) or more questions are needed (False)",
        default=False,
    )


# Initialize agent
renovation_agent = Agent(
    "openai:gpt-4o-mini",
    output_type=RenovationAssistantOutput,
    system_prompt=(
        """You are a professional home renovation assistant. Your goal is to collect detailed information 
        about a client's renovation needs in a professional, concise tone. Ask follow-up questions when 
        needed to get specific details about quantities, dimensions, or specifications. Do not use emojis 
        or slang. 
        Ask simple, short-answer questions covering the following topics:
        1. Areas Involved - Identify which rooms or parts of the home are being considered for renovation.
        2. Purpose or Goals - Define what you hope to accomplish in each space.
        3. Walls and Layout Changes - Determine whether any walls will be moved, added, or removed.
        4. Plumbing and Fixtures - Note any plumbing changes, including fixture additions or relocations.
        5. Electrical Work - Plan for lighting upgrades, new outlets, or smart home features.
        6. Flooring - Decide whether to keep or replace flooring and specify preferred materials.
        7. Windows and Doors - Indicate any replacements or cosmetic updates (e.g., paint, hardware).
        8. Cabinetry and Storage - Clarify if cabinets/vanities will be replaced, refinished, or added.
        9. Countertops - Specify if new countertops are needed and preferred materials.
        10. Appliances and Fixtures - Identify which appliances or fixtures are being replaced or added.
        11. Painting - Confirm if painting is part of the scope (walls, ceilings, trim).
        12. Special Features - List any extra design elements (e.g., shelving, niches, accent walls).
        13. Repairs Needed - Document any existing damage that needs to be fixed.
        14. Style Direction - Describe the general design style (e.g., modern, transitional, traditional).
        15. Budget and Timeline - Provide target budget range, desired start date, and occupancy status.
    
        IMPORTANT INSTRUCTIONS:
        1. You MUST ask at least 15 questions in total before considering the assessment complete
        2. Do NOT number the questions
        3. Do NOT mark the assessment as complete until all 15 questions have been asked and answered
        4. Make questions relevant to the context of the conversation
        5. Do not repeat questions"""
    ),
    instrument=True,
)
