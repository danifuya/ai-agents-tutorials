from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from dotenv import load_dotenv
from typing import Literal


load_dotenv()
feedback_router = Agent(
    OpenAIModel("gpt-4o-mini"),
    system_prompt="""
    Your task is to route the user message either to the assistant that has to modify the listing information according to the user's feedback or to the assistant that has to insert the listing information into the database.
    To decide which assistant to route the user message to you will have to check the user's message and see if the user is fine with the listing information or not
    """,
    output_type=Literal["rectify_listing", "insert_listing"],
)
