from typing import List
import logging
from agents.info_collector import ServiceCode
from repositories.service_repository import ServiceRepository

logger = logging.getLogger(__name__)


class ServiceMapper:
    """Maps service codes from info collector to database service IDs."""

    @classmethod
    async def get_service_ids_by_codes(
        cls, conn, service_codes: List[ServiceCode]
    ) -> List[int]:
        """
        Convert list of ServiceCode enums to database service IDs.
        
        Args:
            conn: Database connection
            service_codes: List of ServiceCode enums from info collector
            
        Returns:
            List of service IDs that exist in the database
        """
        if not service_codes:
            return []
        
        # Convert ServiceCode enums to string codes for database lookup
        code_strings = [str(code) for code in service_codes]
        
        # Get services from database by codes
        services = await ServiceRepository.get_by_codes(conn, code_strings)
        
        # Extract service IDs
        service_ids = [service["service_id"] for service in services]
        
        # Log missing services
        found_codes = {service["code"] for service in services}
        missing_codes = set(code_strings) - found_codes
        if missing_codes:
            logger.warning(f"Service codes not found in database: {missing_codes}")
        
        logger.info(f"Mapped {len(service_codes)} service codes to {len(service_ids)} database service IDs")
        return service_ids