"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://social_studio:social_studio@localhost:5432/social_studio"
    )

    # JWT
    JWT_SECRET: str = "changeme-generate-a-real-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # External services
    GEMINI_API_KEY: str = ""
    DISCORD_WEBHOOK_URL: str = ""

    # App
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"


settings = Settings()
