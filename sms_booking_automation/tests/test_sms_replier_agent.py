import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))

from agents.sms_replier_agent import sms_replier_agent, SMSReplierDeps, add_job_details_to_prompt
from pydantic_ai import RunContext


@pytest.fixture
def mock_sms_replier_deps_with_missing_services():
    """SMSReplierDeps with services in missing_info"""
    return SMSReplierDeps(
        telegram_service=AsyncMock(),
        justcall_service=MagicMock(),
        connection=MagicMock(),
        phone_number="+1234567890",
        job_id=123,
        job_status="pending_client_info",
        job_details=None,
        missing_info=["First Name", "Services required", "Event Date"]  # Services included
    )


@pytest.fixture
def mock_sms_replier_deps_without_missing_services():
    """SMSReplierDeps without services in missing_info"""
    return SMSReplierDeps(
        telegram_service=AsyncMock(),
        justcall_service=MagicMock(),
        connection=MagicMock(),
        phone_number="+0987654321",
        job_id=124,
        job_status="pending_client_info", 
        job_details=None,
        missing_info=["First Name", "Event Date"]  # Services NOT included
    )


class TestSMSReplierAgent:
    """Unit tests for SMS replier agent behavior with missing services"""

    def test_services_included_in_missing_info_prompt(
        self, mock_sms_replier_deps_with_missing_services
    ):
        """
        Given SMSReplierDeps with 'Services required' in missing_info
        When the add_job_details_to_prompt function processes the dependencies
        Then 'Services required' should be included in the generated prompt string
        """
        # Create a mock RunContext with our dependencies
        mock_ctx = MagicMock()
        mock_ctx.deps = mock_sms_replier_deps_with_missing_services
        
        # Call the prompt building function directly
        prompt = add_job_details_to_prompt(mock_ctx)
        
        # Verify the prompt contains the missing services information
        assert prompt, "Prompt should not be empty when missing info is provided"
        assert "Services required" in prompt, f"Expected 'Services required' in prompt: {prompt}"
        assert "First Name" in prompt, f"Expected 'First Name' in prompt: {prompt}"
        assert "Event Date" in prompt, f"Expected 'Event Date' in prompt: {prompt}"
        assert "Missing booking information:" in prompt, f"Expected missing info section in prompt: {prompt}"
        
        # Verify the format matches what we expect
        expected_missing_fields = "First Name, Services required, Event Date"
        assert expected_missing_fields in prompt, f"Expected '{expected_missing_fields}' in prompt: {prompt}"

    def test_services_not_included_when_not_in_missing_info(
        self, mock_sms_replier_deps_without_missing_services
    ):
        """
        Given SMSReplierDeps without 'Services required' in missing_info
        When the add_job_details_to_prompt function processes the dependencies
        Then 'Services required' should NOT be included in the generated prompt string
        """
        # Create a mock RunContext with our dependencies
        mock_ctx = MagicMock()
        mock_ctx.deps = mock_sms_replier_deps_without_missing_services
        
        # Call the prompt building function directly
        prompt = add_job_details_to_prompt(mock_ctx)
        
        # Verify the prompt contains missing info but NOT services
        assert prompt, "Prompt should not be empty when missing info is provided"
        assert "Services required" not in prompt, f"'Services required' should NOT be in prompt: {prompt}"
        assert "First Name" in prompt, f"Expected 'First Name' in prompt: {prompt}"
        assert "Event Date" in prompt, f"Expected 'Event Date' in prompt: {prompt}"
        assert "Missing booking information:" in prompt, f"Expected missing info section in prompt: {prompt}"

    def test_missing_services_appended_to_prompt_list(
        self, mock_sms_replier_deps_with_missing_services
    ):
        """
        Given missing_info containing ['First Name', 'Services required', 'Event Date']
        When the prompt building function processes this information
        Then all missing fields including 'Services required' should be joined into the prompt
        And they should be formatted as a comma-separated list
        """
        # Create a mock RunContext
        mock_ctx = MagicMock()
        mock_ctx.deps = mock_sms_replier_deps_with_missing_services
        
        # Call the prompt building function
        prompt = add_job_details_to_prompt(mock_ctx)
        
        # Verify all missing fields are included in the correct format
        assert "Missing booking information: First Name, Services required, Event Date." in prompt, \
            f"Expected specific format in prompt: {prompt}"
        
        # Verify job status is also included
        assert "Current job status is 'pending_client_info' for reference ID 123." in prompt, \
            f"Expected job status in prompt: {prompt}"

    def test_empty_missing_info_handled_correctly(self):
        """
        Given SMSReplierDeps with empty or None missing_info
        When the add_job_details_to_prompt function processes the dependencies
        Then it should handle the case gracefully without including missing information section
        """
        deps_with_no_missing_info = SMSReplierDeps(
            telegram_service=AsyncMock(),
            justcall_service=MagicMock(),
            connection=MagicMock(),
            phone_number="+5555555555",
            job_id=125,
            job_status="pending_client_info",
            job_details=None,
            missing_info=None  # No missing information
        )
        
        mock_ctx = MagicMock()
        mock_ctx.deps = deps_with_no_missing_info
        
        # Call the prompt building function
        prompt = add_job_details_to_prompt(mock_ctx)
        
        # Should still include job status but no missing info section
        assert "Current job status is 'pending_client_info' for reference ID 125." in prompt, \
            f"Expected job status in prompt: {prompt}"
        assert "Missing booking information:" not in prompt, \
            f"Should not include missing info section when missing_info is None: {prompt}"

    def test_ready_to_post_status_does_not_include_missing_info(self):
        """
        Given SMSReplierDeps with job_status 'ready_to_post' and missing_info
        When the add_job_details_to_prompt function processes the dependencies
        Then it should NOT include the missing information section (only for pending_client_info)
        """
        deps_ready_to_post = SMSReplierDeps(
            telegram_service=AsyncMock(),
            justcall_service=MagicMock(),
            connection=MagicMock(),
            phone_number="+6666666666",
            job_id=126,
            job_status="ready_to_post",
            job_details={"client_first_name": "Jane", "services": ["Photography"]},
            missing_info=["Services required"]  # This should be ignored for ready_to_post
        )
        
        mock_ctx = MagicMock()
        mock_ctx.deps = deps_ready_to_post
        
        # Call the prompt building function
        prompt = add_job_details_to_prompt(mock_ctx)
        
        # Should include job status and details but NOT missing info
        assert "Current job status is 'ready_to_post' for reference ID 126." in prompt, \
            f"Expected job status in prompt: {prompt}"
        assert "Missing booking information:" not in prompt, \
            f"Should not include missing info section for ready_to_post status: {prompt}"
        assert "Booking details:" in prompt, \
            f"Expected job details section for ready_to_post: {prompt}"