from sqlalchemy import (
    create_engine,
    Column,
    INTEGER,
    MetaData,
    TIMESTAMP,
    VARCHAR
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase

from .config import db_url

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })

class CodeMixin:
    id = Column(INTEGER, primary_key=True)
    code = Column(INTEGER, nullable=False, unique=True)
    name = Column(VARCHAR(50))
    sort_order = Column(INTEGER)

class MetadataMixin:
    entered_by = Column(VARCHAR(50))
    entry_time = Column(TIMESTAMP)
    modified_by = Column(VARCHAR(50))
    modified_time = Column(TIMESTAMP)


def get_engine(
        config, 
        access: str = 'read', 
        schema: str = 'public',
        engine_kwargs: dict = None) -> Engine:
    """
    Helper method to get a sqlalchemy engine with defaults

    Args:
        config: Configuration dictionary containing database connection 
            parameters
        access : Database access level
        schema : Database schema to use

    Returns:
        A sqlalchemy Engine
    """
    kwargs = {
        'pool_pre_ping': True,
        'connect_args': {'options': f'-csearch_path={schema}'},
        **(engine_kwargs or {})
    }
    return (
        create_engine(
            db_url(config, access=access.upper()), 
            **kwargs   
        )
    )