from typing import Dict, Any, Optional, List

from services.database_service import DatabaseService
from utils.utils import normalize_phone_number


class ClientRepository:
    @staticmethod
    async def get_by_email(conn, email: str) -> Optional[Dict[str, Any]]:
        """Fetches a single client by their email address."""
        query = "SELECT * FROM clients WHERE email_address = %s LIMIT 1"
        return await DatabaseService.fetch_one(conn, query, (email,))

    @staticmethod
    async def get_by_phone(conn, phone_number: str) -> Optional[Dict[str, Any]]:
        """Fetches a single client by their phone number."""
        normalized_phone = normalize_phone_number(phone_number)
        query = "SELECT * FROM clients WHERE phone_number = %s LIMIT 1"
        return await DatabaseService.fetch_one(conn, query, (normalized_phone,))

    @staticmethod
    async def get_by_phone_or_email(
        conn, phone: Optional[str] = None, email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches a single client by their phone number first, then by email.
        At least one of phone or email must be provided.
        """
        if not phone and not email:
            raise ValueError("At least one of phone or email must be provided.")

        client = None
        if phone:
            client = await ClientRepository.get_by_phone(conn, phone)

        if not client and email:
            client = await ClientRepository.get_by_email(conn, email)

        return client

    @staticmethod
    async def get_jobs(conn, client_id: int) -> List[Dict[str, Any]]:
        """Fetches all jobs associated with a given client ID."""
        query = "SELECT * FROM jobs WHERE client_id = %s ORDER BY event_date DESC"
        return await DatabaseService.fetch_all(conn, query, (client_id,))

    @staticmethod
    async def create(
        conn,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Optional[int]:
        """
        Creates a new client and returns their new client_id.
        At least one contact method (email or phone) must be provided.
        """
        if not email and not phone:
            raise ValueError(
                "At least one contact method (email or phone) is required to create a client."
            )

        # Normalize phone number if provided
        normalized_phone = normalize_phone_number(phone) if phone else None

        query = "INSERT INTO clients (first_name, last_name, email_address, phone_number) VALUES (%s, %s, %s, %s) RETURNING client_id"
        result = await DatabaseService.fetch_val(
            conn, query, (first_name, last_name, email, normalized_phone)
        )
        return result

    @staticmethod
    async def update(conn, client_id: int, update_data: Dict[str, Any]) -> bool:
        """
        Updates an existing client with new information.
        Returns True on success, False otherwise.
        """
        if not update_data:
            return True

        # Normalize phone number if provided
        if "phone_number" in update_data and update_data["phone_number"]:
            update_data["phone_number"] = normalize_phone_number(update_data["phone_number"])

        # Build the SET clause dynamically
        set_clauses = []
        values = []
        for key, value in update_data.items():
            set_clauses.append(f"{key} = %s")
            values.append(value)

        if not set_clauses:
            return True

        query = f"UPDATE clients SET {', '.join(set_clauses)} WHERE client_id = %s"
        values.append(client_id)

        try:
            await DatabaseService.execute(conn, query, tuple(values))
            return True
        except Exception:
            return False
