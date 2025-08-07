from fastapi import Request, HTTPException

from services.celery_service import CeleryService


def get_celery_service(request: Request) -> CeleryService:
    """Gets the Celery service instance from the application state."""
    celery_service = getattr(request.app.state, "celery_service", None)
    if not celery_service:
        raise HTTPException(status_code=503, detail="Celery service is not available.")
    return celery_service
