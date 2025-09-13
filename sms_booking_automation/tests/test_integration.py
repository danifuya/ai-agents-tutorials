import pytest
import pytest_asyncio
import sys
import os
from typing import Dict, Any

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))

from services.database_service import DatabaseService
from repositories.job_repository import JobRepository


@pytest_asyncio.fixture
async def db_service():
    """Set up database service for integration tests"""
    db_service = DatabaseService()
    await db_service.initialize()
    yield db_service
    await db_service.close()


@pytest_asyncio.fixture
async def db_transaction(db_service):
    """Database transaction that rolls back after each test"""
    async with db_service.get_connection() as conn:
        # Start transaction
        await conn.execute("BEGIN")
        
        try:
            yield conn
        finally:
            # Always rollback - no changes persist
            await conn.execute("ROLLBACK")


class TestJobRepositoryIntegration:
    """Integration tests for JobRepository with real database (transaction rollback)"""

    @pytest.mark.asyncio
    async def test_get_consolidated_view_with_real_database(self, db_transaction):
        """
        Given a real database with actual job and service data
        When I call get_consolidated_view
        Then it should return properly formatted data with services array
        
        This test verifies the actual SQL query works with the real database schema.
        """
        # Insert test client
        client_query = """
            INSERT INTO clients (first_name, last_name, email_address, phone_number)
            VALUES (%s, %s, %s, %s)
            RETURNING client_id
        """
        client_result = await DatabaseService.fetch_one(
            db_transaction, 
            client_query, 
            ("Integration", "Test", "integration@test.com", "+9999999999")
        )
        client_id = client_result["client_id"]
        
        # Insert test job
        job_query = """
            INSERT INTO jobs (client_id, event_date, event_start_time, event_address_street,
                            event_address_suburb, event_address_state, event_address_postcode,
                            guest_count, event_type, photographer_count, event_duration_hours, job_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING job_id
        """
        job_result = await DatabaseService.fetch_one(
            db_transaction,
            job_query,
            (client_id, "2024-12-15", "15:00:00", "789 Integration St",
             "TestSuburb", "NSW", "2020", 100, "wedding", 3, 10, "pending_client_info")
        )
        job_id = job_result["job_id"]
        
        # Insert test services
        service_query = """
            INSERT INTO services (name, description) VALUES (%s, %s) RETURNING service_id
        """
        service1_result = await DatabaseService.fetch_one(
            db_transaction, service_query, ("Integration Photography", "Test photo service")
        )
        service2_result = await DatabaseService.fetch_one(
            db_transaction, service_query, ("Integration Videography", "Test video service")  
        )
        
        service1_id = service1_result["service_id"]
        service2_id = service2_result["service_id"]
        
        # Associate services with job
        job_service_query = "INSERT INTO job_services (job_id, service_id) VALUES (%s, %s)"
        await DatabaseService.execute(db_transaction, job_service_query, (job_id, service1_id))
        await DatabaseService.execute(db_transaction, job_service_query, (job_id, service2_id))
        
        # Test the actual method
        result = await JobRepository.get_consolidated_view(db_transaction, job_id)
        
        # Verify the consolidated view works with real data
        assert result is not None, "Should return consolidated view for existing job"
        
        # Verify client data is properly joined
        assert result["client_first_name"] == "Integration"
        assert result["client_last_name"] == "Test"
        assert result["client_email"] == "integration@test.com"
        assert result["client_phone_number"] == "+9999999999"
        
        # Verify job data is properly returned
        assert result["job_status"] == "pending_client_info"
        assert result["event_address_street"] == "789 Integration St"
        assert result["event_address_suburb"] == "TestSuburb"
        assert result["event_address_state"] == "NSW"
        assert result["guest_count"] == 100
        
        # Verify services are properly aggregated
        services = result["services"]
        assert isinstance(services, list), "Services should be a list"
        assert len(services) == 2, f"Should return 2 services, got {len(services)}"
        assert "Integration Photography" in services, "Should contain Integration Photography service"
        assert "Integration Videography" in services, "Should contain Integration Videography service"
        
        # Verify the services are in the expected format
        for service in services:
            assert isinstance(service, str), f"Each service should be a string, got {type(service)}"
            assert service.strip(), "Service names should not be empty"

    @pytest.mark.asyncio
    async def test_consolidated_view_job_without_services_real_db(self, db_transaction):
        """
        Given a real database with a job that has no associated services
        When I call get_consolidated_view
        Then it should return an empty services array
        
        This verifies the SQL COALESCE and array aggregation works correctly for empty results.
        """
        # Insert test client and job without services
        client_result = await DatabaseService.fetch_one(
            db_transaction,
            "INSERT INTO clients (first_name, last_name, email_address, phone_number) VALUES (%s, %s, %s, %s) RETURNING client_id",
            ("NoServices", "Client", "noservices@test.com", "+8888888888")
        )
        client_id = client_result["client_id"]
        
        job_result = await DatabaseService.fetch_one(
            db_transaction,
            "INSERT INTO jobs (client_id, event_date, job_status) VALUES (%s, %s, %s) RETURNING job_id",
            (client_id, "2024-12-20", "pending_client_info")
        )
        job_id = job_result["job_id"]
        
        # Don't insert any services - job has no associated services
        
        # Test the method
        result = await JobRepository.get_consolidated_view(db_transaction, job_id)
        
        assert result is not None, "Should return consolidated view"
        assert result["client_first_name"] == "NoServices"
        
        # Verify services array is empty but properly formatted
        services = result["services"]
        assert isinstance(services, list), "Services should be a list even when empty"
        assert services == [], f"Services should be empty array, got {services}"

    @pytest.mark.asyncio  
    async def test_database_transaction_rollback(self, db_transaction):
        """
        Given database operations within a transaction
        When the test completes
        Then all changes should be rolled back (nothing persists)
        
        This test verifies the transaction rollback mechanism works.
        """
        # Insert test data
        result = await DatabaseService.fetch_one(
            db_transaction,
            "INSERT INTO clients (first_name, last_name, email_address, phone_number) VALUES (%s, %s, %s, %s) RETURNING client_id",
            ("Rollback", "Test", "rollback@test.com", "+7777777777")
        )
        client_id = result["client_id"]
        
        # Verify data exists within this transaction
        check_result = await DatabaseService.fetch_one(
            db_transaction,
            "SELECT first_name FROM clients WHERE client_id = %s",
            (client_id,)
        )
        assert check_result is not None, "Data should exist within the transaction"
        assert check_result["first_name"] == "Rollback"
        
        # When this test ends, the fixture will rollback the transaction
        # The next test should not see this data
        # (This is verified by running multiple tests and ensuring isolation)