from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Única base de datos: la de GIM. La API usa el esquema gimprod (de GIM) y
    # su propio esquema matriculacion.
    gim_database_url: str
    test_gim_database_url: str = "postgresql+asyncpg://gim_test:gim_test@localhost:5434/gim_test"
    # resident.id de la persona de sistema creada con scripts/gim/0001_crear_emisor_matriculacion.sql
    gim_emisor_resident_id: int
    gim_entry_id_revision: int = 813
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60


settings = Settings()
