import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    APP_NAME: str = os.getenv("APP_NAME", "notifyservice")
    API_V1_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", ["*"])

    # JWT
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret")
    JWT_USER_ID_CLAIM: str = os.getenv("JWT_USER_ID_CLAIM", "sub")

    # SSE tuning
    SSE_HEARTBEAT_SECONDS: int = int(os.getenv("SSE_HEARTBEAT_SECONDS", "20"))
    SSE_RETRY_MILLISECONDS: int = int(os.getenv("SSE_RETRY_MILLISECONDS", "1500"))

    # Internal trust
    INTERNAL_TRUSTED_CIDRS_RAW: str = os.getenv("INTERNAL_TRUSTED_CIDRS", "")
    INTERNAL_TRUSTED_CIDRS: List[str] = []

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def __init__(self, **data):
        super().__init__(**data)
        if self.INTERNAL_TRUSTED_CIDRS_RAW.strip():
            self.INTERNAL_TRUSTED_CIDRS = [
                c.strip() for c in self.INTERNAL_TRUSTED_CIDRS_RAW.split(",") if c.strip()
            ]


settings = Settings()
