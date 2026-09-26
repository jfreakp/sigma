import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
from app.models.base import Base
import app.models.client  # noqa: F401
import app.models.orden_titulo  # noqa: F401
import app.models.tramo_rodaje  # noqa: F401

SCHEMA = "matriculacion"

config = context.config
# ConfigParser interpreta "%": se escapa por si la contraseña lo contiene.
config.set_main_option("sqlalchemy.url", settings.gim_database_url.replace("%", "%%"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    # Nunca mirar ni generar cambios fuera del esquema de la API (gimprod es de GIM).
    if type_ == "schema":
        return name == SCHEMA
    return True


def _configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_name=include_name,
        **kwargs,
    )


def run_migrations_offline() -> None:
    _configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    # La tabla alembic_version vive en matriculacion: el esquema debe existir antes.
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
    connection.commit()
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
