from typing import Optional
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential
from msgraph.generated.models.message import Message
from msgraph.generated.models.outlook_category import OutlookCategory
from msgraph.generated.models.category_color import CategoryColor


class GraphService:
    """Service class to handle Microsoft Graph API operations"""

    def __init__(self, client_id: str, client_secret: str, tenant_id: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self._client: Optional[GraphServiceClient] = None

    def get_client(self) -> GraphServiceClient:
        """Get Microsoft Graph client with app-only authentication"""
        if self._client is None:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            scopes = ["https://graph.microsoft.com/.default"]
            self._client = GraphServiceClient(credentials=credential, scopes=scopes)

        return self._client

    async def get_user_messages(self, user_id: str, limit: int = 10):
        """Get messages for a specific user"""
        client = self.get_client()
        messages = await client.users.by_user_id(user_id).messages.get()
        return messages

    async def get_message_by_id(self, user_id: str, message_id: str):
        """Get a specific message by ID"""
        client = self.get_client()
        message = (
            await client.users.by_user_id(user_id)
            .messages.by_message_id(message_id)
            .get()
        )
        return message

    async def get_message_attachments(self, user_id: str, message_id: str):
        """Get all attachments for a specific message"""
        client = self.get_client()
        attachments = (
            await client.users.by_user_id(user_id)
            .messages.by_message_id(message_id)
            .attachments.get()
        )
        return attachments

    async def get_attachment_content(
        self, user_id: str, message_id: str, attachment_id: str
    ):
        """Get the content of a specific attachment"""
        client = self.get_client()
        attachment = (
            await client.users.by_user_id(user_id)
            .messages.by_message_id(message_id)
            .attachments.by_attachment_id(attachment_id)
            .get()
        )
        return attachment

    async def get_user_contacts(self, user_id: str):
        """Get all contacts for a specific user"""
        client = self.get_client()
        contacts = await client.users.by_user_id(user_id).contacts.get()
        return contacts

    async def find_contact_by_email(self, user_id: str, email_address: str):
        """Find a contact by email address"""
        client = self.get_client()

        # Use manual search approach for reliable results
        contacts = await client.users.by_user_id(user_id).contacts.get()

        if contacts and contacts.value:
            for contact in contacts.value:
                if hasattr(contact, 'email_addresses') and contact.email_addresses:
                    for email in contact.email_addresses:
                        if hasattr(email, 'address') and email.address:
                            if email.address.lower() == email_address.lower():
                                return contact
        return None

    def extract_significant_other(self, contact):
        """Extract the significant other field from a contact"""
        if not contact:
            return None

        # Check if contact has significant other field
        significant_other = getattr(contact, "spouse_name", None)
        if significant_other and significant_other.strip():
            return significant_other.strip()

        return None

    async def assign_category_to_message(
        self, user_id: str, message_id: str, category: str
    ):
        """Assign a category to an email message"""
        client = self.get_client()

        # Create message update object with category
        message_update = Message()
        message_update.categories = [category]

        # Update the message
        await (
            client.users.by_user_id(user_id)
            .messages.by_message_id(message_id)
            .patch(message_update)
        )
        return True
