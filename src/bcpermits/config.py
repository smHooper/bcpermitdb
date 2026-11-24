import json
from os import environ, PathLike
from pathlib import Path
from sqlalchemy import URL

ENVIRONMENT_MAP = {
    'git': 'dev',
    'prod': 'prod'
}
SCHEMA_MAP = {
    'dev': 'dev',
    'prod': 'public'
}
CONFIG_FILENAME_PATTERN = 'bcpermits_config_{environment}.json'


def get_environment(file_path: str | PathLike) -> str:
    """
    Get the environment name from the file path. 

    Args:
        file_path: Path to the file to infer the environment from

    Raises:
        ValueError: If the environment cannot be inferred from the file 
        path

    Returns:
        The environment name (e.g. 'dev', 'prod')
    """
    for parent in Path(file_path).parents:
        if parent.name in ENVIRONMENT_MAP:
            return ENVIRONMENT_MAP[parent.name]
    
    # exhausted parents without finding the environment
    raise ValueError(
        f'Environment could not be inferred from path: {file_path}'
    )


def find_config(
        name: str | None = None,
        config_dir: str | PathLike = 'config',
        environment: str = 'prod'
    ) -> PathLike:
    """
    Search the parents of the current file for a config file path. The config file is expected to be in a directory named `config_dir`. Each parent is searched for the child path `config_dir`/`name`.

    Args:
        name: name of the conig file. Defaults to `None`.
        config_dir: name of the config directory. Defaults to 'config'.
        environment: name of the app's environment (e.g., 'dev', 'prod'). 
            Only used to define `name` if `name` is not provided, in which case
            the default search pattern CONFIG_FILENAME_PATTERN is used. 
            Defaults to 'prod'.

    Raises:
        FileNotFoundError: If the config file cannot be found

    Returns:
        path to the config file
    """
    if not name:
        name = CONFIG_FILENAME_PATTERN.format(environment=environment)
    for parent in Path(__file__).parents:
        candidate = parent / config_dir / name
        if candidate.exists():
            return candidate
    
    # exhausted parents without finding a config file
    raise FileNotFoundError(name)


def load_config(environment: str) -> dict:
    """
    Load a config JSON file for the given environment

    Args:
        environment: name of the app's environment (e.g., 'dev', 'prod')

    Returns:
        A dictionary containing the configuration values
    """
    with open(find_config(environment=environment), encoding='utf-8') as f:
        return json.load(f)


def db_url(config: dict, access: str = 'READ'):
    """
    Get an encoded database URL from the `config` dictionary for the given `access` level. The config dictionary is expected to have a key named `DB_{access}_PARAMS` (e.g., `DB_READ_PARAMS`, `DB_WRITE_PARAMS`) that contains a dictionary of parameters to pass to `sqlalchemy.engine.URL.create()`.

    Args:
        config: configuration dictionary containing database connection 
            parameters
        access: database access level (e.g., 'READ', 'WRITE').

    Raises:
        ValueError: If DB_{access}_PARAMS is not found in the config dictionary

    Returns:
        An encoded database URL
    """

    db_params = config.get(f'DB_{access.upper()}_PARAMS')

    if not db_params:
        raise ValueError(f'Database access keyword invalid: "{access}"')
    
    return URL.create('postgresql+psycopg', **db_params)