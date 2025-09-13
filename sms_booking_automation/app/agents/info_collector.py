from pydantic_ai import Agent
from pydantic import BaseModel, Field
from datetime import date, time, datetime
from typing import Optional, List
from enum import StrEnum

import logfire

logfire.configure()


class EventType(StrEnum):
    WEDDING = "wedding"
    CORPORATE = "corporate"
    BIRTHDAY_PARTY = "birthday_party"
    GRADUATION = "graduation"
    ANNIVERSARY = "anniversary"
    FAMILY_REUNION = "family_reunion"
    OTHER = "other"


class ServiceCode(StrEnum):
    # ─────── Wedding Photography ───────────────────────
    WEDDING_CEREMONY = "wedding_ceremony"
    WEDDING_RECEPTION = "wedding_reception"
    WEDDING_FULL_DAY = "wedding_full_day"

    # ─────── Portrait Photography ─────────────────────
    PORTRAIT_INDIVIDUAL = "portrait_individual"
    PORTRAIT_FAMILY = "portrait_family"
    PORTRAIT_CORPORATE = "portrait_corporate"

    # ─────── Event Photography ────────────────────────
    EVENT_CORPORATE = "event_corporate"
    EVENT_BIRTHDAY = "event_birthday"
    EVENT_GRADUATION = "event_graduation"
    EVENT_ANNIVERSARY = "event_anniversary"

    # ─────── Photography Packages ─────────────────────
    PACKAGE_BASIC = "package_basic"
    PACKAGE_STANDARD = "package_standard"
    PACKAGE_PREMIUM = "package_premium"
    PACKAGE_DELUXE = "package_deluxe"


class ServiceRequestInfo(BaseModel):
    service_id: Optional[int] = Field(description="The id of the service")
    client_first_name: Optional[str] = Field(
        description="First name of the client making the request"
    )
    client_last_name: Optional[str] = Field(
        description="Last name of the client making the request"
    )
    client_email: Optional[str] = Field(
        description="Email address of the client making the request"
    )
    client_phone_number: Optional[str] = Field(
        description="Phone number of the client making the request with country code e.g. +61412345678"
    )
    event_date: Optional[date] = Field(
        description="Date when the service will take place in the format YYYY-MM-DD"
    )
    start_time: Optional[time] = Field(
        description="The time the event starts in 24 hour format, e.g 18:30"
    )
    event_address_street: Optional[str] = Field(
        description="Street address of the event place including number and street name"
    )
    event_address_suburb: Optional[str] = Field(
        description="Suburb or city name of the event place"
    )
    event_address_state: Optional[str] = Field(
        description="State or territory abbreviation of the event place"
    )
    event_address_postcode: Optional[str] = Field(
        description="Postal code of the event place"
    )
    guest_count: Optional[int] = Field(
        ge=1, le=5_000, description="Total number of guests expected at the event"
    )
    event_type: Optional[EventType] = Field(
        description="Type of event (wedding, corporate, birthday_party, etc.)"
    )
    photographer_count: Optional[int] = Field(
        ge=1,
        le=10,
        description="Number of photographers requested for the event",
    )
    services: Optional[List[ServiceCode]] = Field(
        description="Service code from the official list"
    )
    event_duration_hours: Optional[float] = Field(
        description="Duration of the entire event in hours (e.g., 3.0 for 3 hours, 2.5 for 2.5 hours)"
    )


# Get current date
def get_current_date() -> str:
    """Get current date formatted as YYYY-MM-DD"""
    current_date = datetime.now().date()
    return current_date.strftime("%Y-%m-%d")


# Define the email classification agent
info_collector_agent = Agent(
    model="openai:gpt-4o-mini",
    retries=3,
    system_prompt=f"""You are an AI assistant that collects information from client requests to book professional photography services.
    You will be provided with conversations between the client and the photography agency.
    Your task is to detect if the client has provided all the relevant information to book a photography service.
    Today's date is {get_current_date()}
    Required information:
    - Reference id
    - Client first name
    - Client last name
    - Client email
    - Client phone number
    - Date when service should take place
    - Starting time of the event
    - Address of the event (street, suburb, state, postcode)
    - Photography services required
    - Number of guests
    - Event type (wedding, corporate, birthday_party, graduation, anniversary, family_reunion, or other)
    - Number of photographers requested (how many photographers the client wants to book)
    - Duration of the event in hours
    - Service id (as reference id)
    If information is missing, return null for the missing information.
    Do not omit any fields when calling output tool. Do not call the output tool more than once in the same message.
    
    Example Conversation format:
    [user]: Hi there
    [user]: I'm looking for a photographer for my wedding on 2025-08-01 at 18:30
    [assistant]: Sure, what's your name?
    [user]: John Doe
    
    Example Output:
    
"service_id": null,
"client_first_name": "John",
"client_last_name": "Doe",
"client_email": "null",
"client_phone_number": null,
"event_date": "2025-08-01",
"start_time": "18:30",
"event_address_street": null,
"event_address_suburb": null,
"event_address_state": null,
"event_address_postcode": null,
"guest_count": null,
"event_type": "wedding",
"photographer_count": null,
"services": null,
"event_duration_hours": null,

    """,
    output_type=ServiceRequestInfo,
    instrument=True,
)
