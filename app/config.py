from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://eduhelper:eduhelper@db/eduhelper"
    secret_key: str
    admin_password_hash: str
    access_minutes: int = 10
    refresh_days: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
