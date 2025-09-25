import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from msgraph.generated.models.subscription import Subscription
from .graph_service import GraphService


class SubscriptionService:
    """Service class to handle Microsoft Graph subscription operations"""

    def __init__(self, graph_service: GraphService, webhook_url: str, user_id: str):
        self.graph_service = graph_service
        self.webhook_url = webhook_url
        self.user_id = user_id

    async def create_subscription(
        self,
        resource: Optional[str] = None,
        change_types: str = "created",
        expiration_hours: int = 1,
    ) -> Dict[str, Any]:
        """
        Create a Microsoft Graph subscription for Outlook messages

        Args:
            resource: The resource to monitor (defaults to user messages)
            change_types: Types of changes to monitor
            expiration_hours: Hours until subscription expires
        """
        client = self.graph_service.get_client()

        # Use default resource if not provided
        if not resource:
            resource = f"users/{self.user_id}/mailFolders('Inbox')/messages"

        # Create subscription object
        subscription = Subscription()
        subscription.change_type = change_types
        subscription.notification_url = self.webhook_url
        subscription.resource = resource
        subscription.expiration_date_time = datetime.now(timezone.utc) + timedelta(
            hours=expiration_hours
        )
        subscription.client_state = str(uuid.uuid4())  # Random string for validation

        # Create the subscription
        created_subscription = await client.subscriptions.post(subscription)

        return {
            "subscription_id": created_subscription.id,
            "expiration": created_subscription.expiration_date_time,
            "resource": created_subscription.resource,
            "notification_url": created_subscription.notification_url,
            "client_state": created_subscription.client_state,
            "change_type": created_subscription.change_type,
        }

    async def list_subscriptions(self) -> List[Dict[str, Any]]:
        """List all active Microsoft Graph subscriptions"""
        client = self.graph_service.get_client()
        subscriptions = await client.subscriptions.get()

        return [
            {
                "id": sub.id,
                "resource": sub.resource,
                "change_type": sub.change_type,
                "notification_url": sub.notification_url,
                "expiration": sub.expiration_date_time,
                "client_state": sub.client_state,
            }
            for sub in (subscriptions.value or [])
        ]

    async def delete_subscription(self, subscription_id: str) -> Dict[str, str]:
        """Delete a Microsoft Graph subscription"""
        client = self.graph_service.get_client()
        await client.subscriptions.by_subscription_id(subscription_id).delete()

        return {
            "status": "success",
            "message": f"Subscription {subscription_id} deleted",
        }

    async def renew_subscription(
        self, subscription_id: str, expiration_hours: int = 1
    ) -> Dict[str, Any]:
        """Renew an existing subscription"""
        client = self.graph_service.get_client()

        # Update subscription with new expiration
        subscription_update = Subscription()
        subscription_update.expiration_date_time = datetime.now(
            timezone.utc
        ) + timedelta(hours=expiration_hours)

        updated_subscription = await client.subscriptions.by_subscription_id(
            subscription_id
        ).patch(subscription_update)

        return {
            "subscription_id": updated_subscription.id,
            "new_expiration": updated_subscription.expiration_date_time,
            "status": "renewed",
        }
