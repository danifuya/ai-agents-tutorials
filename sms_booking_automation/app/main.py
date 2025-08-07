import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

from api.routes import router
from services.redis_service import RedisService
from services.celery_service import CeleryService

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events with proper dependency injection."""
    logger.info(f"🚀 Application starting up in {ENVIRONMENT} environment...")

    redis_service = RedisService()
    await redis_service.initialize()
    app.state.redis_service = redis_service

    # Initialize Celery (pass redis_service for debouncing)
    celery_service = CeleryService(redis_service=redis_service)
    await celery_service.initialize()
    app.state.celery_service = celery_service

    logger.info("✅ Application startup complete.")
    yield

    # --- Shutdown ---
    logger.info("🛑 Application shutting down...")
    if hasattr(app.state, "redis_service") and app.state.redis_service:
        await app.state.redis_service.close()
        logger.info("Redis connection closed.")
    logger.info("✅ Application shutdown complete.")


# Create FastAPI app
app = FastAPI(
    title="Photography Booking API",
    description="FastAPI server for automated photography service bookings",
    version="1.0.0",
    lifespan=lifespan,
)

# Include API routes
app.include_router(router)

if __name__ == "__main__":
    is_development = ENVIRONMENT == "development"

    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=is_development,
        log_level="info",
    )
