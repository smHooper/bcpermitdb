import json

import pytest
from sqlalchemy import URL

from bcpermits import config


# --------------------------------------------------------------------------
# get_environment
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    'path, expected',
    [
        ('/home/user/git/project/app.py', 'dev'),
        ('/srv/prod/project/pkg/app.py', 'prod'),
        ('C:/work/git/project/app.py', 'dev'),
    ],
)
def test_get_environment_known(path, expected):
    assert config.get_environment(path) == expected


def test_get_environment_accepts_pathlike(tmp_path):
    p = tmp_path / 'prod' / 'pkg' / 'file.py'
    assert config.get_environment(p) == 'prod'


def test_get_environment_nearest_parent_wins():
    # 'git' is closer to the file than 'prod'
    assert config.get_environment('/prod/git/app.py') == 'dev'
    assert config.get_environment('/git/prod/app.py') == 'prod'


def test_get_environment_unknown_raises():
    with pytest.raises(ValueError, match='could not be inferred'):
        config.get_environment('/home/user/other/app.py')


def test_get_environment_ignores_filename_itself():
    # only parents are checked, not the final path component
    with pytest.raises(ValueError):
        config.get_environment('/home/user/prod')


# --------------------------------------------------------------------------
# find_config
# --------------------------------------------------------------------------

@pytest.fixture
def fake_module_location(tmp_path, monkeypatch):
    """Pretend config.py lives at tmp_path/app/pkg/config.py."""
    module_file = tmp_path / 'app' / 'pkg' / 'config.py'
    module_file.parent.mkdir(parents=True)
    module_file.touch()
    monkeypatch.setattr(config, '__file__', str(module_file))
    return tmp_path


def test_find_config_default_name_uses_environment(fake_module_location):
    cfg_dir = fake_module_location / 'app' / 'config'
    cfg_dir.mkdir()
    expected = cfg_dir / 'bcpermits_config_dev.json'
    expected.write_text('{}')

    assert config.find_config(environment='dev') == expected


def test_find_config_default_environment_is_prod(fake_module_location):
    cfg_dir = fake_module_location / 'config'
    cfg_dir.mkdir()
    expected = cfg_dir / 'bcpermits_config_prod.json'
    expected.write_text('{}')

    # found several parents up
    assert config.find_config() == expected


def test_find_config_explicit_name_overrides_environment(fake_module_location):
    cfg_dir = fake_module_location / 'config'
    cfg_dir.mkdir()
    (cfg_dir / 'bcpermits_config_prod.json').write_text('{}')
    custom = cfg_dir / 'custom.json'
    custom.write_text('{}')

    assert config.find_config(name='custom.json', environment='prod') == custom


def test_find_config_custom_config_dir(fake_module_location):
    cfg_dir = fake_module_location / 'app' / 'settings'
    cfg_dir.mkdir()
    expected = cfg_dir / 'x.json'
    expected.write_text('{}')

    assert config.find_config(name='x.json', config_dir='settings') == expected


def test_find_config_prefers_closest_parent(fake_module_location):
    near = fake_module_location / 'app' / 'pkg' / 'config'
    far = fake_module_location / 'config'
    for d in (near, far):
        d.mkdir()
        (d / 'x.json').write_text('{}')

    assert config.find_config(name='x.json') == near / 'x.json'


def test_find_config_not_found_raises(fake_module_location):
    with pytest.raises(FileNotFoundError, match='does_not_exist.json'):
        config.find_config(name='does_not_exist.json')


# --------------------------------------------------------------------------
# load_config
# --------------------------------------------------------------------------

def test_load_config_reads_json(tmp_path, monkeypatch):
    data = {'DB_READ_PARAMS': {'host': 'localhost'}, 'unicode': 'caf\u00e9'}
    cfg_file = tmp_path / 'cfg.json'
    cfg_file.write_text(json.dumps(data), encoding='utf-8')

    seen = {}

    def fake_find_config(**kwargs):
        seen.update(kwargs)
        return cfg_file

    monkeypatch.setattr(config, 'find_config', fake_find_config)

    assert config.load_config('dev') == data
    assert seen == {'environment': 'dev'}


def test_load_config_invalid_json_raises(tmp_path, monkeypatch):
    cfg_file = tmp_path / 'bad.json'
    cfg_file.write_text('{not json')
    monkeypatch.setattr(config, 'find_config', lambda **kw: cfg_file)

    with pytest.raises(json.JSONDecodeError):
        config.load_config('prod')


def test_load_config_propagates_missing_file(monkeypatch):
    def raise_missing(**kwargs):
        raise FileNotFoundError('nope')

    monkeypatch.setattr(config, 'find_config', raise_missing)

    with pytest.raises(FileNotFoundError):
        config.load_config('prod')


# --------------------------------------------------------------------------
# db_url
# --------------------------------------------------------------------------

@pytest.fixture
def db_config():
    return {
        'DB_READ_PARAMS': {
            'host': 'db.example.com',
            'port': 5432,
            'username': 'reader',
            'password': 'r-secret',
            'database': 'bcpermits',
        },
        'DB_WRITE_PARAMS': {
            'host': 'db.example.com',
            'username': 'writer',
            'password': 'w-secret',
            'database': 'bcpermits',
        },
    }


def test_db_url_default_is_read(db_config):
    url = config.db_url(db_config)

    assert isinstance(url, URL)
    assert url.drivername == 'postgresql+psycopg'
    assert url.username == 'reader'
    assert url.host == 'db.example.com'
    assert url.port == 5432
    assert url.database == 'bcpermits'


def test_db_url_write_access(db_config):
    url = config.db_url(db_config, access='WRITE')

    assert url.username == 'writer'
    assert url.password == 'w-secret'


@pytest.mark.parametrize('access', ['read', 'Read', 'READ'])
def test_db_url_access_case_insensitive(db_config, access):
    assert config.db_url(db_config, access=access).username == 'reader'


def test_db_url_special_characters_are_encoded():
    cfg = {'DB_READ_PARAMS': {
        'host': 'h', 'username': 'u', 'password': 'p@ss/w:rd', 'database': 'd',
    }}
    rendered = config.db_url(cfg).render_as_string(hide_password=False)

    assert 'p@ss/w:rd' not in rendered
    assert 'p%40ss%2Fw%3Ard' in rendered


@pytest.mark.parametrize('access', ['admin', '', 'readonly'])
def test_db_url_invalid_access_raises(db_config, access):
    with pytest.raises(ValueError, match='access keyword invalid'):
        config.db_url(db_config, access=access)


def test_db_url_empty_params_raises():
    with pytest.raises(ValueError):
        config.db_url({'DB_READ_PARAMS': {}})


def test_db_url_empty_config_raises():
    with pytest.raises(ValueError):
        config.db_url({})