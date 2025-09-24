from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from typing import Dict, Any
import uvicorn
import os
from dotenv import load_dotenv
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential
from msgraph.generated.subscriptions.subscriptions_request_builder import (
    SubscriptionsRequestBuilder,
)
from msgraph.generated.models.subscription import Subscription
from datetime import datetime, timedelta
import uuid
from datetime import timezone

load_dotenv()

app = FastAPI(title="Outlook Invoice Classifier", version="0.1.0")

# Microsoft Graph configuration
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TENANT_ID = os.getenv("TENANT_ID")
USER_ID = os.getenv("USER_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")


def get_graph_client():
    """Initialize Microsoft Graph client with app-only authentication"""
    if not all([CLIENT_ID, CLIENT_SECRET, TENANT_ID]):
        raise ValueError(
            "Missing required environment variables: CLIENT_ID, CLIENT_SECRET, TENANT_ID"
        )

    credential = ClientSecretCredential(
        tenant_id=TENANT_ID, client_id=CLIENT_ID, client_secret=CLIENT_SECRET
    )

    scopes = ["https://graph.microsoft.com/.default"]
    return GraphServiceClient(credentials=credential, scopes=scopes)


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
            print(f"Received validation request with token: {validation_token}")
            # Return the validation token as plain text for Microsoft Graph validation
            return Response(content=validation_token, media_type="text/plain")

        # Get the raw JSON payload for actual notifications
        payload = await request.json()

        # Log the received webhook data
        print(f"Received Outlook webhook: {payload}")

        # Process the webhook notification
        # This is where you'll add your message processing logic

        return {"status": "success", "message": "Webhook received"}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/create-subscription")
async def create_subscription():
    """
    Create a Microsoft Graph subscription for Outlook messages
    """
    try:
        if not WEBHOOK_URL:
            raise HTTPException(status_code=400, detail="WEBHOOK_URL not configured")

        graph_client = get_graph_client()

        # Create subscription object
        subscription = Subscription()
        subscription.change_type = "created,updated"
        subscription.notification_url = WEBHOOK_URL
        if not USER_ID or USER_ID == "your_user_id_here":
            raise HTTPException(status_code=400, detail="USER_ID not configured in .env file")

        subscription.resource = f"users/{USER_ID}/messages"
        subscription.expiration_date_time = datetime.now(timezone.utc) + timedelta(
            hours=1
        )  # 1 hour expiry
        subscription.client_state = str(uuid.uuid4())  # Random string for validation

        # Create the subscription
        created_subscription = await graph_client.subscriptions.post(subscription)

        return {
            "status": "success",
            "subscription_id": created_subscription.id,
            "expiration": created_subscription.expiration_date_time,
            "resource": created_subscription.resource,
            "notification_url": created_subscription.notification_url,
            "client_state": created_subscription.client_state,
        }

    except Exception as e:
        print(f"Error creating subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/subscriptions")
async def list_subscriptions():
    """
    List all active Microsoft Graph subscriptions
    """
    try:
        graph_client = get_graph_client()
        subscriptions = await graph_client.subscriptions.get()

        return {
            "status": "success",
            "subscriptions": [
                {
                    "id": sub.id,
                    "resource": sub.resource,
                    "change_type": sub.change_type,
                    "notification_url": sub.notification_url,
                    "expiration": sub.expiration_date_time,
                }
                for sub in (subscriptions.value or [])
            ],
        }

    except Exception as e:
        print(f"Error listing subscriptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/subscription/{subscription_id}")
async def delete_subscription(subscription_id: str):
    """
    Delete a Microsoft Graph subscription
    """
    try:
        graph_client = get_graph_client()
        await graph_client.subscriptions.by_subscription_id(subscription_id).delete()

        return {
            "status": "success",
            "message": f"Subscription {subscription_id} deleted",
        }

    except Exception as e:
        print(f"Error deleting subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
