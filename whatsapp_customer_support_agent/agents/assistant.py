from pydantic_ai.models.openai import OpenAIModel
import openai
import os

from database.pg_vector import SupabaseVectorDB  # Use absolute import
import logfire
from pydantic_ai import Agent

from dotenv import load_dotenv
from pydantic_ai.exceptions import UsageLimitExceeded

load_dotenv()
logfire.configure(token=os.getenv("LOGFIRE_TOKEN"))
logfire.instrument_openai()


# Example node function
model = OpenAIModel("gpt-4o-mini")


# System prompt to guide the LLM's behavior
system_prompt = """You are a technical support assistant.
1. Check if you need additional information to resolve the user's query.
2. If the user has a problem, consult get_common_problems_and_solutions to obtain common problems and solutions to respond to them.
3. When responding to the user, first identify the problem and reply with one step at a time. Do not mix steps from different solutions.
4. If the problem persists, tell the user that you will escalate the issue to a human technician.
5. To format text on WhatsApp and make it clearer or more expressive, you can use the following format:
- Bold, enclose the text in asterisks, e.g. *this text*
- Italics, use underscores, e.g. _this text_
"""


assistant = Agent(
    model,
    system_prompt=system_prompt,
    model_settings={"temperature": 0.0, "max_tokens": 500},
)


@assistant.tool_plain
def get_common_problems_and_solutions(query: str) -> str:
    """
    Returns relevant technical support information, such as common problems and solutions.

    Args:
        query (str): The user's query.

    Returns:
        str: Content of relevant technical support information.
    """
    db = SupabaseVectorDB()

    # Now we search in the new `documents_code` table

    try:
        # Initialize OpenAI embeddings
        client = openai.OpenAI()

        # Create embedding for the query
        query_response = client.embeddings.create(
            model="text-embedding-3-small", input=query
        )

        query_embedding = query_response.data[0].embedding

        # Create a PGVector-based vector store
        docs = db.search_similar_in_my_embeddings(query_embedding, top_k=3)

        # Combine results into a single string
        results = []
        for doc in docs:
            results.append(doc["text_content"])  # or doc.get('content')

        return "\n\n---\n\n".join(results)
    except UsageLimitExceeded as e:
        return (
            f"Error retrieving technical support info, tool usage limit exceeded: {e}"
        )
    except Exception as e:
        return f"Error retrieving technical support info: {e}"
