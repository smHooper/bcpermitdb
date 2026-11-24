from unittest.mock import MagicMock

import pytest
from sqlalchemy import INTEGER, TIMESTAMP, VARCHAR
from sqlalchemy.orm import DeclarativeBase

from bcpermits import db


# --------------------------------------------------------------------------
# Base / naming convention
# --------------------------------------------------------------------------

def test_base_is_declarative_base():
    assert issubclass(db.Base, DeclarativeBase)


def test_base_naming_convention():
    assert db.Base.metadata.naming_convention == {
        'ix': 'ix_%(column_0_label)s',
        'uq': 'uq_%(table_name)s_%(column_0_name)s',
        'ck': 'ck_%(table_name)s_%(constraint_name)s',
        'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
        'pk': 'pk_%(table_name)s',
    }


def test_naming_convention_applied_to_constraints():
    from sqlalchemy import Column, ForeignKey, ForeignKeyConstraint

    class Parent(db.Base):
        __tablename__ = 'naming_parent'
        id = Column(INTEGER, primary_key=True)
        code = Column(INTEGER, unique=True)

    class Child(db.Base):
        __tablename__ = 'naming_child'
        id = Column(INTEGER, primary_key=True)
        parent_code = Column(INTEGER, ForeignKey(Parent.code))

    try:
        assert Parent.__table__.primary_key.name == 'pk_naming_parent'
        fk = next(
            c for c in Child.__table__.constraints
            if isinstance(c, ForeignKeyConstraint)
        )
        assert fk.name == 'fk_naming_child_parent_code_naming_parent'
    finally:
        db.Base.metadata.remove(Child.__table__)
        db.Base.metadata.remove(Parent.__table__)


# --------------------------------------------------------------------------
# Mixins
# --------------------------------------------------------------------------

def test_code_mixin_columns():
    mixin = db.CodeMixin
    assert mixin.id.primary_key
    assert isinstance(mixin.id.type, INTEGER)

    assert isinstance(mixin.code.type, INTEGER)
    assert mixin.code.nullable is False
    assert mixin.code.unique is True

    assert isinstance(mixin.name.type, VARCHAR)
    assert mixin.name.type.length == 50
    assert isinstance(mixin.sort_order.type, INTEGER)


def test_metadata_mixin_columns():
    mixin = db.MetadataMixin
    for name in ('entered_by', 'modified_by'):
        col = getattr(mixin, name)
        assert isinstance(col.type, VARCHAR)
        assert col.type.length == 50
    for name in ('entry_time', 'modified_time'):
        assert isinstance(getattr(mixin, name).type, TIMESTAMP)


# --------------------------------------------------------------------------
# get_engine
# --------------------------------------------------------------------------

@pytest.fixture
def mocks(monkeypatch):
    create_engine = MagicMock(name='create_engine')
    db_url = MagicMock(name='db_url', return_value='sentinel-url')
    monkeypatch.setattr(db, 'create_engine', create_engine)
    monkeypatch.setattr(db, 'db_url', db_url)
    return create_engine, db_url


def test_get_engine_returns_created_engine(mocks):
    create_engine, _ = mocks

    assert db.get_engine({'cfg': 1}) is create_engine.return_value


def test_get_engine_defaults(mocks):
    create_engine, db_url = mocks
    cfg = {'cfg': 1}

    db.get_engine(cfg)

    db_url.assert_called_once_with(cfg, access='READ')
    create_engine.assert_called_once_with(
        'sentinel-url',
        pool_pre_ping=True,
        connect_args={'options': '-csearch_path=public'},
    )


def test_get_engine_access_is_uppercased(mocks):
    _, db_url = mocks

    db.get_engine({}, access='write')

    db_url.assert_called_once_with({}, access='WRITE')


def test_get_engine_custom_schema(mocks):
    create_engine, _ = mocks

    db.get_engine({}, schema='dev')

    kwargs = create_engine.call_args.kwargs
    assert kwargs['connect_args'] == {'options': '-csearch_path=dev'}


def test_get_engine_passes_engine_kwargs(mocks):
    create_engine, _ = mocks

    db.get_engine({}, engine_kwargs={'echo': True, 'pool_size': 3})

    kwargs = create_engine.call_args.kwargs
    assert kwargs['echo'] is True
    assert kwargs['pool_size'] == 3
    assert kwargs['pool_pre_ping'] is True


def test_get_engine_engine_kwargs_override_pool_pre_ping(mocks):
    # caller-supplied engine_kwargs take precedence over get_engine's defaults
    create_engine, _ = mocks

    db.get_engine({}, engine_kwargs={'pool_pre_ping': False})

    assert create_engine.call_args.kwargs['pool_pre_ping'] is False


def test_get_engine_engine_kwargs_connect_args_replaces_default(mocks):
    # connect_args is replaced wholesale, not merged, so the search_path
    #   option is lost unless the caller includes it
    create_engine, _ = mocks

    db.get_engine({}, schema='dev', engine_kwargs={'connect_args': {'connect_timeout': 5}})

    assert create_engine.call_args.kwargs['connect_args'] == {'connect_timeout': 5}

def test_get_engine_unrelated_engine_kwargs_keep_defaults(mocks):
    create_engine, _ = mocks

    db.get_engine({}, schema='dev', engine_kwargs={'echo': True})

    kwargs = create_engine.call_args.kwargs
    assert kwargs['echo'] is True
    assert kwargs['pool_pre_ping'] is True
    assert kwargs['connect_args'] == {'options': '-csearch_path=dev'}

def test_get_engine_engine_kwargs_none(mocks):
    create_engine, _ = mocks

    db.get_engine({}, engine_kwargs=None)

    kwargs = create_engine.call_args.kwargs
    assert kwargs['pool_pre_ping'] is True
    assert kwargs['connect_args'] == {'options': '-csearch_path=public'}

def test_get_engine_invalid_access_propagates_error(monkeypatch):
    # use the real db_url, but keep create_engine from touching a driver
    monkeypatch.setattr(db, 'create_engine', MagicMock())

    with pytest.raises(ValueError):
        db.get_engine({}, access='bogus')