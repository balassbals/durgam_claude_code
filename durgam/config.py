from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://durgam:durgam@localhost:5432/durgam",
        alias="DATABASE_URL",
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg://durgam:durgam@localhost:5432/durgam",
        alias="DATABASE_URL_SYNC",
    )
    test_database_url: str = Field(
        default="postgresql+psycopg://durgam:durgam@localhost:5432/durgam_test",
        alias="TEST_DATABASE_URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="durgam", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    smtp_host: str = Field(default="localhost", alias="SMTP_HOST")
    smtp_port: int = Field(default=1025, alias="SMTP_PORT")
    smtp_from: str = Field(default="noreply@sssihl.edu.in", alias="SMTP_FROM")

    app_base_url: str = Field(default="http://localhost:3000", alias="APP_BASE_URL")

    # Never ship the dev default to production — override via SECRET_KEY env var.
    secret_key: str = Field(default="dev-secret-key-change-in-production", alias="SECRET_KEY")
    debug: bool = Field(default=False, alias="DEBUG")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Auth rate-limiting (OQ-2 confirmed thresholds).
    auth_user_failure_threshold: int = Field(default=5, alias="AUTH_USER_FAILURE_THRESHOLD")
    auth_user_lockout_minutes: int = Field(default=15, alias="AUTH_USER_LOCKOUT_MINUTES")
    auth_ip_throttle_limit: int = Field(default=20, alias="AUTH_IP_THROTTLE_LIMIT")
    auth_ip_throttle_window_minutes: int = Field(
        default=15, alias="AUTH_IP_THROTTLE_WINDOW_MINUTES"
    )


settings = Settings()
