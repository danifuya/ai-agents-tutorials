import os
import httpx
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from utils.utils import normalize_phone_number

logger = logging.getLogger(__name__)


class JustCallServiceError(Exception):
    """Base exception for JustCall service errors."""

    pass


class JustCallAPIError(JustCallServiceError):
    """Exception for JustCall API errors."""

    pass


class JustCallService:
    """Service for sending SMS messages using JustCall."""

    API_BASE_URL = "https://api.justcall.io/v2.1"

    def __init__(self):
        """
        Initializes the JustCallService, loading credentials from environment variables.
        """
        self.api_key = os.environ["JUSTCALL_API_KEY"]
        self.api_secret = os.environ["JUSTCALL_API_SECRET"]
        self.justcall_number = os.environ["JUSTCALL_NUMBER"]
        self.justcall_phone_id = os.environ["JUSTCALL_PHONE_ID"]
        self.escalation_tag_id = os.environ.get("JUSTCALL_ESCALATION_TAG_ID")
        self.headers = {
            "Authorization": f"{self.api_key}:{self.api_secret}",
            "Accept": "application/json",
        }

        # Validate configuration during initialization
        self._validate_configuration()

    def send_sms(self, to: str, body: str) -> str:
        """Send an SMS message."""
        normalized_to = normalize_phone_number(to)
        url = f"{self.API_BASE_URL}/texts/new"
        payload = {
            "justcall_number": self.justcall_number,
            "contact_number": normalized_to,
            "body": body,
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                result = response.json()
                message_id = result.get("text", {}).get("id")
                logger.info(
                    f"Successfully sent SMS to {normalized_to}, message ID: {message_id}"
                )
                return message_id
        except httpx.HTTPStatusError as e:
            logger.error(
                f"JustCall API error sending SMS to {normalized_to}: {e.response.status_code} - {e.response.text}"
            )
            raise JustCallAPIError(f"Failed to send SMS: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Network error sending SMS to {normalized_to}: {str(e)}")
            raise JustCallServiceError(f"Network error sending SMS: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {normalized_to}: {str(e)}")
            raise JustCallServiceError(f"SMS send failed: {str(e)}")

    def send_mms(
        self, to: str, body: str, attachments: Optional[List[str]] = None
    ) -> str:
        """Send an MMS message with optional attachments using JustCall API."""
        normalized_to = normalize_phone_number(to)
        url = f"{self.API_BASE_URL}/texts/new"

        try:
            # Map local file paths to public URLs
            # For service images, we use the Google Cloud Storage URLs
            media_urls = []
            if attachments:
                for attachment_path in attachments:
                    # Map local paths to public URLs
                    if "services.jpg" in attachment_path:
                        media_urls.append(
                            "https://raw.githubusercontent.com/danifuya/ai-agents-tutorials/refs/heads/main/sms_booking_automation/app/assets/services.jpg"
                        )
                    else:
                        logger.warning(
                            f"Unknown attachment path: {attachment_path}, skipping"
                        )
                        continue

                logger.info(
                    f"Mapped {len(media_urls)} attachments to public URLs for MMS to {normalized_to}"
                )

            # Prepare JSON payload according to JustCall API documentation
            payload = {
                "justcall_number": self.justcall_number,
                "contact_number": normalized_to,
                "body": body,
            }

            # Add media URLs if present (comma-separated as per documentation)
            if media_urls:
                payload["media_url"] = ",".join(media_urls)

            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                result = response.json()
                message_id = result.get("text", {}).get("id")
                logger.info(
                    f"Successfully sent MMS to {normalized_to} with {len(media_urls)} media URLs, message ID: {message_id}"
                )
                return message_id

        except httpx.HTTPStatusError as e:
            logger.error(
                f"JustCall API error sending MMS to {normalized_to}: {e.response.status_code} - {e.response.text}"
            )
            raise JustCallAPIError(f"Failed to send MMS: HTTP {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Network error sending MMS to {normalized_to}: {str(e)}")
            raise JustCallServiceError(f"Network error sending MMS: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error sending MMS to {normalized_to}: {str(e)}")
            raise JustCallServiceError(f"MMS send failed: {str(e)}")

    def get_conversation_history(
        self, participant_number: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieves the last 'limit' messages to and from a specific number.
        """
        normalized_number = normalize_phone_number(participant_number)
        url = f"{self.API_BASE_URL}/texts"
        params = {
            "contact_number": normalized_number,
            "sort": "id",
            "page": 0,
            "per_page": limit * 2,
        }

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                result = response.json()
                messages = result.get("data", [])

            history = []
            for msg in messages:
                body = msg.get("sms_info", {}).get("body")
                if not body:
                    continue

                role = "assistant" if msg.get("direction") == "Outgoing" else "user"
                history.append({"role": role, "content": body})

            # The API returns messages sorted by most recent first. We need to reverse
            # them to get chronological order for the agent.
            history.reverse()
            final_history = history[-limit:]

            logger.info(
                f"Retrieved {len(final_history)} messages for conversation with {normalized_number}"
            )
            return final_history

        except httpx.HTTPStatusError as e:
            logger.error(
                f"JustCall API error getting conversation history for {normalized_number}: {e.response.status_code} - {e.response.text}"
            )
            raise JustCallAPIError(
                f"Failed to get conversation history: HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error(
                f"Network error getting conversation history for {normalized_number}: {str(e)}"
            )
            raise JustCallServiceError(
                f"Network error getting conversation history: {str(e)}"
            )
        except Exception as e:
            logger.error(
                f"Unexpected error getting conversation history for {normalized_number}: {str(e)}"
            )
            raise JustCallServiceError(f"Failed to get conversation history: {str(e)}")

    def get_conversation_thread_tags(self, participant_number: str) -> List[str]:
        """
        Retrieves thread tags for the conversation with a specific number.
        Uses the /texts/threads endpoint with phone_id and contact_number.
        Returns a list of tag IDs associated with the conversation thread.
        """
        normalized_number = normalize_phone_number(participant_number)
        url = f"{self.API_BASE_URL}/texts/threads"
        params = {
            "phone_id": self.justcall_phone_id,
            "contact_number": normalized_number,
        }

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                result = response.json()

            threads = result.get("data", [])

            if not threads:
                logger.info("No threads found for number")
                return []

            # Get the first thread (should be the main conversation thread)
            thread = threads[0]

            # Extract tag IDs from thread_tags field
            thread_tags_data = thread.get("thread_tags", [])
            thread_tags = [
                str(tag.get("id")) for tag in thread_tags_data if tag.get("id")
            ]

            logger.info(
                f"Retrieved {len(thread_tags)} thread tags for conversation with {normalized_number}: {thread_tags}"
            )
            return thread_tags

        except httpx.HTTPStatusError as e:
            logger.error(
                f"JustCall API error getting thread tags for {normalized_number}: {e.response.status_code} - {e.response.text}"
            )
            raise JustCallAPIError(
                f"Failed to get thread tags: HTTP {e.response.status_code}"
            )
        except httpx.RequestError as e:
            logger.error(
                f"Network error getting thread tags for {normalized_number}: {str(e)}"
            )
            raise JustCallServiceError(f"Network error getting thread tags: {str(e)}")
        except Exception as e:
            logger.error(
                f"Unexpected error getting thread tags for {normalized_number}: {str(e)}"
            )
            raise JustCallServiceError(f"Failed to get thread tags: {str(e)}")

    def tag_conversation(self, contact_number: str, tag_id: str) -> bool:
        """
        Add a tag to a conversation thread using the add_tag_to_thread endpoint.
        Returns True if successful, False otherwise.
        """
        if not tag_id:
            logger.error("No tag ID provided")
            return False

        normalized_number = normalize_phone_number(contact_number)
        url = f"{self.API_BASE_URL}/texts/threads/tag"
        payload = {
            "tag_id": tag_id,
            "phone_id": self.justcall_phone_id,
            "contact_number": normalized_number,
        }

        try:
            with httpx.Client() as client:
                response = client.post(url, headers=self.headers, json=payload)
                response.raise_for_status()
                result = response.json()

                # Check if the operation was successful
                status = result.get("status")
                if status == "success":
                    logger.info(
                        f"Successfully tagged conversation with {normalized_number} using tag ID {tag_id}"
                    )
                    return True
                else:
                    logger.error(
                        f"Failed to tag conversation with {normalized_number}: API returned status={status}"
                    )
                    return False

        except httpx.HTTPStatusError as e:
            # Check if the error is because tag is already assigned
            try:
                error_response = e.response.json()
                if (
                    error_response.get("status") == "failed"
                    and "already assigned" in error_response.get("message", "").lower()
                ):
                    logger.info(
                        f"Tag {tag_id} already assigned to conversation with {normalized_number} - treating as success"
                    )
                    return True
            except Exception:
                pass  # If we can't parse the response, fall through to the error handling

            logger.error(
                f"JustCall API error tagging conversation with {normalized_number}: {e.response.status_code} - {e.response.text}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                f"Network error tagging conversation with {normalized_number}: {str(e)}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error tagging conversation with {normalized_number}: {str(e)}"
            )
            return False

    def remove_tag_from_conversation(self, contact_number: str, tag_id: str) -> bool:
        """
        Remove a tag from a conversation thread using the remove tag endpoint.
        Returns True if successful, False otherwise.
        """
        if not tag_id:
            logger.error("No tag ID provided")
            return False

        normalized_number = normalize_phone_number(contact_number)
        url = f"{self.API_BASE_URL}/texts/threads/tag"
        params = {
            "tag_id": tag_id,
            "phone_id": self.justcall_phone_id,
            "contact_number": normalized_number,
        }

        try:
            with httpx.Client() as client:
                response = client.delete(url, headers=self.headers, params=params)
                response.raise_for_status()
                result = response.json()

                # Check if the operation was successful
                status = result.get("status")
                if status == "success":
                    logger.info(
                        f"Successfully removed tag {tag_id} from conversation with {normalized_number}"
                    )
                    return True
                else:
                    logger.error(
                        f"Failed to remove tag from conversation with {normalized_number}: API returned status={status}"
                    )
                    return False

        except httpx.HTTPStatusError as e:
            # Check if the error is because tag was already removed or doesn't exist
            try:
                error_response = e.response.json()
                error_message = error_response.get("message", "").lower()
                if error_response.get("status") == "failed" and (
                    "not found" in error_message
                    or "doesn't exist" in error_message
                    or "not assigned" in error_message
                ):
                    logger.info(
                        f"Tag {tag_id} not found on conversation with {normalized_number} - treating as success"
                    )
                    return True
            except Exception:
                pass  # If we can't parse the response, fall through to the error handling

            logger.error(
                f"JustCall API error removing tag from conversation with {normalized_number}: {e.response.status_code} - {e.response.text}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(
                f"Network error removing tag from conversation with {normalized_number}: {str(e)}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error removing tag from conversation with {normalized_number}: {str(e)}"
            )
            return False

    def escalate_conversation(self, contact_number: str) -> bool:
        """
        Mark a conversation as escalated by adding the escalation tag.
        This is a convenience method that specifically uses the escalation tag ID.
        Returns True if successful, False otherwise.
        """
        if not self.escalation_tag_id:
            logger.error(
                "Cannot escalate conversation: no escalation tag ID configured"
            )
            return False

        normalized_number = normalize_phone_number(contact_number)
        logger.info(
            f"Escalating conversation with {normalized_number} using escalation tag ID {self.escalation_tag_id}"
        )
        return self.tag_conversation(normalized_number, self.escalation_tag_id)

    def de_escalate_conversation(self, contact_number: str) -> bool:
        """
        Remove escalation from a conversation by removing the escalation tag.
        This is a convenience method that specifically removes the escalation tag ID.
        Returns True if successful, False otherwise.
        """
        if not self.escalation_tag_id:
            logger.error(
                "Cannot de-escalate conversation: no escalation tag ID configured"
            )
            return False

        normalized_number = normalize_phone_number(contact_number)
        logger.info(
            f"De-escalating conversation with {normalized_number} by removing escalation tag ID {self.escalation_tag_id}"
        )
        return self.remove_tag_from_conversation(
            normalized_number, self.escalation_tag_id
        )

    def _validate_phone_number_mapping(self) -> bool:
        """
        Validates that the configured phone number matches the phone ID.
        Returns True if they match, False otherwise.
        """
        url = f"{self.API_BASE_URL}/phone-numbers"

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()
                result = response.json()
                phone_numbers = result.get("data", [])

            # Find the phone number that matches our configured phone ID
            target_phone = None
            for phone in phone_numbers:
                if str(phone.get("id")) == str(self.justcall_phone_id):
                    target_phone = phone
                    break

            if not target_phone:
                logger.error(
                    f"Phone ID {self.justcall_phone_id} not found in JustCall account"
                )
                return False

            # Check if the phone numbers match
            justcall_number_from_api = target_phone.get("justcall_number")
            if justcall_number_from_api != self.justcall_number:
                logger.error(
                    f"Phone number mismatch: JUSTCALL_NUMBER={self.justcall_number} but phone ID {self.justcall_phone_id} maps to {justcall_number_from_api}"
                )
                return False

            logger.info(
                f"✅ Phone number validation passed: {self.justcall_number} (ID: {self.justcall_phone_id})"
            )
            return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"JustCall API error validating phone number: {e.response.status_code} - {e.response.text}"
            )
            return False
        except httpx.RequestError as e:
            logger.error(f"Network error validating phone number: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating phone number: {str(e)}")
            return False

    def _validate_escalation_tag_by_id(self) -> bool:
        """
        Validates that the configured escalation tag ID exists by fetching it directly.
        Returns True if the tag exists, False if it doesn't exist or isn't configured.
        """
        if not self.escalation_tag_id:
            logger.info("No escalation tag ID configured - skipping validation")
            return True  # Not configured is considered valid

        url = f"{self.API_BASE_URL}/texts/tags/{self.escalation_tag_id}"

        try:
            with httpx.Client() as client:
                response = client.get(url, headers=self.headers)
                response.raise_for_status()
                result = response.json()

            # If we get here, the tag exists
            data = result.get("data", {})
            tag_name = data.get("name", "Unknown")
            tag_color = data.get("color_code", "Unknown")
            logger.info(
                f"✅ Escalation tag validation passed: ID {self.escalation_tag_id} = '{tag_name}' ({tag_color})"
            )
            return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.error(
                    f"Escalation tag ID {self.escalation_tag_id} not found in JustCall account"
                )
            else:
                logger.error(
                    f"JustCall API error validating escalation tag: {e.response.status_code} - {e.response.text}"
                )
            return False
        except httpx.RequestError as e:
            logger.error(f"Network error validating escalation tag by ID: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error validating escalation tag by ID: {str(e)}")
            return False

    def _validate_configuration(self) -> None:
        """
        Validates the JustCall service configuration during initialization.
        Checks phone number/ID mapping and escalation tag existence.
        Raises JustCallServiceError if validation fails.
        """
        logger.info("🔍 Validating JustCall service configuration...")

        validation_errors = []

        # Validate phone number mapping
        try:
            if not self._validate_phone_number_mapping():
                validation_errors.append("Phone number/ID mapping validation failed")
        except Exception as e:
            validation_errors.append(f"Phone number validation error: {str(e)}")

        # Validate escalation tag
        try:
            if not self._validate_escalation_tag_by_id():
                validation_errors.append("Escalation tag validation failed")
        except Exception as e:
            validation_errors.append(f"Escalation tag validation error: {str(e)}")

        # Raise error if any validations failed
        if validation_errors:
            error_message = (
                "JustCall service configuration validation failed:\n"
                + "\n".join(f"  - {error}" for error in validation_errors)
            )
            logger.error(error_message)
            raise JustCallServiceError(error_message)

        logger.info("✅ JustCall service configuration validation passed")
