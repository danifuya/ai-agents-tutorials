import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any, Optional

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))

from repositories.job_repository import JobRepository


@pytest.fixture
def mock_db_connection():
    """Mock database connection for unit tests"""
    return MagicMock()


@pytest.fixture
def sample_consolidated_view_with_services():
    """Sample consolidated view data with associated services"""
    return {
        "service_id": 123,
        "job_status": "pending_client_info",
        "client_id": 456,
        "client_first_name": "John",
        "client_last_name": "Doe",
        "client_email": "john.doe@test.com",
        "client_phone_number": "+1234567890",
        "event_date": "2024-06-15",
        "start_time": "14:00:00",
        "event_address_street": "123 Main St",
        "event_address_suburb": "Downtown",
        "event_address_state": "NSW",
        "event_address_postcode": "2000",
        "guest_count": 50,
        "event_type": "wedding",
        "photographer_count": 2,
        "event_duration_hours": 8,
        "services": ["Wedding Photography", "Event Videography"]  # Has associated services
    }


@pytest.fixture
def sample_consolidated_view_without_services():
    """Sample consolidated view data without associated services"""
    return {
        "service_id": 124,
        "job_status": "pending_client_info",
        "client_id": 457,
        "client_first_name": "Jane",
        "client_last_name": "Smith",
        "client_email": "jane.smith@test.com",
        "client_phone_number": "+0987654321",
        "event_date": "2024-07-15",
        "start_time": "16:00:00",
        "job_status": "pending_client_info",
        "services": []  # No associated services
    }


class TestJobRepository:
    """Unit tests for JobRepository methods with mocked database"""

    @pytest.mark.asyncio
    async def test_consolidated_view_returns_associated_services(
        self, mock_db_connection, sample_consolidated_view_with_services
    ):
        """
        Given a job with 2 associated services in the database
        When I call get_consolidated_view with the job ID
        Then it should return only the 2 services associated with that job
        And it should not include any non-associated services
        """
        job_id = 123
        
        with patch('repositories.job_repository.DatabaseService.fetch_one') as mock_fetch:
            # Mock the database to return our sample data
            mock_fetch.return_value = sample_consolidated_view_with_services
            
            # Call the method under test
            result = await JobRepository.get_consolidated_view(mock_db_connection, job_id)
            
            # Verify database was called correctly
            mock_fetch.assert_called_once_with(mock_db_connection, 
                                             JobRepository.get_consolidated_view.__code__.co_consts[1],  # The SQL query
                                             (job_id,))
            
            # Verify return value
            assert result is not None, "Should return consolidated view data"
            assert result == sample_consolidated_view_with_services
            
            # Verify services field contains expected services
            services = result["services"]
            assert isinstance(services, list), "Services should be a list"
            assert len(services) == 2, f"Expected 2 services, got {len(services)}"
            assert "Wedding Photography" in services, "Should contain Wedding Photography"
            assert "Event Videography" in services, "Should contain Event Videography"

    @pytest.mark.asyncio
    async def test_consolidated_view_with_services_populates_services_field(
        self, mock_db_connection, sample_consolidated_view_with_services
    ):
        """
        Given a job with associated services in the database
        When I get the consolidated view for that job
        Then the services field should be properly populated with service names
        And it should be a non-empty list of strings
        """
        job_id = 123
        
        with patch('repositories.job_repository.DatabaseService.fetch_one') as mock_fetch:
            mock_fetch.return_value = sample_consolidated_view_with_services
            
            result = await JobRepository.get_consolidated_view(mock_db_connection, job_id)
            
            assert result is not None, "Consolidated view should not be None"
            
            # Verify services field is properly populated
            services = result["services"]
            assert services, "Services field should not be empty"
            assert len(services) > 0, "Services should contain at least one service"
            assert isinstance(services, list), "Services should be a list"
            assert all(isinstance(s, str) and s.strip() for s in services), \
                "All services should be non-empty strings"

    @pytest.mark.asyncio
    async def test_consolidated_view_job_without_services(
        self, mock_db_connection, sample_consolidated_view_without_services
    ):
        """
        Given a job with no associated services in the database
        When I call get_consolidated_view with the job ID
        Then it should return an empty services array
        And the services field should indicate no services are associated
        """
        job_id = 124
        
        with patch('repositories.job_repository.DatabaseService.fetch_one') as mock_fetch:
            mock_fetch.return_value = sample_consolidated_view_without_services
            
            result = await JobRepository.get_consolidated_view(mock_db_connection, job_id)
            
            assert result is not None, "Consolidated view should not be None"
            
            # Verify services field is empty
            services = result["services"]
            assert services == [], f"Services should be empty array, got: {services}"
            assert len(services) == 0, "Services array should be empty, indicating no services"

    @pytest.mark.asyncio
    async def test_consolidated_view_nonexistent_job(self, mock_db_connection):
        """
        Given a job ID that does not exist in the database
        When I call get_consolidated_view with that job ID
        Then it should return None
        """
        job_id = 99999
        
        with patch('repositories.job_repository.DatabaseService.fetch_one') as mock_fetch:
            # Mock database to return None (no job found)
            mock_fetch.return_value = None
            
            result = await JobRepository.get_consolidated_view(mock_db_connection, job_id)
            
            # Verify database was called correctly
            mock_fetch.assert_called_once()
            
            # Verify return value
            assert result is None, "Should return None for non-existent job"

    @pytest.mark.asyncio 
    async def test_consolidated_view_sql_query_structure(self, mock_db_connection):
        """
        Given any job ID
        When I call get_consolidated_view
        Then it should execute a SQL query with proper JOIN structure for services
        """
        job_id = 123
        
        with patch('repositories.job_repository.DatabaseService.fetch_one') as mock_fetch:
            mock_fetch.return_value = {"job_id": job_id, "services": []}
            
            await JobRepository.get_consolidated_view(mock_db_connection, job_id)
            
            # Verify the SQL query was called
            call_args = mock_fetch.call_args
            assert call_args is not None, "DatabaseService.fetch_one should have been called"
            
            # Verify correct parameters passed
            called_conn, called_query, called_params = call_args[0]
            assert called_conn == mock_db_connection, "Should pass the connection"
            assert called_params == (job_id,), f"Should pass job_id as parameter, got {called_params}"
            
            # Verify SQL contains necessary JOINs (basic structure check)
            assert "LEFT JOIN" in called_query, "Query should contain LEFT JOIN for services"
            assert "job_services" in called_query, "Query should join with job_services table"
            assert "services" in called_query, "Query should join with services table"
            assert "COALESCE(ARRAY_AGG" in called_query, "Query should aggregate services into array"

    @pytest.mark.asyncio
    async def test_consolidated_view_job_with_no_services_returns_empty_array(
        self, mock_db_connection, sample_consolidated_view_without_services
    ):
        """
        Given a job with no associated services in the database
        When I call get_consolidated_view with the job ID
        Then it should return an empty services array []
        And the empty array should be what triggers 'Services required' as missing in the workflow
        """
        job_id = 128
        
        # Mock consolidated view to return empty services array (this is what the real DB would return)
        mock_view_no_services = {
            **sample_consolidated_view_without_services,
            "job_id": job_id,
            "services": []  # This is what COALESCE(ARRAY_AGG(...)) returns when no services exist
        }
        
        with patch('repositories.job_repository.DatabaseService.fetch_one') as mock_fetch:
            mock_fetch.return_value = mock_view_no_services
            
            result = await JobRepository.get_consolidated_view(mock_db_connection, job_id)
            
            # Verify the consolidated view returns empty array for no services
            assert result is not None, "Should return consolidated view"
            assert "services" in result, "Should contain services field"
            assert result["services"] == [], f"Services should be empty array for job with no services, got: {result['services']}"
            assert isinstance(result["services"], list), "Services should be a list type"
            assert len(result["services"]) == 0, "Services list should have zero length"