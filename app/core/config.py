import os
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # --- APP BASICS ---
    app_env: str 
    app_name: str
    environment: str

    # --- DATABASE & REDIS ---
    database_url: str
    db_port: int
    redis_url: str
    redis_port: int
    celery_broker_url: str
    celery_result_backend: str
    

    # --- SECURITY ---
    secret_key: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    jwt_algorithm: str

    stripe_secret_key: str
    stripe_webhook_secret: str

    s3_bucket: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str

    storage: str

    sendgrid_api_key: str
    email_from: str




    def __init__(self, **values):
        super().__init__(**values)

        # Check for Railway, If we are on railway, DO NOT touch the strings.
        is_railway = os.environ.get("RAILWAY_ENVIRONMENT_ID") is not None

        # Check for Docker (Local Compose)
        is_docker = os.path.exists("/.dockerenv")

        if is_railway:
            logger.info("Railway environment detected. Using Dashboard variables as provided.")
        elif is_docker:
            logger.info("Local Docker detected. Routing traffic to service names ()")

            target_db = "health_com_db"

            self.database_url = self.database_url.replace("localhost", target_db).replace("127.0.0.1", target_db)
            
            self.redis_url = self.redis_url.replace("localhost", "redis").replace("127.0.0.1", "redis")
            self.celery_broker_url = self.celery_broker_url.replace("localhost", "redis").replace("127.0.0.1", "redis")
            self.celery_result_backend = self.celery_result_backend.replace("localhost", "redis").replace("127.0.0.1", "redis")

                
        else:
            logger.info("Local Windows/OS detected. Using localhost connections.")


    model_config = SettingsConfigDict(
        # This order is important: System Environment Variables (Railway) always 
        # override the .env file (Local).
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False
    )

settings = Settings()

