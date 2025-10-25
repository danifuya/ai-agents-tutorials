import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logfire

from app.api.routes import router


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()


API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
# Required services
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN")

# Simple validation - check what you actually need
if not OPENAI_API_KEY:
    print("❌ OPENAI_API_KEY is required!")
    exit(1)

# Set up monitoring if credentials exist and libraries are available
if LOGFIRE_TOKEN:
    logfire.configure()
    logfire.instrument_pydantic_ai()
else:
    print("⚠️  LOGFIRE_TOKEN not found, skipping logfire configuration")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events with proper dependency injection."""
    logger.info(f"🚀 Application starting up in {ENVIRONMENT} environment...")

    logger.info("✅ Application startup complete.")
    yield

    # --- Shutdown ---
    logger.info("🛑 Application shutting down...")

    logger.info("✅ Application shutdown complete.")


# Create FastAPI app
app = FastAPI(
    title="Multi-Agent System API",
    description="FastAPI server with multi-agent workflow management",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)
