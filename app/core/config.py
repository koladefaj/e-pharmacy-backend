import os
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, SecretStr


logger = logging.getLogger(__name__)

class Settings(BaseSettings):

    
    # APP BASICS 
    app_env: str 
    app_name: str
    environment: str

    # DATABASE & REDIS 
    database_url: str
    db_port: int
    redis_url: str
    redis_port: int

    @field_validator("database_url", "redis_url", mode="after")
    @classmethod
    def adjust_urls_for_docker(cls, v: str) -> str:
        if os.environ.get("RAILWAY_ENVIRONMENT_ID"):
            return v
            
        # If in Local Docker, swap localhost for service names
        if os.path.exists("/.dockerenv"):
            # Replace localhost/127.0.0.1 with service names defined in docker-compose.yml
            v = v.replace("localhost", "e_pharmacy_db").replace("127.0.0.1", "e_pharmacy_db")
            if "redis" in v or "6379" in v:
                return v.replace("e_pharmacy_db", "redis") 
        return v
    

    # SECURITY
    secret_key: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    jwt_algorithm: str

    # STRIPE
    stripe_secret_key: str
    stripe_webhook_secret: str

    # STORAGE
    s3_bucket: str
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str
    s3_region: str

    storage: str

    # EMAIL PROVIDER
    sendgrid_api_key: SecretStr
    email_from: str


    model_config = SettingsConfigDict(
        # This order is important: System Environment Variables (Railway) always 
        # override the .env file (Local).
        env_file=(".env"),
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False
    )

settings = Settings()
