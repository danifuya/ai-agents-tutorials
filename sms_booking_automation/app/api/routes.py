import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Request, Response


# Import service classes
from services.celery_service import CeleryService

# Import dependency getters
from .dependencies import (
    get_celery_service,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/sms")
async def sms_webhook(
    request: Request, celery_service: CeleryService = Depends(get_celery_service)
):
    """
    Webhook endpoint for SMS API push notifications from JustCall.
    It acknowledges the request immediately and then queues a task to process the SMS.
    Handles JSON payload.
    """
    try:
        body = await request.json()
        logger.debug(f"Received SMS webhook JSON data: {body}")

        # Extract data from JustCall webhook format
        data = body.get("data", {})
        from_number = data.get("contact_number")
        sms_info = data.get("sms_info", {})
        message_body = sms_info.get("body")

        if not from_number or not message_body:
            logger.warning(
                "Webhook received with missing 'contact_number' or 'body' in data"
            )
            # Return 204 to prevent the provider from retrying
            return Response(status_code=204)

        logger.info(f"Received SMS from {from_number}. Queuing for processing.")

        # --- Delegate all logic to a Celery worker with debouncing ---
        await celery_service.queue_sms_processing_debounced(
            from_number=from_number,
            message_body=message_body,
        )
        # --------------------------------------------------------------------------

        # Acknowledge the webhook request with 204 No Content.
        return Response(status_code=204)

    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from SMS webhook", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        logger.error(f"SMS webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
