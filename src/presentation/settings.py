from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/payments"
    bank_api_base_url: str = "http://bank-api:8000"
    bank_api_mode: str = "fake"
    logs_dir: str = "/tmp/logs"  # nosec B108


settings = Settings()
