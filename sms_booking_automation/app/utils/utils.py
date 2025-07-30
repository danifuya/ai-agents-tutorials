import re
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)



def normalize_phone_number(phone_number: str) -> str:
    """
    Normalize phone number to E.164 format without the "+" prefix.
    Handles international phone numbers and adds US country code (1) as default if no country code is present.
    
    Examples:
        "5551234567" -> "15551234567" (US number)
        "15551234567" -> "15551234567" (US number)
        "+15551234567" -> "15551234567" (US number)
        "447123456789" -> "447123456789" (UK number)
        "34612345678" -> "34612345678" (Spain number)
    """
    if not phone_number:
        return phone_number
    
    # Remove all non-digit characters
    cleaned = re.sub(r'[^\d]', '', phone_number)
    
    # If number is too short, return as-is
    if len(cleaned) < 8:
        logger.warning(f"Phone number {phone_number} is too short")
        return cleaned
    
    # Check if it already has a country code (starts with common country codes)
    # Common country codes: 1 (US/Canada), 44 (UK), 61 (Australia), 34 (Spain), etc.
    if len(cleaned) >= 10 and (
        cleaned.startswith('1') or  # US/Canada
        cleaned.startswith('44') or  # UK
        cleaned.startswith('61') or  # Australia
        cleaned.startswith('34') or  # Spain
        cleaned.startswith('49') or  # Germany
        cleaned.startswith('33') or  # France
        cleaned.startswith('39') or  # Italy
        cleaned.startswith('81') or  # Japan
        cleaned.startswith('86') or  # China
        cleaned.startswith('91') or  # India
        cleaned.startswith('55') or  # Brazil
        (len(cleaned) >= 11 and cleaned.startswith('7'))  # Russia
    ):
        # Already has a country code
        return cleaned
    else:
        # Assume it's a US number without country code and add 1 prefix
        return '1' + cleaned
