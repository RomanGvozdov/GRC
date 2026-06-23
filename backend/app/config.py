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

    # Сповіщення. Email вимкнені, поки не задано SMTP_HOST
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "grc@localhost"
    smtp_starttls: bool = True
    slack_webhook_url: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    base_url: str = ""  # посилання в листах, напр. https://grc.company.ua
    digest_hour: int = 8  # година щоденного дайджесту (Europe/Kyiv)
    scheduler_enabled: bool = True

    # AI (ТЗ §9). Вимкнено за замовчуванням; у КСЗІ-режимі — лише локальна модель,
    # дані не покидають периметр. Провайдер — OpenAI-сумісний (Ollama/vLLM).
    ai_enabled: bool = False
    ai_provider: str = "openai_compat"
    ai_base_url: str = ""  # напр. http://ollama:11434/v1
    ai_api_key: str = ""  # для локальних — зазвичай порожній
    ai_model: str = ""  # напр. llama3.1, qwen2.5
    ai_embed_model: str = ""  # напр. bge-m3
    ai_embed_dim: int = 1024  # розмірність ембедінгів (bge-m3 = 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
