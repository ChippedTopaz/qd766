from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from qd766.backend.config import Settings
from qd766.backend.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Alembic stores main options in ConfigParser, where a literal percent sign
# must be doubled. SQLAlchemy URLs percent-encode reserved password characters.
config.set_main_option(
    "sqlalchemy.url",
    Settings.from_env().database_url.replace("%", "%%"),
)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
