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

    # Інтеграція з SIEM Wazuh (опційно). Вимкнено за замовчуванням.
    # Менеджер (порт 55000) — статус/агенти; indexer/OpenSearch (порт 9200) —
    # події wazuh-alerts-* за період. Рекомендовано read-only користувачів.
    wazuh_enabled: bool = False
    wazuh_api_url: str = ""  # напр. https://wazuh.local:55000
    wazuh_api_user: str = ""
    wazuh_api_password: str = ""
    wazuh_indexer_url: str = ""  # напр. https://wazuh.local:9200
    wazuh_indexer_user: str = ""
    wazuh_indexer_password: str = ""
    # TLS: у Wazuh типово самопідписані сертифікати. Найкраще — вказати CA-файл;
    # verify=false лишайте тільки для ізольованого внутрішнього сегмента.
    wazuh_verify_ssl: bool = True
    wazuh_ca_bundle: str = ""  # шлях до CA-сертифіката всередині контейнера


@lru_cache
def get_settings() -> Settings:
    return Settings()
