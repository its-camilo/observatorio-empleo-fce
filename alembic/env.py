"""Entorno de Alembic: usa DATABASE_URL y los modelos de observatorio.db.modelos."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from observatorio.config import ajustes
from observatorio.db.modelos import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", ajustes().database_url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    conectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with conectable.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
