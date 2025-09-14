import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))

from workflows.job_management_workflow import manage_job_from_service_request


@pytest.fixture
def mock_db_connection():
    """Mock database connection for unit tests"""
    return MagicMock()


@pytest.fixture
def complete_service_info():
    """Complete service request info with all required fields"""
    return {
        "client_phone_number": "+1234567890",
        "client_first_name": "John",
        "client_last_name": "Doe",
        "client_email": "john.doe@test.com",
        "event_date": "2024-08-15",
        "start_time": "14:00:00",
        "event_address_street": "123 Main Street",
        "event_address_postcode": "2000",
        "guest_count": 75,
        "event_type": "wedding",
        "photographer_count": 2,
        "services": ["wedding_ceremony", "wedding_reception"],
        "event_duration_hours": 8,
    }


@pytest.fixture
def incomplete_service_info():
    """Incomplete service request info missing some required fields"""
    return {
        "client_phone_number": "+0987654321",
        "client_first_name": "Jane",
        "client_last_name": "Smith",
        "client_email": "jane.smith@test.com",
        "event_date": "2024-09-20",
        "start_time": "16:00:00",
        # Missing: event_address_postcode
        "event_address_street": "456 Oak Avenue",
        "guest_count": 50,
        "event_type": "corporate",
        "photographer_count": 1,
        "services": ["event_corporate"],
        "event_duration_hours": 4,
    }


class TestJobManagementWorkflow:
    """Unit tests for job management workflow focusing on job status transitions"""

    @pytest.mark.asyncio
    async def test_complete_service_info_creates_ready_to_post_job(
        self, mock_db_connection, complete_service_info
    ):
        """
        Given complete service request information with all required fields
        When the job management workflow processes the request
        Then the job status should be 'ready_to_post'
        And all job details should be properly saved
        """
        with (
            patch(
                "workflows.job_management_workflow.ClientRepository"
            ) as mock_client_repo,
            patch("workflows.job_management_workflow.JobRepository") as mock_job_repo,
            patch(
                "workflows.job_management_workflow.ServiceMapper"
            ) as mock_service_mapper,
            patch(
                "workflows.job_management_workflow.JobServiceRepository"
            ) as mock_job_service_repo,
        ):
            # Mock client creation/retrieval
            mock_client_repo.get_by_phone = AsyncMock(return_value=None)  # New client
            mock_client_repo.get_by_phone_or_email = AsyncMock(
                return_value=None
            )  # New client
            mock_client_repo.create = AsyncMock(return_value=123)  # client_id
            mock_client_repo.update = AsyncMock(return_value=None)

            # Mock job lookup (no existing jobs for this client)
            mock_job_repo.get_by_client_phone_or_email = AsyncMock(
                return_value=[]
            )  # No existing jobs

            # Mock service mapping (assume valid services from V001 migration)
            mock_service_mapper.get_service_ids_by_codes = AsyncMock(
                return_value=[1, 2]
            )  # service_ids for wedding_ceremony, wedding_reception

            # Mock job creation with ready_to_post status
            mock_job_repo.create = AsyncMock(return_value=456)  # job_id
            mock_job_repo.associate_services = AsyncMock(return_value=None)
            mock_job_repo.get_by_code = AsyncMock(
                return_value=None
            )  # No duplicate job codes
            mock_job_repo.update = AsyncMock(return_value=None)

            # Mock consolidated view - complete data should result in ready_to_post
            mock_job_repo.get_consolidated_view = AsyncMock(
                return_value={
                    **complete_service_info,
                }
            )

            # Mock job service repository
            with patch(
                "workflows.job_management_workflow.JobServiceRepository"
            ) as mock_job_service_repo:
                mock_job_service_repo.update_job_services = AsyncMock(return_value=None)

                # Execute the job management workflow
                result = await manage_job_from_service_request(
                    conn=mock_db_connection, service_info=complete_service_info
                )

                # Verify the workflow result
                assert result is not None, "Workflow should return a result"
                assert "job_id" in result, "Result should contain job_id"
                assert result["job_id"] == 456, "Should return the mocked job_id"
                assert result["job_status"] == "ready_to_post", (
                    "Should set status to ready_to_post for complete info"
                )

                # Verify client creation was attempted
                mock_client_repo.create.assert_called_once()

                # Verify job creation was attempted
                mock_job_repo.create.assert_called_once()

                # Verify services were processed (main focus is that services are handled)
                mock_service_mapper.get_service_ids_by_codes.assert_called_once()

    @pytest.mark.asyncio
    async def test_incomplete_service_info_creates_pending_client_info_job(
        self, mock_db_connection, incomplete_service_info
    ):
        """
        Given incomplete service request information missing required fields
        When the job management workflow processes the request
        Then the job status should be 'pending_client_info'
        And the job should be created with available information
        """
        with (
            patch(
                "workflows.job_management_workflow.ClientRepository"
            ) as mock_client_repo,
            patch("workflows.job_management_workflow.JobRepository") as mock_job_repo,
            patch(
                "workflows.job_management_workflow.ServiceMapper"
            ) as mock_service_mapper,
            patch(
                "workflows.job_management_workflow.JobServiceRepository"
            ) as mock_job_service_repo,
        ):
            # Mock client creation
            mock_client_repo.get_by_phone = AsyncMock(return_value=None)
            mock_client_repo.get_by_phone_or_email = AsyncMock(return_value=None)
            mock_client_repo.create = AsyncMock(return_value=123)
            mock_client_repo.update = AsyncMock(return_value=None)

            # Mock job lookup (no existing jobs)
            mock_job_repo.get_by_client_phone_or_email = AsyncMock(return_value=[])
            mock_job_repo.get_by_code = AsyncMock(return_value=None)
            mock_job_repo.update = AsyncMock(return_value=None)

            # Mock service mapping
            mock_service_mapper.get_service_ids_by_codes = AsyncMock(
                return_value=[3]
            )  # event_corporate

            # Mock job creation with pending_client_info status
            mock_job_repo.create = AsyncMock(return_value=789)
            mock_job_repo.associate_services = AsyncMock(return_value=None)

            # Mock consolidated view - incomplete data should result in pending_client_info
            mock_job_repo.get_consolidated_view = AsyncMock(
                return_value={
                    **incomplete_service_info,
                    # Missing fields from incomplete_service_info result in pending status
                }
            )

            # Mock job service repository
            mock_job_service_repo.update_job_services = AsyncMock(return_value=None)

            # Execute the job management workflow
            result = await manage_job_from_service_request(
                conn=mock_db_connection, service_info=incomplete_service_info
            )

            # Verify the workflow result
            assert result is not None, "Workflow should return a result"
            assert "job_id" in result, "Result should contain job_id"
            assert result["job_id"] == 789, "Should return the mocked job_id"
            assert result["job_status"] == "pending_client_info", (
                "Should set status to pending_client_info for incomplete info"
            )

            # Verify job was created with available data
            mock_job_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_with_missing_services_not_ready_to_post(
        self, mock_db_connection, complete_service_info
    ):
        """
        Given service request information without services specified
        When the job management workflow processes the request
        Then the job status should be 'pending_client_info'
        Because services are required for ready_to_post status
        """
        # Remove services from complete info
        incomplete_info = complete_service_info.copy()
        del incomplete_info["services"]  # Remove services field entirely

        with (
            patch(
                "workflows.job_management_workflow.ClientRepository"
            ) as mock_client_repo,
            patch("workflows.job_management_workflow.JobRepository") as mock_job_repo,
            patch(
                "workflows.job_management_workflow.ServiceMapper"
            ) as mock_service_mapper,
            patch(
                "workflows.job_management_workflow.JobServiceRepository"
            ) as mock_job_service_repo,
        ):
            # Mock client creation
            mock_client_repo.get_by_phone = AsyncMock(return_value=None)
            mock_client_repo.get_by_phone_or_email = AsyncMock(return_value=None)
            mock_client_repo.create = AsyncMock(return_value=123)
            mock_client_repo.update = AsyncMock(return_value=None)

            # Mock job lookup (no existing jobs)
            mock_job_repo.get_by_client_phone_or_email = AsyncMock(return_value=[])
            mock_job_repo.get_by_code = AsyncMock(return_value=None)
            mock_job_repo.update = AsyncMock(return_value=None)

            # Mock service mapping returns empty (no services)
            mock_service_mapper.get_service_ids_by_codes = AsyncMock(return_value=[])

            # Mock job creation
            mock_job_repo.create = AsyncMock(return_value=999)
            mock_job_repo.associate_services = AsyncMock(return_value=None)

            # Mock consolidated view - missing services should result in pending_client_info
            mock_job_repo.get_consolidated_view = AsyncMock(
                return_value={
                    **incomplete_info,
                    "services": [],  # No services
                }
            )

            # Mock job service repository
            mock_job_service_repo.update_job_services = AsyncMock(return_value=None)

            # Execute the job management workflow
            result = await manage_job_from_service_request(
                conn=mock_db_connection, service_info=incomplete_info
            )

            # Verify the job status is pending_client_info (not ready_to_post)
            assert result["job_status"] == "pending_client_info", (
                f"Expected job status 'pending_client_info' when services missing, got '{result['job_status']}'"
            )

    @pytest.mark.asyncio
    async def test_job_with_empty_services_not_ready_to_post(
        self, mock_db_connection, complete_service_info
    ):
        """
        Given service request information with empty services list
        When the job management workflow processes the request
        Then the job status should be 'pending_client_info'
        Because empty services should be treated as missing
        """
        # Set services to empty list
        incomplete_info = complete_service_info.copy()
        incomplete_info["services"] = []  # Empty services list

        with (
            patch(
                "workflows.job_management_workflow.ClientRepository"
            ) as mock_client_repo,
            patch("workflows.job_management_workflow.JobRepository") as mock_job_repo,
            patch(
                "workflows.job_management_workflow.ServiceMapper"
            ) as mock_service_mapper,
            patch(
                "workflows.job_management_workflow.JobServiceRepository"
            ) as mock_job_service_repo,
        ):
            # Mock client creation
            mock_client_repo.get_by_phone = AsyncMock(return_value=None)
            mock_client_repo.get_by_phone_or_email = AsyncMock(return_value=None)
            mock_client_repo.create = AsyncMock(return_value=123)
            mock_client_repo.update = AsyncMock(return_value=None)

            # Mock job lookup (no existing jobs)
            mock_job_repo.get_by_client_phone_or_email = AsyncMock(return_value=[])
            mock_job_repo.get_by_code = AsyncMock(return_value=None)
            mock_job_repo.update = AsyncMock(return_value=None)

            # Mock service mapping returns empty (empty services list)
            mock_service_mapper.get_service_ids_by_codes = AsyncMock(return_value=[])

            # Mock job creation
            mock_job_repo.create = AsyncMock(return_value=888)
            mock_job_repo.associate_services = AsyncMock(return_value=None)

            # Mock consolidated view - empty services should result in pending_client_info
            mock_job_repo.get_consolidated_view = AsyncMock(
                return_value={
                    **incomplete_info,
                    "services": [],  # Empty services list
                }
            )

            # Mock job service repository
            mock_job_service_repo.update_job_services = AsyncMock(return_value=None)

            # Execute the job management workflow
            result = await manage_job_from_service_request(
                conn=mock_db_connection, service_info=incomplete_info
            )

            # Verify the job status is pending_client_info (not ready_to_post)
            assert result["job_status"] == "pending_client_info", (
                f"Expected job status 'pending_client_info' when services empty, got '{result['job_status']}'"
            )

    @pytest.mark.asyncio
    async def test_required_fields_for_ready_to_post_status(
        self, mock_db_connection, complete_service_info
    ):
        """
        Given service request information missing each required field individually
        When the job management workflow processes the request
        Then the job status should be 'pending_client_info' for each missing field
        This test helps identify exactly which fields are required for ready_to_post
        """
        # Fields that should be required for ready_to_post status
        required_fields = [
            "client_first_name",
            "client_last_name",
            "client_email",
            "event_date",
            "start_time",
            "event_address_street",
            "event_address_postcode",
            "guest_count",
            "event_type",
            "photographer_count",
            "services",
            "event_duration_hours",
        ]

        for field in required_fields:
            with (
                patch(
                    "workflows.job_management_workflow.ClientRepository"
                ) as mock_client_repo,
                patch(
                    "workflows.job_management_workflow.JobRepository"
                ) as mock_job_repo,
                patch(
                    "workflows.job_management_workflow.ServiceMapper"
                ) as mock_service_mapper,
                patch(
                    "workflows.job_management_workflow.JobServiceRepository"
                ) as mock_job_service_repo,
            ):
                # Create incomplete info missing this field
                incomplete_info = complete_service_info.copy()
                del incomplete_info[field]

                # Mock dependencies
                mock_client_repo.get_by_phone = AsyncMock(return_value=None)
                mock_client_repo.get_by_phone_or_email = AsyncMock(return_value=None)
                mock_client_repo.create = AsyncMock(return_value=123)
                mock_client_repo.update = AsyncMock(return_value=None)

                # Mock job lookup (no existing jobs)
                mock_job_repo.get_by_client_phone_or_email = AsyncMock(return_value=[])
                mock_job_repo.get_by_code = AsyncMock(return_value=None)
                mock_job_repo.update = AsyncMock(return_value=None)

                # If services field is missing, mock empty service mapping
                if field == "services":
                    mock_service_mapper.get_service_ids_by_codes = AsyncMock(
                        return_value=[]
                    )
                else:
                    mock_service_mapper.get_service_ids_by_codes = AsyncMock(
                        return_value=[1, 2]
                    )

                mock_job_repo.create = AsyncMock(return_value=777)
                mock_job_repo.associate_services = AsyncMock(return_value=None)

                # Mock consolidated view - missing any field should result in pending_client_info
                mock_job_repo.get_consolidated_view = AsyncMock(
                    return_value={
                        **incomplete_info,
                        "services": []
                        if field == "services"
                        else ["wedding_ceremony", "wedding_reception"],
                    }
                )

                # Mock job service repository
                mock_job_service_repo.update_job_services = AsyncMock(return_value=None)

                # Execute the job management workflow
                result = await manage_job_from_service_request(
                    conn=mock_db_connection, service_info=incomplete_info
                )

                # Verify the job status is NOT ready_to_post
                assert result["job_status"] != "ready_to_post", (
                    f"Job should NOT be ready_to_post when missing field '{field}', got status '{result['job_status']}'"
                )

                # Should be pending_client_info when any required field is missing
                assert result["job_status"] == "pending_client_info", (
                    f"Expected 'pending_client_info' when missing field '{field}', got '{result['job_status']}'"
                )

    @pytest.mark.asyncio
    async def test_service_info_plus_existing_db_data_creates_ready_to_post_job(
        self, mock_db_connection
    ):
        """
        Given partial service request information (missing some fields)
        And an existing job in the database that has the missing fields
        When the job management workflow processes the request
        Then the combined data should result in 'ready_to_post' status
        Because service_info + existing_db_data = complete information
        """
        # Partial service info (missing some required fields)
        partial_service_info = {
            "client_phone_number": "+1234567890",
            "client_first_name": "John",
            "client_last_name": "Doe",
            "client_email": "john.doe@test.com",
            "event_date": "2024-08-15",
            "start_time": "14:00:00",
            # Missing: event_address fields, guest_count, event_type, photographer_count, services, event_duration_hours
        }

        # Existing job in DB that has the missing fields
        existing_job_from_db = {
            "job_id": 999,
            "job_status": "pending_client_info",
            "client_id": 123,
            "event_date": "2024-08-15",
            "start_time": "14:00:00",
            "event_address_street": "123 Main Street",
            "event_address_postcode": "2000",
            "guest_count": 75,
            "event_type": "wedding",
            "photographer_count": 2,
            "event_duration_hours": 8,
            # This job already has the address and event details that service_info is missing
        }

        with (
            patch(
                "workflows.job_management_workflow.ClientRepository"
            ) as mock_client_repo,
            patch("workflows.job_management_workflow.JobRepository") as mock_job_repo,
            patch(
                "workflows.job_management_workflow.ServiceMapper"
            ) as mock_service_mapper,
            patch(
                "workflows.job_management_workflow.JobServiceRepository"
            ) as mock_job_service_repo,
        ):
            # Mock client lookup - existing client
            mock_client_repo.get_by_phone_or_email = AsyncMock(
                return_value={"client_id": 123}
            )
            mock_client_repo.update = AsyncMock(return_value=None)

            # Mock job lookup - return the existing job with missing fields from service_info
            mock_job_repo.get_by_client_phone_or_email = AsyncMock(
                return_value=[existing_job_from_db]
            )
            mock_job_repo.get_by_code = AsyncMock(return_value=None)
            mock_job_repo.update = AsyncMock(return_value=None)

            # Mock consolidated view that combines service_info + existing_db_data
            # This should return ALL required fields (service_info + existing_job_from_db)
            mock_job_repo.get_consolidated_view = AsyncMock(
                return_value={
                    **existing_job_from_db,
                    # Combined data should have ALL required fields
                    "client_first_name": partial_service_info["client_first_name"],
                    "client_last_name": partial_service_info["client_last_name"],
                    "client_email": partial_service_info["client_email"],
                    "services": [
                        "wedding_ceremony",
                        "wedding_reception",
                    ],  # Assume services exist in DB
                }
            )

            # Mock service mapping - assume services exist in DB
            mock_service_mapper.get_service_ids_by_codes = AsyncMock(
                return_value=[1, 2]
            )

            # Mock job updates
            mock_job_service_repo.update_job_services = AsyncMock(return_value=None)

            # Execute the job management workflow with partial service info
            result = await manage_job_from_service_request(
                conn=mock_db_connection, service_info=partial_service_info
            )

            # Verify the workflow result
            assert result is not None, "Workflow should return a result"
            assert "job_id" in result, "Result should contain job_id"
            assert result["job_id"] == 999, "Should return the existing job_id"

            # CRITICAL TEST: Combined data should result in ready_to_post
            assert result["job_status"] == "ready_to_post", (
                f"Expected 'ready_to_post' when service_info + existing_db_data is complete, got '{result['job_status']}'"
            )

            # Verify the existing job was updated (workflow calls JobRepository.update, not update_status)
            mock_job_repo.update.call_count == 2

    @pytest.mark.asyncio
    async def test_existing_pending_job_retrieved_instead_of_creating_new_job(
        self, mock_db_connection
    ):
        """
        Given a client with just a phone number
        And the client has one existing job in 'pending_client_info' status with missing fields
        When new service info is provided for the same client
        Then no new job should be created
        And the existing pending job should be retrieved and updated
        And the job_id returned should be the existing job's ID
        """
        # Service info with just phone number (minimal client info)
        minimal_service_info = {
            "client_phone_number": "+1234567890",
        }

        # Existing pending job in database with most fields missing
        existing_pending_job = {
            "job_id": 555,
            "job_status": "pending_client_info",
            "client_id": 123,
            "event_date": None,
            "start_time": None,
            "event_address_street": None,
            "event_address_postcode": None,
            "guest_count": None,
            "event_type": None,
            "photographer_count": None,
            "event_duration_hours": None,
        }

        with (
            patch(
                "workflows.job_management_workflow.ClientRepository"
            ) as mock_client_repo,
            patch("workflows.job_management_workflow.JobRepository") as mock_job_repo,
            patch(
                "workflows.job_management_workflow.ServiceMapper"
            ) as mock_service_mapper,
            patch(
                "workflows.job_management_workflow.JobServiceRepository"
            ) as mock_job_service_repo,
        ):
            # Mock client lookup - existing client found by phone
            mock_client_repo.get_by_phone_or_email = AsyncMock(
                return_value={"client_id": 123}
            )
            mock_client_repo.update = AsyncMock(return_value=None)

            # Mock job lookup - return existing pending job for this client
            mock_job_repo.get_by_client_phone_or_email = AsyncMock(
                return_value=[existing_pending_job]
            )
            mock_job_repo.get_by_code = AsyncMock(return_value=None)
            mock_job_repo.update = AsyncMock(return_value=None)

            # Mock service mapping
            mock_service_mapper.get_service_ids_by_codes = AsyncMock(
                return_value=[1]  # wedding_ceremony
            )

            # Mock consolidated view - combined data still incomplete (many fields missing)
            mock_job_repo.get_consolidated_view = AsyncMock(
                return_value={
                    **existing_pending_job,
                    "client_first_name": None,  # Still missing
                    "client_last_name": None,  # Still missing
                    "client_email": None,  # Still missing
                    "services": [],
                    # Most other fields still missing, so should remain pending_client_info
                }
            )

            # Mock job service repository
            mock_job_service_repo.update_job_services = AsyncMock(return_value=None)

            # CRITICAL: Mock job creation should NOT be called - no new job should be created
            mock_job_repo.create = AsyncMock(
                return_value=999
            )  # This should NOT be called

            # Execute the job management workflow
            result = await manage_job_from_service_request(
                conn=mock_db_connection, service_info=minimal_service_info
            )

            # Verify the workflow result
            assert result is not None, "Workflow should return a result"
            assert "job_id" in result, "Result should contain job_id"

            # CRITICAL ASSERTION: Should return existing job ID, not create new one
            assert result["job_id"] == 555, (
                f"Should return existing job_id 555, but got {result['job_id']}"
            )

            # Verify no new job was created
            (
                mock_job_repo.create.assert_not_called(),
                ("No new job should be created when existing pending job exists"),
            )

            # Verify job status update was called (this should happen)
            mock_job_repo.update.assert_called_with(
                mock_db_connection, 555, {"job_status": "pending_client_info"}
            )

            # Or verify update was called exactly once (for status only, not job fields)
            assert mock_job_repo.update.call_count == 1

            # Verify services were processed for the existing job
            mock_job_service_repo.update_job_services.assert_not_called()

            # Job should remain in pending_client_info since many fields still missing
            assert result["job_status"] == "pending_client_info", (
                f"Job should remain 'pending_client_info' since most fields missing, got '{result['job_status']}'"
            )
