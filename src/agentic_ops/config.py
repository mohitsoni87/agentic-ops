from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    langsmith_api_key: str = ""
    langsmith_tracing: bool = False
    langsmith_project: str = "agentic-ops"

    k8s_mode: str = "mock"
    poll_interval_seconds: int = 30

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentic_ops"

    slack_webhook_url: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    notify_email_to: str = ""


settings = Settings()
