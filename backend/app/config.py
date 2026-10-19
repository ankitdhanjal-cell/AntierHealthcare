from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg2://ahs:ahs_local_pw@localhost:5442/ahs"
    redis_url: str = "redis://localhost:6389/0"
    jwt_secret: str = "change-me"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "Antier Healthcare Suite <no-reply@healthcare-suite.antiers.work>"
    public_web_url: str = "http://localhost:3010"
    app_version: str = "1.0.0"
    evidence_dir: str = str(Path(__file__).resolve().parent.parent / "data" / "evidence")  # uploaded and sample evidence files


settings = Settings()
