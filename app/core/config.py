from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://revision_user:revision_pass@localhost:5433/revision_vehicular"
    test_database_url: str = "postgresql+asyncpg://revision_user:revision_pass@localhost:5433/revision_vehicular_test"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60


settings = Settings()
