from fastapi import Request, HTTPException
from typing import AsyncGenerator, Optional

# Import Service classes
from services.database_service import DatabaseService
from services.celery_service import CeleryService
from services.redis_service import RedisService
from services.justcall_service import JustCallService


def get_db_service(request: Request) -> DatabaseService:
    """Gets the database service instance from the application state."""
    db_service: Optional[DatabaseService] = getattr(
        request.app.state, "db_service", None
    )
    if not db_service or not db_service.is_available():
        raise HTTPException(
            status_code=503, detail="Database service is not available."
        )
    return db_service


def get_celery_service(request: Request) -> CeleryService:
    """Gets the Celery service instance from the application state."""
    celery_service = getattr(request.app.state, "celery_service", None)
    if not celery_service:
        raise HTTPException(status_code=503, detail="Celery service is not available.")
    return celery_service


def get_redis_service(request: Request) -> RedisService:
    """Gets the Redis service instance from the application state."""
    redis_service = getattr(request.app.state, "redis_service", None)
    if not redis_service:
        raise HTTPException(status_code=503, detail="Redis service is not available.")
    return redis_service


def get_justcall_service(request: Request) -> JustCallService:
    """Gets the JustCall service instance from the application state."""
    justcall_service = getattr(request.app.state, "justcall_service", None)
    if not justcall_service:
        raise HTTPException(
            status_code=503, detail="JustCall service is not available."
        )
    return justcall_service


# --- Connection Dependency ---


async def get_db_connection(request: Request) -> AsyncGenerator:
    """
    Dependency that provides a single database connection with a transaction
    for the scope of a single request. It handles acquiring a connection,
    starting a transaction, and committing or rolling back.
    """
    db_service: Optional[DatabaseService] = getattr(
        request.app.state, "db_service", None
    )
    if not db_service or not db_service.is_available():
        raise HTTPException(
            status_code=503, detail="Database service is not available."
        )
    # get_connection is a context manager that gets a connection from the pool
    async with db_service.get_connection() as conn:
        async with conn.transaction():
            yield conn
