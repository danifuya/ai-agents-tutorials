from typing import Dict, Any, List, Optional
import logging

from services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class ServiceRepository:
    @staticmethod
    async def get_all(conn) -> List[Dict[str, Any]]:
        """Retrieve all services from database."""
        query = """
            SELECT service_id, code, name, base_price, created_at, updated_at
            FROM services
            ORDER BY service_id
        """
        return await DatabaseService.fetch_all(conn, query)

    @staticmethod
    async def get_by_id(conn, service_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve service by ID from database."""
        query = """
            SELECT service_id, code, name, base_price, created_at, updated_at
            FROM services
            WHERE service_id = %s
        """
        return await DatabaseService.fetch_one(conn, query, (service_id,))

    @staticmethod
    async def get_by_code(conn, code: str) -> Optional[Dict[str, Any]]:
        """Retrieve service by code from database."""
        query = """
            SELECT service_id, code, name, base_price, created_at, updated_at
            FROM services
            WHERE code = %s
        """
        return await DatabaseService.fetch_one(conn, query, (code,))

    @staticmethod
    async def get_by_codes(conn, codes: List[str]) -> List[Dict[str, Any]]:
        """Retrieve services by list of codes from database."""
        if not codes:
            return []
        
        placeholders = ", ".join(["%s" for _ in codes])
        query = f"""
            SELECT service_id, code, name, base_price, created_at, updated_at
            FROM services
            WHERE code IN ({placeholders})
        """
        return await DatabaseService.fetch_all(conn, query, codes)

    @staticmethod
    async def create(conn, name: str, description: Optional[str] = None, 
                    base_price: Optional[float] = None, 
                    infographic_image_url: Optional[str] = None) -> int:
        """Create a new service and return the service_id."""
        query = """
            INSERT INTO services (name, description, base_price, infographic_image_url)
            VALUES (%s, %s, %s, %s)
            RETURNING service_id
        """
        result = await DatabaseService.fetch_one(conn, query, (name, description, base_price, infographic_image_url))
        service_id = result["service_id"]
        logger.info(f"Created new service with ID: {service_id}")
        return service_id

    @staticmethod
    async def update(conn, service_id: int, update_data: Dict[str, Any]) -> bool:
        """Update service data."""
        if not update_data:
            return True

        # Build the SET clause dynamically
        set_clauses = []
        values = []
        for key, value in update_data.items():
            if key in ["name", "description", "base_price", "infographic_image_url"]:
                set_clauses.append(f"{key} = %s")
                values.append(value)

        if not set_clauses:
            logger.warning(f"No valid fields to update for service {service_id}")
            return True

        # Add updated_at timestamp
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        values.append(service_id)

        query = f"""
            UPDATE services 
            SET {', '.join(set_clauses)}
            WHERE service_id = %s
        """

        await DatabaseService.execute(conn, query, values)
        logger.info(f"Updated service {service_id}")
        return True


class JobServiceRepository:
    @staticmethod
    async def get_by_job_id(conn, job_id: int) -> List[Dict[str, Any]]:
        """Retrieve job services by job ID from database."""
        query = """
            SELECT js.job_service_id, js.job_id, js.service_id, 
                   js.duration_hours, js.created_at, js.updated_at,
                   s.name as service_name, s.description as service_description,
                   s.base_price
            FROM job_services js
            JOIN services s ON js.service_id = s.service_id
            WHERE js.job_id = %s
            ORDER BY js.job_service_id
        """
        return await DatabaseService.fetch_all(conn, query, (job_id,))

    @staticmethod
    async def create(conn, job_id: int, service_id: int,
                    duration_hours: Optional[float] = None) -> int:
        """Create a new job service link and return the job_service_id."""
        query = """
            INSERT INTO job_services (job_id, service_id, duration_hours)
            VALUES (%s, %s, %s)
            RETURNING job_service_id
        """
        result = await DatabaseService.fetch_one(conn, query, (job_id, service_id, duration_hours))
        job_service_id = result["job_service_id"]
        logger.info(f"Created new job service link with ID: {job_service_id} (job: {job_id}, service: {service_id})")
        return job_service_id

    @staticmethod
    async def delete_by_job_id(conn, job_id: int) -> bool:
        """Delete all job services for a specific job."""
        query = """
            DELETE FROM job_services
            WHERE job_id = %s
        """
        await DatabaseService.execute(conn, query, (job_id,))
        logger.info(f"Deleted all job services for job {job_id}")
        return True

    @staticmethod
    async def update_job_services(conn, job_id: int, service_data: List[Dict[str, Any]]) -> bool:
        """
        Update job services by replacing existing ones with new service data.
        
        Args:
            conn: Database connection
            job_id: ID of the job to update services for
            service_data: List of dictionaries containing:
                - service_id: int - The service ID
                - duration_hours: Optional[float] - Duration hours for services that require it
        
        Returns:
            bool: True if successful
        """
        # First, delete existing job services
        await JobServiceRepository.delete_by_job_id(conn, job_id)
        
        # Then, create new job services with duration hours
        for service_item in service_data:
            service_id = service_item.get("service_id")
            duration_hours = service_item.get("duration_hours")
            
            if service_id:
                await JobServiceRepository.create(conn, job_id, service_id, duration_hours)
        
        logger.info(f"Updated job services for job {job_id} with {len(service_data)} services")
        return True