from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a local .env file."""

    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = ""
    MAX_FILE_SIZE_MB: int = 20
    UPLOAD_DIR: str = "uploads"
    OCR_LANGUAGE: str = "eng"
    TESSERACT_CMD: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
