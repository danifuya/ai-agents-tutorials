import re
import os
import base64
from typing import Dict, Any, Optional
from fastapi import Request
from fastapi.responses import Response
from .graph_service import GraphService
from .document_service import DocumentService
from .agent_service import AgentService


class WebhookService:
    """Service class to handle webhook notifications from Microsoft Graph"""

    def __init__(self, graph_service: GraphService, document_service: DocumentService, agent_service: AgentService, category_name: str):
        self.graph_service = graph_service
        self.document_service = document_service
        self.agent_service = agent_service
        self.category_name = category_name

    async def handle_validation(self, validation_token: str) -> Response:
        """
        Handle Microsoft Graph webhook validation request

        Args:
            validation_token: The validation token from the query parameters

        Returns:
            Response with the validation token as plain text
        """
        print(f"Received validation request with token: {validation_token}")
        return Response(content=validation_token, media_type="text/plain")

    async def process_notification(self, payload: Dict[str, Any]) -> Dict[str, str]:
        """
        Process incoming webhook notifications

        Args:
            payload: The JSON payload from Microsoft Graph

        Returns:
            Response indicating processing status
        """
        print(f"Received Outlook webhook: {payload}")

        # Extract notification details
        if "value" in payload:
            for notification in payload["value"]:
                await self._process_single_notification(notification)

        return {"status": "success", "message": "Webhook received"}

    async def _process_single_notification(self, notification: Dict[str, Any]):
        """
        Process a single notification from the webhook payload

        Args:
            notification: Single notification object
        """
        resource = notification.get("resource")
        change_type = notification.get("changeType")
        subscription_id = notification.get("subscriptionId")

        print(
            f"Processing notification - Resource: {resource}, Change: {change_type}, Subscription: {subscription_id}"
        )

        # Extract user ID and message ID from resource URL using robust regex
        # Handles various formats like:
        # - Users/{user-id}/Messages/{message-id}
        # - users/{user-id}/messages/{message-id}
        # - Users/{user-id}/MailFolders('Inbox')/Messages/{message-id}
        if resource:
            try:
                # Robust regex to extract user ID and message ID (case-insensitive)
                pattern = r"[Uu]sers/([^/]+)/.*[Mm]essages/([^/?]+)"
                match = re.search(pattern, resource)

                if match:
                    user_id = match.group(1)
                    message_id = match.group(2)

                    print(f"Extracted User ID: {user_id}, Message ID: {message_id}")

                    # Fetch the actual message details
                    await self._fetch_and_process_message(
                        user_id, message_id, change_type
                    )
                else:
                    print(f"Could not parse resource URL: {resource}")

            except Exception as e:
                print(f"Error processing notification: {e}")

    async def _fetch_and_process_message(
        self, user_id: str, message_id: str, change_type: str
    ):
        """
        Fetch and process the actual email message

        Args:
            user_id: The user ID
            message_id: The message ID
            change_type: The type of change (created, updated)
        """
        try:
            print(f"Fetching message details for: {message_id}")

            # Fetch the message details from Microsoft Graph
            message = await self.graph_service.get_message_by_id(user_id, message_id)

            if message:
                # Extract message details safely
                subject = getattr(message, "subject", "No Subject")

                # Safe sender extraction
                sender_email = "Unknown"
                sender_name = "Unknown"

                if hasattr(message, "sender") and message.sender:
                    if (
                        hasattr(message.sender, "email_address")
                        and message.sender.email_address
                    ):
                        sender_email = getattr(
                            message.sender.email_address, "address", "Unknown"
                        )
                        sender_name = getattr(
                            message.sender.email_address, "name", sender_email
                        )

                # Extract body preview
                body_preview = getattr(message, "body_preview", "No preview available")[
                    :100
                ]

                print(f"📧 NEW EMAIL {change_type.upper()}:")
                print(f"  📋 Subject: {subject}")
                print(f"  👤 From: {sender_name} <{sender_email}>")
                print(f"  📄 Preview: {body_preview}...")
                print(f"  🆔 Message ID: {message_id}")
                print("-" * 60)

                # Check contact for folder name
                folder_name = await self._get_contact_folder_name(
                    user_id, sender_email
                )

                if folder_name:
                    print(f"  📁 Folder: {folder_name}")

                    # Process attachments in contact's folder
                    attachments_stored = await self._process_attachments(
                        user_id, message_id, subject, folder_name
                    )

                    # Classify invoice message
                    await self._classify_invoice_message(
                        message, subject, sender_email, body_preview
                    )

                    # Only assign category if attachments were successfully stored
                    if attachments_stored:
                        await self._assign_category(user_id, message_id)
                    else:
                        print("🏷️ No category assigned - no attachments stored")
                else:
                    print(f"  📁 No folder name found for {sender_email}")
                    print("  ⏭️ Skipping attachment processing and categorization")
                    print("  📄 Only processing emails from contacts with folder information")

            else:
                print(f"❌ Could not fetch message {message_id}")

        except Exception as e:
            print(f"❌ Error fetching message {message_id}: {e}")
            print(f"   User ID: {user_id}")

    async def _get_contact_folder_name(self, user_id: str, sender_email: str):
        """
        Get folder name from contact information
        """
        try:
            print(f"🔍 Looking up contact for: {sender_email}")

            # Find contact by email address
            contact = await self.graph_service.find_contact_by_email(user_id, sender_email)

            if contact:
                print(f"👤 Contact found: {getattr(contact, 'display_name', 'Unknown')}")

                # Extract folder name from contact
                folder_name = self.graph_service.extract_significant_other(contact)

                return folder_name
            else:
                print(f"👤 No contact found for {sender_email}")
                return None

        except Exception as e:
            print(f"❌ Error looking up contact for {sender_email}: {e}")
            return None

    async def _classify_invoice_message(
        self, message, subject: str, sender_email: str, body_preview: str
    ):
        """
        Classify if the message is an invoice
        """
        # Simple invoice detection keywords
        invoice_keywords = [
            "invoice",
            "bill",
            "payment",
            "receipt",
            "statement",
            "facture",
            "rechnung",
        ]

        subject_lower = subject.lower()
        body_lower = body_preview.lower()

        # Check for invoice keywords
        is_potential_invoice = any(
            keyword in subject_lower or keyword in body_lower
            for keyword in invoice_keywords
        )

        if is_potential_invoice:
            print(f"🧾 POTENTIAL INVOICE DETECTED!")
            print(f"   Keywords found in: {subject} | {body_preview}")
        else:
            print(f"📄 Regular email (not an invoice)")

    async def _process_attachments(self, user_id: str, message_id: str, subject: str, folder_name: str):
        """
        Process and download attachments from the email
        Returns True if any attachments were successfully stored
        """
        attachments_stored = False

        try:
            # Get all attachments for the message
            attachments_response = await self.graph_service.get_message_attachments(
                user_id, message_id
            )

            if not attachments_response or not attachments_response.value:
                print("📎 No attachments found")
                return False

            attachments = attachments_response.value
            print(f"📎 Found {len(attachments)} attachment(s):")

            # Create folder based on contact information
            safe_folder_name = re.sub(r"[^\w\-_\.]", "_", folder_name)[:50]
            attachments_dir = os.path.join("attachments", safe_folder_name)
            os.makedirs(attachments_dir, exist_ok=True)
            print(f"📁 Storing in folder: {attachments_dir}")

            for attachment in attachments:
                stored = await self._process_single_attachment(
                    user_id, message_id, attachment, attachments_dir, subject
                )
                if stored:
                    attachments_stored = True

            return attachments_stored

        except Exception as e:
            print(f"❌ Error processing attachments: {e}")
            return False

    async def _process_single_attachment(
        self,
        user_id: str,
        message_id: str,
        attachment,
        attachments_dir: str,
        subject: str,
    ):
        """
        Process a single attachment
        Returns True if attachment was successfully stored
        """
        try:
            attachment_name = getattr(attachment, "name", "unknown_attachment")
            attachment_size = getattr(attachment, "size", 0)
            attachment_type = getattr(attachment, "content_type", "unknown")
            attachment_id = getattr(attachment, "id", None)

            print(
                f"  📋 {attachment_name} ({attachment_size} bytes, {attachment_type})"
            )

            # Filter for common invoice file types
            invoice_extensions = [
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
                ".png",
                ".jpg",
                ".jpeg",
            ]
            file_ext = os.path.splitext(attachment_name.lower())[1]

            if file_ext not in invoice_extensions:
                print(f"     ⏭️ Skipping {attachment_name} (not an invoice-type file)")
                return False

            # Always fetch attachment content separately (simpler and consistent)
            if attachment_id:
                print(f"     🔄 Fetching {attachment_name} content...")
                attachment_detail = await self.graph_service.get_attachment_content(
                    user_id, message_id, attachment_id
                )

                if (
                    hasattr(attachment_detail, "content_bytes")
                    and attachment_detail.content_bytes
                ):
                    success = await self._save_attachment_content(
                        attachment_detail.content_bytes,
                        attachment_name,
                        attachments_dir,
                        subject,
                    )
                    return success
                else:
                    print(f"     ❌ Could not get content for {attachment_name}")
                    return False
            else:
                print(f"     ❌ No attachment ID found for {attachment_name}")
                return False

        except Exception as e:
            print(f"     ❌ Error processing attachment {attachment_name}: {e}")
            return False

    async def _save_attachment_content(
        self, content_bytes, filename: str, attachments_dir: str, subject: str
    ):
        """
        Save attachment content to disk
        Returns True if successfully saved
        """
        try:
            # Use original attachment filename
            file_path = os.path.join(attachments_dir, filename)

            # Microsoft Graph always returns base64-encoded content
            # Decode from base64 regardless of whether it's string or bytes
            try:
                file_content = base64.b64decode(content_bytes)
                print(f"     🔄 Decoded from base64")
            except Exception as decode_error:
                print(f"     ❌ Base64 decode error: {decode_error}")
                return False

            if file_content:
                # Save to file
                with open(file_path, "wb") as f:
                    f.write(file_content)

                print(f"     ✅ Saved: {file_path} ({len(file_content)} bytes)")

                # Try to validate the file
                if filename.lower().endswith(".pdf"):
                    # Check if it starts with PDF signature
                    if file_content.startswith(b"%PDF"):
                        print(
                            f"     📄 Valid PDF detected - ready for invoice processing!"
                        )

                        # Scan document with docling and extract invoice data
                        await self._process_document_intelligence(file_path, filename)
                    else:
                        print(f"     ⚠️ WARNING: File doesn't appear to be a valid PDF")
                        print(f"     🔍 File starts with: {file_content[:10]}")

                return True

        except Exception as e:
            print(f"     ❌ Error saving {filename}: {e}")
            import traceback

            print(f"     🔍 Full error: {traceback.format_exc()}")
            return False

    async def _process_document_intelligence(self, file_path: str, filename: str):
        """
        Process document with docling and AI extraction, then rename if needed
        """
        try:
            # Step 1: Scan document with docling
            markdown_content = await self.document_service.scan_document(file_path, filename)

            if markdown_content:
                # Step 2: Extract invoice data with AI
                invoice_data = await self.agent_service.extract_invoice_data(markdown_content)

                # Step 3: Rename file if both date and number are found
                if invoice_data.invoice_date and invoice_data.invoice_number:
                    # Format date as YYYY-MM-DD string for filename
                    date_str = invoice_data.invoice_date.strftime("%Y-%m-%d")
                    new_filename = f"{date_str}_{invoice_data.invoice_number}.pdf"
                    new_file_path = os.path.join(os.path.dirname(file_path), new_filename)

                    print(f"     📝 Renaming file to: {new_filename}")
                    os.rename(file_path, new_file_path)
                    print(f"     ✅ File renamed successfully")
                else:
                    print(f"     📄 Keeping original filename: {filename}")
                    if not invoice_data.invoice_date:
                        print(f"     ❓ Missing invoice date")
                    if not invoice_data.invoice_number:
                        print(f"     ❓ Missing invoice number")

        except Exception as e:
            print(f"     ❌ Error processing document intelligence: {e}")

    async def _assign_category(self, user_id: str, message_id: str):
        """
        Assign a category to the processed email
        """
        try:
            await self.graph_service.assign_category_to_message(
                user_id, message_id, self.category_name
            )
            print(f"🏷️ Assigned category: '{self.category_name}'")

        except Exception as e:
            print(f"❌ Error assigning category: {e}")
