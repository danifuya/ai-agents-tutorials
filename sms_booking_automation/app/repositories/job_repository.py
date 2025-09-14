from typing import Dict, Any, List, Optional
import logging

from services.database_service import DatabaseService

logger = logging.getLogger(__name__)


class JobRepository:
    @staticmethod
    async def get_by_client_id(conn, client_id: int) -> List[Dict[str, Any]]:
        """Retrieve jobs by client id from database."""
        query = """
            SELECT j.* 
            FROM jobs j
            WHERE j.client_id = %s
        """
        return await DatabaseService.fetch_all(conn, query, (client_id,))

    @staticmethod
    async def get_by_client_email(conn, client_email: str) -> List[Dict[str, Any]]:
        """Retrieve jobs by client email from database."""
        query = """
            SELECT j.* 
            FROM jobs j
            JOIN clients c ON j.client_id = c.client_id
            WHERE c.email_address = %s
        """
        return await DatabaseService.fetch_all(conn, query, (client_email,))

    @staticmethod
    async def get_by_client_phone(conn, phone_number: str) -> List[Dict[str, Any]]:
        """Retrieve jobs by client phone from database."""
        query = """
            SELECT j.* 
            FROM jobs j
            JOIN clients c ON j.client_id = c.client_id
            WHERE c.phone_number = %s
        """
        return await DatabaseService.fetch_all(conn, query, (phone_number,))

    @staticmethod
    async def get_by_client_phone_or_email(
        conn, phone_number: Optional[str] = None, email: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve unique jobs by client phone number or email from the database.
        At least one identifier (phone_number or email) must be provided.
        """
        if not phone_number and not email:
            raise ValueError("At least one of phone_number or email must be provided.")

        query_conditions = []
        params = []

        if phone_number:
            query_conditions.append("c.phone_number = %s")
            params.append(phone_number)
        if email:
            query_conditions.append("c.email_address = %s")
            params.append(email)

        where_clause = " OR ".join(query_conditions)

        query = f"""
            SELECT DISTINCT j.*
            FROM jobs j
            JOIN clients c ON j.client_id = c.client_id
            WHERE {where_clause}
        """
        return await DatabaseService.fetch_all(conn, query, tuple(params))

    @staticmethod
    async def get_by_id(conn, job_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a single job by its primary key."""
        query = "SELECT * FROM jobs WHERE job_id = %s"
        return await DatabaseService.fetch_one(conn, query, (job_id,))

    @staticmethod
    async def get_by_code(conn, job_code: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single job by its unique job_code."""
        query = "SELECT * FROM jobs WHERE job_code = %s"
        return await DatabaseService.fetch_one(conn, query, (job_code,))

    @staticmethod
    async def create(conn, job_data: Dict[str, Any]) -> Optional[int]:
        """
        Creates a new job from a dictionary of data and returns the new job_id.
        """
        if "client_id" not in job_data or "job_code" not in job_data:
            logger.error("client_id and job_code are required to create a job.")
            raise ValueError("client_id and job_code are required.")

        columns = job_data.keys()
        values = job_data.values()

        query = f"""
            INSERT INTO jobs ({", ".join(columns)})
            VALUES ({", ".join(["%s"] * len(values))})
            RETURNING job_id
        """

        try:
            job_id = await DatabaseService.fetch_val(conn, query, tuple(values))
            logger.info(f"✅ Successfully created job with ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"❌ Error creating job: {e}")
            return None

    @staticmethod
    async def update(conn, job_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Updates an existing job from a dictionary of data.
        Returns True on success, False otherwise.
        """
        if not update_data:
            logger.warning(f"⚠️ Update called with no data for job_id: {job_id}")
            return False

        set_parts = [f"{key} = %s" for key in update_data.keys()]
        set_clause = ", ".join(set_parts)

        query = f"""
            UPDATE jobs
            SET {set_clause}, updated_at = NOW()
            WHERE job_id = %s
        """

        values = list(update_data.values())
        values.append(job_id)

        try:
            await DatabaseService.execute(conn, query, tuple(values))
            logger.info(f"✅ Successfully updated job with ID: {job_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating job {job_id}: {e}")
            return False

    @staticmethod
    async def get_consolidated_view(conn, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves a consolidated view of a job and its associated client
        and service details, structured similarly to ServiceRequestInfo.
        """
        query = """
            SELECT
                j.job_id AS service_id,
                j.job_status,
                j.client_id,
                c.first_name AS client_first_name,
                c.last_name AS client_last_name,
                c.email_address AS client_email,
                c.phone_number AS client_phone_number,
                j.event_date,
                j.event_start_time AS start_time,
                j.event_address_street,
                j.event_address_postcode,
                j.guest_count,
                j.event_type,
                j.photographer_count,
                j.event_duration_hours,
                COALESCE(ARRAY_AGG(s.name) FILTER (WHERE s.name IS NOT NULL), '{}') AS services
            FROM
                jobs j
            JOIN
                clients c ON j.client_id = c.client_id
            LEFT JOIN
                job_services js ON j.job_id = js.job_id
            LEFT JOIN
                services s ON js.service_id = s.service_id
            WHERE
                j.job_id = %s
            GROUP BY
                j.job_id, c.client_id
        """
        return await DatabaseService.fetch_one(conn, query, (job_id,))
