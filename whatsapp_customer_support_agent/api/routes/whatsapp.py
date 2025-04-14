from fastapi import APIRouter, Request, HTTPException, Query
from api.services.whatsapp_service import send_whatsapp_message
import os
from dotenv import load_dotenv
from main import run_agent
from fastapi.background import BackgroundTasks


load_dotenv()

router = APIRouter()
MAX_MESSAGE_LENGTH = 2000


@router.post("/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    # Parse the request body
    data = await request.json()

    # Immediately queue the processing task and return 200
    # Process the message asynchronously after responding
    background_tasks.add_task(process_whatsapp_message, data)

    # Return 200 OK immediately to acknowledge receipt
    return {"status": "received"}


async def process_whatsapp_message(data: dict):
    # Extract message updates
    entry = data.get("entry", [{}])[0]
    changes = entry.get("changes", [{}])[0]
    value = changes.get("value", {})
    print(f"Value: {value}")
    # ✅ Filter out system events (Only process if 'messages' exists)
    if "messages" not in value:
        return

    messages = value["messages"]
    if not messages:
        return
    # Extract user message
    message = messages[0]
    from_number = message["from"]
    user_text = message["text"]["body"]
    print(f"User text: {user_text}")
    # Check message length
    if len(user_text) > MAX_MESSAGE_LENGTH:
        send_whatsapp_message(
            to=from_number,
            body=f"Your message is too long. Please send a shorter message.",
        )
        return {"status": "message_too_long"}

    # Process chatbot pipeline
    response = await run_agent(user_text, from_number)
    # Send the response
    send_whatsapp_message(to=from_number, body=response)


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return int(hub_challenge)
    else:
        raise HTTPException(status_code=403, detail="Verification failed")
