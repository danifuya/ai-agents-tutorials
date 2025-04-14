from fastapi import FastAPI
from .routes.whatsapp import router as whatsapp_router
import logfire


def create_app():
    app = FastAPI()

    # Include all your route modules
    app.include_router(whatsapp_router, prefix="/whatsapp", tags=["whatsapp"])

    return app


app = create_app()
logfire.configure()
logfire.instrument_fastapi(app)
