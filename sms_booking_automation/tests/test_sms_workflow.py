import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))

from workflows.sms_workflow import process_incoming_sms
from agents.sms_replier_agent import SMSReplierDeps


@pytest.fixture
def mock_justcall_service():
    """Mock JustCall service"""
    mock_service = MagicMock()
    mock_service.get_conversation_history.return_value = []
    mock_service.escalation_tag_id = None
    mock_service.send_sms = MagicMock()
    return mock_service


@pytest.fixture
def mock_telegram_service():
    """Mock Telegram service"""
    return AsyncMock()


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    return MagicMock()


@pytest.fixture
def consolidated_view_without_services():
    """Consolidated view data for job without services"""
    return {
        "job_id": 123,
        "job_status": "pending_client_info",
        "client_first_name": "John",
        "client_last_name": "Doe", 
        "client_email": "john.doe@test.com",
        "client_phone_number": "+1234567890",
        "event_date": "2024-07-15",
        "start_time": "16:00:00",
        "event_address_street": "123 Main St",
        "event_address_suburb": "Downtown",
        "event_address_state": "NSW",
        "event_address_postcode": "2000",
        "guest_count": 50,
        "event_type": "wedding", 
        "photographer_count": 2,
        "event_duration_hours": 8,
        "services": None  # No services - marked as missing
    }


@pytest.fixture
def consolidated_view_with_services():
    """Consolidated view data for job with services"""
    return {
        "job_id": 124,
        "job_status": "pending_client_info", 
        "client_first_name": "Jane",
        "client_last_name": "Smith",
        "client_email": "jane.smith@test.com",
        "client_phone_number": "+0987654321",
        "event_date": "2024-08-15",
        "start_time": "14:00:00",
        "event_address_street": "456 Oak St",
        "event_address_suburb": "Midtown",
        "event_address_state": "NSW",
        "event_address_postcode": "2001",
        "guest_count": 75,
        "event_type": "wedding",
        "photographer_count": 2,
        "event_duration_hours": 6,
        "services": ["Wedding Photography", "Event Videography"]  # Has services
    }


class TestSMSWorkflow:
    """Unit tests for process_incoming_sms function behavior with missing services"""

    @pytest.mark.asyncio
    async def test_missing_services_passed_to_sms_replier_agent(
        self, mock_db_connection, mock_justcall_service, mock_telegram_service, 
        consolidated_view_without_services
    ):
        """
        Given a job that exists but has no associated services
        When the SMS workflow processes a message from that client
        Then the SMS replier agent should receive 'Services required' in missing_info
        """
        phone_number = "+1234567890"
        message_body = "Hi, I need more information about my booking"
        job_id = 123

        # Mock to capture the dependencies passed to SMS replier agent
        captured_deps = None
        
        async def mock_sms_replier_run(user_prompt, deps):
            nonlocal captured_deps
            captured_deps = deps
            return MagicMock(output="Mock reply")

        with patch('workflows.sms_workflow.ClientRepository.get_by_phone') as mock_get_client, \
             patch('workflows.sms_workflow.sms_filter_agent') as mock_filter, \
             patch('workflows.sms_workflow.info_collector_agent') as mock_info_collector, \
             patch('workflows.sms_workflow.manage_job_from_service_request') as mock_job_manager, \
             patch('workflows.sms_workflow.JobRepository.get_consolidated_view') as mock_consolidated_view, \
             patch('workflows.sms_workflow.sms_replier_agent') as mock_replier:

            # Configure mocks
            mock_get_client.return_value = None  # New client
            mock_filter.run = AsyncMock(return_value=MagicMock(output=MagicMock(is_service_request=True)))
            
            # Mock info collector
            mock_service_info = MagicMock()
            mock_service_info.model_dump.return_value = {"client_phone_number": phone_number}
            mock_info_collector.run = AsyncMock(return_value=MagicMock(output=mock_service_info))
            
            # Mock job manager to return job ID
            mock_job_manager.return_value = {"job_id": job_id}
            
            # Mock consolidated view to return job without services
            mock_consolidated_view.return_value = consolidated_view_without_services
            
            # Mock SMS replier agent
            mock_replier.run = mock_sms_replier_run

            # Execute the SMS workflow
            await process_incoming_sms(
                conn=mock_db_connection,
                justcall_service=mock_justcall_service,
                telegram_service=mock_telegram_service,
                from_number=phone_number,
                message_body=message_body
            )

            # Verify SMS replier agent was called with correct dependencies
            assert captured_deps is not None, "SMS replier agent should have been called"
            assert isinstance(captured_deps, SMSReplierDeps), "Should pass SMSReplierDeps object"
            
            # Verify missing_info contains 'Services required'
            missing_info = captured_deps.missing_info
            assert missing_info is not None, "missing_info should not be None when fields are missing"
            assert "Services required" in missing_info, f"Expected 'Services required' in missing_info, got: {missing_info}"
            
            # Since all other fields are properly populated in our mock data,
            # 'Services required' should be the only missing field
            assert missing_info == ["Services required"], f"Expected only 'Services required' to be missing, got: {missing_info}"
                
            # Verify job details
            assert captured_deps.job_id == job_id, f"Expected job_id {job_id}, got {captured_deps.job_id}"
            assert captured_deps.job_status == "pending_client_info", f"Expected job_status pending_client_info"

    @pytest.mark.asyncio
    async def test_services_not_missing_when_job_has_services(
        self, mock_db_connection, mock_justcall_service, mock_telegram_service,
        consolidated_view_with_services
    ):
        """
        Given a job with associated services in the database
        When the SMS workflow processes a message from that client  
        Then the SMS replier agent should NOT receive 'Services required' in missing_info
        """
        phone_number = "+0987654321"
        message_body = "Hi, I have a question about my booking"
        job_id = 124

        captured_deps = None
        
        async def mock_sms_replier_run(user_prompt, deps):
            nonlocal captured_deps
            captured_deps = deps
            return MagicMock(output="Mock reply")

        with patch('workflows.sms_workflow.ClientRepository.get_by_phone') as mock_get_client, \
             patch('workflows.sms_workflow.sms_filter_agent') as mock_filter, \
             patch('workflows.sms_workflow.info_collector_agent') as mock_info_collector, \
             patch('workflows.sms_workflow.manage_job_from_service_request') as mock_job_manager, \
             patch('workflows.sms_workflow.JobRepository.get_consolidated_view') as mock_consolidated_view, \
             patch('workflows.sms_workflow.sms_replier_agent') as mock_replier:

            # Configure mocks
            mock_get_client.return_value = None  # New client
            mock_filter.run = AsyncMock(return_value=MagicMock(output=MagicMock(is_service_request=True)))
            
            mock_service_info = MagicMock()
            mock_service_info.model_dump.return_value = {"client_phone_number": phone_number}
            mock_info_collector.run = AsyncMock(return_value=MagicMock(output=mock_service_info))
            
            mock_job_manager.return_value = {"job_id": job_id}
            
            # Mock consolidated view to return job WITH services
            mock_consolidated_view.return_value = consolidated_view_with_services
            
            mock_replier.run = mock_sms_replier_run

            # Execute the SMS workflow
            await process_incoming_sms(
                conn=mock_db_connection,
                justcall_service=mock_justcall_service,
                telegram_service=mock_telegram_service,
                from_number=phone_number,
                message_body=message_body
            )

            # Verify SMS replier agent was called
            assert captured_deps is not None, "SMS replier agent should have been called"
            
            # Verify missing_info does NOT contain 'Services required'
            missing_info = captured_deps.missing_info
            if missing_info is not None:
                assert "Services required" not in missing_info, \
                    f"'Services required' should not be in missing_info when job has services, got: {missing_info}"
            else:
                # If missing_info is None, that's also valid (no missing fields)
                assert True, "missing_info is None, which means no fields are missing"

    @pytest.mark.asyncio
    async def test_existing_client_bypasses_filter(
        self, mock_db_connection, mock_justcall_service, mock_telegram_service
    ):
        """
        Given an existing client in the database
        When the SMS workflow processes a message from that client
        Then it should bypass the SMS filter and process the request directly
        """
        phone_number = "+1111111111"
        message_body = "Update on my booking please"
        
        existing_client = {
            "client_id": 789,
            "first_name": "Existing",
            "last_name": "Customer",
            "phone_number": phone_number
        }

        captured_deps = None
        
        async def mock_sms_replier_run(user_prompt, deps):
            nonlocal captured_deps
            captured_deps = deps
            return MagicMock(output="Mock reply")

        with patch('workflows.sms_workflow.ClientRepository.get_by_phone') as mock_get_client, \
             patch('workflows.sms_workflow.sms_filter_agent') as mock_filter, \
             patch('workflows.sms_workflow.info_collector_agent') as mock_info_collector, \
             patch('workflows.sms_workflow.manage_job_from_service_request') as mock_job_manager, \
             patch('workflows.sms_workflow.JobRepository.get_consolidated_view') as mock_consolidated_view, \
             patch('workflows.sms_workflow.sms_replier_agent') as mock_replier:

            # Configure mocks - existing client
            mock_get_client.return_value = existing_client
            
            # SMS filter should NOT be called for existing clients
            mock_filter.run = AsyncMock()
            
            mock_service_info = MagicMock()
            mock_service_info.model_dump.return_value = {"client_phone_number": phone_number}
            mock_info_collector.run = AsyncMock(return_value=MagicMock(output=mock_service_info))
            
            mock_job_manager.return_value = {"job_id": 999}
            mock_consolidated_view.return_value = {"job_id": 999, "job_status": "confirmed", "services": []}
            mock_replier.run = mock_sms_replier_run

            # Execute the SMS workflow
            await process_incoming_sms(
                conn=mock_db_connection,
                justcall_service=mock_justcall_service,
                telegram_service=mock_telegram_service,
                from_number=phone_number,
                message_body=message_body
            )

            # Verify SMS filter was NOT called (bypassed for existing clients)
            mock_filter.run.assert_not_called()
            
            # Verify other components were still called
            assert captured_deps is not None, "SMS replier should have been called"
            mock_info_collector.run.assert_called_once()
            mock_job_manager.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_service_request_filtered_out(
        self, mock_db_connection, mock_justcall_service, mock_telegram_service
    ):
        """
        Given a new client sending a non-service-related message
        When the SMS workflow processes the message
        Then it should be filtered out and no further processing should occur
        """
        phone_number = "+2222222222"
        message_body = "Hello, what's the weather like today?"

        with patch('workflows.sms_workflow.ClientRepository.get_by_phone') as mock_get_client, \
             patch('workflows.sms_workflow.sms_filter_agent') as mock_filter, \
             patch('workflows.sms_workflow.info_collector_agent') as mock_info_collector, \
             patch('workflows.sms_workflow.manage_job_from_service_request') as mock_job_manager, \
             patch('workflows.sms_workflow.sms_replier_agent') as mock_replier:

            # Configure mocks
            mock_get_client.return_value = None  # New client
            
            # Mock filter to reject the message as non-service-related
            mock_filter.run = AsyncMock(return_value=MagicMock(output=MagicMock(is_service_request=False)))
            
            # These should NOT be called when message is filtered out
            mock_info_collector.run = AsyncMock()
            mock_job_manager = AsyncMock()
            mock_replier.run = AsyncMock()

            # Execute the SMS workflow
            await process_incoming_sms(
                conn=mock_db_connection,
                justcall_service=mock_justcall_service,
                telegram_service=mock_telegram_service,
                from_number=phone_number,
                message_body=message_body
            )

            # Verify filter was called
            mock_filter.run.assert_called_once()
            
            # Verify subsequent steps were NOT called
            mock_info_collector.run.assert_not_called()
            mock_job_manager.assert_not_called()
            mock_replier.run.assert_not_called()
            
            # Verify no SMS was sent
            mock_justcall_service.send_sms.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_services_array_treated_as_missing(
        self, mock_db_connection, mock_justcall_service, mock_telegram_service
    ):
        """
        Given a job that has an empty services array (no associated services)
        When the SMS workflow processes a message from that client
        Then the SMS replier agent should receive 'Services required' in missing_info
        And services should be treated as missing even though it's an empty array, not None
        """
        phone_number = "+3333333333"
        message_body = "I need info about my booking"
        job_id = 127

        # Consolidated view with empty services array (not None)
        consolidated_view_empty_services = {
            "job_id": 127,
            "job_status": "pending_client_info",
            "client_first_name": "Alice",
            "client_last_name": "Johnson",
            "client_email": "alice@test.com", 
            "client_phone_number": "+3333333333",
            "event_date": "2024-09-15",
            "start_time": "18:00:00",
            "event_address_street": "456 Oak Ave",
            "event_address_suburb": "Westside",
            "event_address_state": "VIC",
            "event_address_postcode": "3000",
            "guest_count": 75,
            "event_type": "corporate",
            "photographer_count": 1,
            "event_duration_hours": 4,
            "services": []  # Empty array - should be treated as missing
        }

        captured_deps = None
        
        async def mock_sms_replier_run(user_prompt, deps):
            nonlocal captured_deps
            captured_deps = deps
            return MagicMock(output="Mock reply")

        with patch('workflows.sms_workflow.ClientRepository.get_by_phone') as mock_get_client, \
             patch('workflows.sms_workflow.sms_filter_agent') as mock_filter, \
             patch('workflows.sms_workflow.info_collector_agent') as mock_info_collector, \
             patch('workflows.sms_workflow.manage_job_from_service_request') as mock_job_manager, \
             patch('workflows.sms_workflow.JobRepository.get_consolidated_view') as mock_consolidated_view, \
             patch('workflows.sms_workflow.sms_replier_agent') as mock_replier:

            # Configure mocks
            mock_get_client.return_value = None  # New client
            mock_filter.run = AsyncMock(return_value=MagicMock(output=MagicMock(is_service_request=True)))
            
            mock_service_info = MagicMock()
            mock_service_info.model_dump.return_value = {"client_phone_number": phone_number}
            mock_info_collector.run = AsyncMock(return_value=MagicMock(output=mock_service_info))
            
            mock_job_manager.return_value = {"job_id": job_id}
            
            # Mock consolidated view to return job with EMPTY services array
            mock_consolidated_view.return_value = consolidated_view_empty_services
            
            mock_replier.run = mock_sms_replier_run

            # Execute the SMS workflow
            await process_incoming_sms(
                conn=mock_db_connection,
                justcall_service=mock_justcall_service,
                telegram_service=mock_telegram_service,
                from_number=phone_number,
                message_body=message_body
            )

            # Verify SMS replier agent was called
            assert captured_deps is not None, "SMS replier agent should have been called"
            assert isinstance(captured_deps, SMSReplierDeps), "Should pass SMSReplierDeps object"
            
            # THIS IS THE KEY TEST: empty services array should be treated as missing
            missing_info = captured_deps.missing_info
            if missing_info is None:
                # Currently this might be None because empty array is not considered missing
                # After fix, this should contain "Services required"
                assert False, "missing_info should not be None when services array is empty"
            else:
                assert "Services required" in missing_info, f"Expected 'Services required' in missing_info when services is empty array, got: {missing_info}"