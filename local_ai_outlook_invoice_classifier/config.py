from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Application configuration using Pydantic BaseSettings"""

    # Microsoft Graph Configuration
    client_id: str
    client_secret: str
    tenant_id: str
    user_id: str

    # Webhook Configuration
    webhook_url: str

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True

    # Email Processing Configuration
    category_name: str = "Invoice Saved"

    # AI Configuration
    openai_api_key: str = "dummy"
    local_api_url: str = "http://localhost:12434/engines/v1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


# Global settings instance - loaded once
settings = AppSettings()
