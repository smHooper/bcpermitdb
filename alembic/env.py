from logging.config import fileConfig

from alembic import context
from sqlalchemy.pool import NullPool

import bcpermits.config as app_config
from bcpermits.config import get_environment, load_config, SCHEMA_MAP
from bcpermits.db import Base, get_engine
import bcpermits.models  # noqa: F401  (registers all models on Base.metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# --- Work out the target --------------------------------------------------
ENVIRONMENT = get_environment(__file__)          # from where env.py lives
PKG_ENVIRONMENT = get_environment(app_config.__file__)  # from where the package was imported

# Guards against a venv whose editable install points at the *other* tree
if ENVIRONMENT != PKG_ENVIRONMENT:
    raise RuntimeError(
        f'env.py is in "{ENVIRONMENT}" but bcpermits was imported from '
        f'"{PKG_ENVIRONMENT}". Check which tree this venv is installed from.'
    )

cfg = load_config(ENVIRONMENT)
SCHEMA = cfg.get('DB_SCHEMA') or SCHEMA_MAP[ENVIRONMENT]

print(
    f'Alembic target: env={ENVIRONMENT}, schema={SCHEMA}, '
    f'host={cfg["DB_WRITE_PARAMS"]["host"]}, db={cfg["DB_WRITE_PARAMS"]["database"]}'
)

# --- Prod confirmation ------------------------------------------------------
x = context.get_x_argument(as_dictionary=True)
cmd = getattr(getattr(config, 'cmd_opts', None), 'cmd', None)
cmd_name = cmd[0].__name__ if cmd else None

if SCHEMA == 'public' and cmd_name in ('upgrade', 'downgrade', 'stamp'):
    if x.get('confirm') != 'prod':
        raise RuntimeError(
            'Refusing to modify prod. Re-run with: alembic -x confirm=prod '
            f'{cmd_name} ...'
        )


def run_migrations_offline() -> None:
    raise RuntimeError(
        'Offline mode is not supported (the schema is set via search_path '
        'on the connection).'
    )


def run_migrations_online() -> None:
    engine = get_engine(
        cfg,
        access='write',          # or 'admin' if your write role lacks DDL rights
        schema=SCHEMA,
        engine_kwargs={'poolclass': NullPool},
    )
    
    with engine.connect() as connection:

        connection.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"')
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()