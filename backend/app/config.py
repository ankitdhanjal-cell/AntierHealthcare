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
    s3_endpoint: str = "http://localhost:9010"
    s3_bucket: str = "ahs-evidence"
    s3_access_key: str = "ahsminio"
    s3_secret_key: str = "ahsminio-secret"
    app_version: str = "1.0.0"


settings = Settings()
