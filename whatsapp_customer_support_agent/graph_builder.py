# src/graph_builder.py
from langgraph.graph import StateGraph, START
from typing import List

from agents.assistant import assistant
from typing import Annotated
from typing_extensions import TypedDict
from pydantic_ai.usage import UsageLimits
from langgraph.types import StreamWriter

# Import the message classes from Pydantic AI
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

MAX_HISTORY_MESSAGES = 7


class ChatbotState(TypedDict):
    latest_user_message: str = ""
    messages: Annotated[List[bytes], lambda x, y: x + y]


async def main_assistant(state: ChatbotState, writer: StreamWriter):
    # Get the message history into the format for Pydantic AI
    message_history: list[ModelMessage] = []

    # Only use the last 7 messages to limit context
    recent_messages = state["messages"][-MAX_HISTORY_MESSAGES:]

    for message_row in recent_messages:
        message_history.extend(ModelMessagesTypeAdapter.validate_json(message_row))

    result = await assistant.run(
        state["latest_user_message"],
        message_history=message_history,
        usage_limits=UsageLimits(request_limit=3),
    )
    writer(result.data)

    return {
        "messages": [result.new_messages_json()],
    }


def build_graph(checkpointer=None):
    graph_builder = StateGraph(ChatbotState)

    graph_builder.add_node("agent", main_assistant)
    graph_builder.add_edge(START, "agent")

    graph = graph_builder.compile(checkpointer=checkpointer)

    return graph
