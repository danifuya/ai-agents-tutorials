import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from app.agents.replier import replier_agent
from app.rag.retrieval.hierarchical_retrieval import HierarchicalRetrieval
from app.rag.retrieval.query_processing import QueryProcessor
from app.db.connection import DatabaseService

router = APIRouter()
logger = logging.getLogger(__name__)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class MessageEvent(BaseModel):
    message: str
    event_type: str = "chat_message"
    timestamp: str = None
    context: dict = None


async def process_message_event(event: MessageEvent):
    logger.info(f"Processing event: {event.event_type} with message: {event.message}")

    # Hybrid retrieval - get relevant chunks for the user message
    db_service = DatabaseService()
    await db_service.initialize()

    try:
        async with db_service.get_connection() as conn:
            # Initialize retrieval components
            query_processor = QueryProcessor(embedding_provider="openai")
            retrieval_engine = HierarchicalRetrieval(
                db_connection=conn,
                stage1_similarity_threshold=0.3,
                stage1_document_limit=10,
                stage2_chunk_limit=5,
            )

            # Process the user query
            processed_query = query_processor.process_query(event.message)
            logger.info(f"Query processed in {processed_query.processing_time:.3f}s")

            # Run hierarchical retrieval
            retrieval_result = await retrieval_engine.search(
                processed_query.embedding, processed_query.cleaned_text
            )
            logger.info(
                f"Retrieved {retrieval_result.total_chunks_found} chunks in {retrieval_result.total_time:.3f}s"
            )

            # Format retrieved chunks as string
            chunks_text = ""
            if retrieval_result.chunks:
                for i, chunk in enumerate(retrieval_result.chunks, 1):
                    chunks_text += f"\n--- Fragment {i} (Document: {chunk['document_title']}) ---\n"
                    chunks_text += chunk["content"]
                    chunks_text += "\n"
            else:
                chunks_text = "No relevant information was found in the analysis."

            # Create combined prompt
            combined_prompt = f"User question: '{event.message}'\n\nRelevant information from the analysis:{chunks_text}"

    except Exception as e:
        logger.error(f"Retrieval failed: {e}")
        combined_prompt = f"User question: '{event.message}'\n\nRelevant information from the analysis: Could not access analysis information due to a technical error."

    finally:
        await db_service.close()

    # Pass the combined prompt to the replier agent
    replier_response = await replier_agent.run(user_prompt=combined_prompt)

    # Return format expected by assistant-ui
    return {
        "message": replier_response.output,
        "event_metadata": {
            "event_type": "chat_response",
            "original_event": event.model_dump(),
            "retrieval_info": {
                "chunks_found": len(retrieval_result.chunks)
                if "retrieval_result" in locals()
                else 0,
                "total_documents_searched": getattr(
                    retrieval_result, "total_documents_searched", 0
                )
                if "retrieval_result" in locals()
                else 0,
            },
        },
    }


@router.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
        logger.info(f"Received request body: {body}")

        # Handle both formats for flexibility
        if "messages" in body:
            messages = body["messages"]
            last_user_message = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    # Handle assistant-ui format where content is array of objects
                    if isinstance(content, list) and len(content) > 0:
                        for item in content:
                            if item.get("type") == "text":
                                last_user_message = item.get("text", "")
                                break
                    elif isinstance(content, str):
                        last_user_message = content
                    break
        else:
            last_user_message = body.get("message", "hi")
            messages = []

        if not last_user_message:
            last_user_message = "hi"

        event = MessageEvent(
            message=last_user_message, context={"full_conversation": messages}
        )

        response = await process_message_event(event)
        return response
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
