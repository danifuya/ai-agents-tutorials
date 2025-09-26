from fastapi import FastAPI, Request, HTTPException
from typing import Dict, Any
import uvicorn

from config import settings
from services.graph_service import GraphService
from services.subscription_service import SubscriptionService
from services.webhook_service import WebhookService
from services.document_service import DocumentService
from services.agent_service import AgentService

app = FastAPI(title="Outlook Invoice Classifier", version="0.1.0")

# Initialize services with clean dependency injection
graph_service = GraphService(
    client_id=settings.client_id,
    client_secret=settings.client_secret,
    tenant_id=settings.tenant_id
)

subscription_service = SubscriptionService(
    graph_service=graph_service,
    webhook_url=settings.webhook_url,
    user_id=settings.user_id
)

document_service = DocumentService()

agent_service = AgentService(openai_api_key=settings.openai_api_key, local_api_url=settings.local_api_url)

webhook_service = WebhookService(
    graph_service=graph_service,
    document_service=document_service,
    agent_service=agent_service,
    category_name=settings.category_name
)


@app.get("/")
async def root():
    return {"message": "Outlook Invoice Classifier API"}


@app.post("/webhook/outlook")
async def outlook_webhook(request: Request):
    """
    Endpoint to receive Outlook webhook notifications
    Handles both validation requests and actual notifications
    """
    try:
        # Check if this is a validation request (has validationToken query parameter)
        validation_token = request.query_params.get("validationToken")
        if validation_token:
            return await webhook_service.handle_validation(validation_token)

        # Get the raw JSON payload for actual notifications
        payload = await request.json()

        # Process the webhook notification using the service
        return await webhook_service.process_notification(payload)

    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/create-subscription")
async def create_subscription():
    """
    Create a Microsoft Graph subscription for Outlook messages
    """
    try:
        result = await subscription_service.create_subscription()
        return {"status": "success", **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/subscriptions")
async def list_subscriptions():
    """
    List all active Microsoft Graph subscriptions
    """
    try:
        subscriptions = await subscription_service.list_subscriptions()
        return {"status": "success", "subscriptions": subscriptions}
    except Exception as e:
        print(f"Error listing subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/subscription/{subscription_id}")
async def delete_subscription(subscription_id: str):
    """
    Delete a Microsoft Graph subscription
    """
    try:
        return await subscription_service.delete_subscription(subscription_id)
    except Exception as e:
        print(f"Error deleting subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/subscription/{subscription_id}/renew")
async def renew_subscription(subscription_id: str, hours: int = 1):
    """
    Renew a Microsoft Graph subscription
    """
    try:
        return await subscription_service.renew_subscription(subscription_id, hours)
    except Exception as e:
        print(f"Error renewing subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.reload)
