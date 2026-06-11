from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "GRC"
    secret_key: str = "change-me-in-production"
    database_url: str = "postgresql+psycopg://grc:grc@localhost:5432/grc"

    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    # Перший адміністратор: створюється при старті, якщо в БД немає користувачів
    admin_email: str = "admin@example.com"
    admin_password: str = ""
    admin_full_name: str = "Адміністратор"

    max_failed_logins: int = 5
    lockout_minutes: int = 15
    max_upload_mb: int = 25
    upload_dir: str = "uploads"

    # Поріг рівня ризику, вище якого прийняття вимагає затвердження (10 = "високий")
    risk_acceptance_threshold: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()
