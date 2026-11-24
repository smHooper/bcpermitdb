from datetime import date, datetime

import pytest
from sqlalchemy import BOOLEAN, INTEGER, VARCHAR, create_engine, inspect, select
from sqlalchemy.orm import Session

from bcpermits import models
from bcpermits.db import CodeMixin, MetadataMixin

TABLES = models.Base.metadata.tables

CODE_MODELS = {
    'user_role_codes': models.UserRoleCode,
    'state_codes': models.StateCode,
    'country_codes': models.CountryCode,
    'brfc_status_codes': models.BRFCStatusCode,
}

METADATA_MODELS = [
    models.BackcountryUser,
    models.Permit,
    models.BRFC,
    models.BRFCCheckout,
    models.PartyMember,
    models.Itinerary,
    models.BackcountryOrientation,
]


# --------------------------------------------------------------------------
# Table names / registration
# --------------------------------------------------------------------------

def test_all_expected_tables_registered():
    expected = {
        'user_role_codes', 'state_codes', 'country_codes', 'brfc_status_codes',
        'users', 'backcountry_units', 'backcountry_users', 'permits', 'brfcs',
        'brfc_checkouts', 'party_members', 'itineraries',
        'backcountry_orientations',
    }
    assert expected <= set(TABLES)


@pytest.mark.parametrize('table_name, model', CODE_MODELS.items())
def test_code_tables_use_code_mixin(table_name, model):
    assert model.__tablename__ == table_name
    assert issubclass(model, CodeMixin)
    assert {'id', 'code', 'name', 'sort_order'} <= set(model.__table__.c.keys())
    assert model.__table__.c.code.unique
    assert not model.__table__.c.code.nullable


@pytest.mark.parametrize('model', METADATA_MODELS)
def test_metadata_mixin_columns_present(model):
    assert issubclass(model, MetadataMixin)
    cols = set(model.__table__.c.keys())
    assert {'entered_by', 'entry_time', 'modified_by', 'modified_time'} <= cols


def test_user_has_no_metadata_columns():
    assert 'entered_by' not in models.User.__table__.c


# --------------------------------------------------------------------------
# Primary keys
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    'model, pk',
    [
        (models.User, 'id'),
        (models.BackcountryUnit, 'unit_number'),
        (models.BackcountryUser, 'id'),
        (models.Permit, 'permit_number'),
        (models.BRFC, 'id'),
        (models.BRFCCheckout, 'id'),
        (models.PartyMember, 'id'),
        (models.Itinerary, 'id'),
        (models.BackcountryOrientation, 'id'),
    ],
)
def test_primary_keys(model, pk):
    assert [c.name for c in model.__table__.primary_key.columns] == [pk]


# --------------------------------------------------------------------------
# Foreign keys
# --------------------------------------------------------------------------

FOREIGN_KEYS = [
    ('users', 'role', 'user_role_codes.code'),
    ('backcountry_users', 'state_province_code', 'state_codes.code'),
    ('backcountry_users', 'country_code', 'country_codes.code'),
    ('permits', 'license_plate_state_code', 'state_codes.code'),
    ('permits', 'emergency_contact_state_code', 'state_codes.code'),
    ('permits', 'emergency_contact_country_code', 'country_codes.code'),
    ('brfcs', 'brfc_status_code', 'brfc_status_codes.code'),
    ('brfc_checkouts', 'brfc_id', 'brfcs.id'),
    ('brfc_checkouts', 'permit_number', 'permits.permit_number'),
    ('party_members', 'permit_number', 'permits.permit_number'),
    ('party_members', 'backcountry_user_id', 'backcountry_users.id'),
    ('itineraries', 'party_member_id', 'party_members.id'),
    ('itineraries', 'backcountry_unit_number', 'backcountry_units.unit_number'),
    ('backcountry_orientations', 'backcountry_user_id', 'backcountry_users.id'),
]


@pytest.mark.parametrize('table, column, target', FOREIGN_KEYS)
def test_foreign_key_targets(table, column, target):
    fks = TABLES[table].c[column].foreign_keys
    assert {fk.target_fullname for fk in fks} == {target}


def test_foreign_keys_resolve():
    # accessing .column forces SQLAlchemy to resolve each FK target
    for table in TABLES.values():
        for fk in table.foreign_keys:
            assert fk.column is not None


# --------------------------------------------------------------------------
# Nullability
# --------------------------------------------------------------------------

NOT_NULL = [
    ('brfc_checkouts', 'brfc_id'),
    ('party_members', 'permit_number'),
    ('party_members', 'backcountry_user_id'),
    ('itineraries', 'party_member_id'),
    ('itineraries', 'backcountry_unit_number'),
    ('itineraries', 'start_date'),
    ('itineraries', 'end_date'),
    ('backcountry_orientations', 'backcountry_user_id'),
    ('backcountry_orientations', 'video_date'),
    ('backcountry_orientations', 'safety_talk_date'),
    ('backcountry_orientations', 'safety_talk_ranger'),
]


@pytest.mark.parametrize('table, column', NOT_NULL)
def test_required_columns_not_nullable(table, column):
    assert TABLES[table].c[column].nullable is False


@pytest.mark.parametrize(
    'table, column',
    [
        ('permits', 'party_size'),
        ('permits', 'license_plate'),
        ('brfc_checkouts', 'checkin_time'),
        ('brfcs', 'date_decommissioned'),
        ('backcountry_users', 'address_2'),
    ],
)
def test_optional_columns_nullable(table, column):
    assert TABLES[table].c[column].nullable is True


# --------------------------------------------------------------------------
# Types and lengths
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    'table, column, length',
    [
        ('users', 'ad_username', 50),
        ('backcountry_units', 'unit_name', 100),
        ('backcountry_users', 'email', 100),
        ('backcountry_users', 'phone_number', 20),
        ('permits', 'license_plate', 20),
        ('permits', 'bike_descriptions', 255),
        ('permits', 'packraft_descriptions', 255),
        ('permits', 'emergency_contact_phone', 20),
        ('brfcs', 'brfc_number', 20),
        ('backcountry_orientations', 'safety_talk_ranger', 50),
    ],
)
def test_varchar_lengths(table, column, length):
    col = TABLES[table].c[column]
    assert isinstance(col.type, VARCHAR)
    assert col.type.length == length


@pytest.mark.parametrize(
    'column',
    ['is_admin', 'is_bikepacking', 'is_packrafting', 'is_mountaineering'],
)
def test_permit_boolean_flags_default_false(column):
    col = TABLES['permits'].c[column]
    assert isinstance(col.type, BOOLEAN)
    assert col.default.arg is False


def test_brfc_checkout_is_longterm_default_false():
    col = TABLES['brfc_checkouts'].c['is_longterm']
    assert isinstance(col.type, BOOLEAN)
    assert col.default.arg is False


def test_integer_columns():
    assert isinstance(TABLES['permits'].c['party_size'].type, INTEGER)
    assert isinstance(TABLES['backcountry_units'].c['limit'].type, INTEGER)


# --------------------------------------------------------------------------
# Behavioral tests against an in-memory SQLite database
# --------------------------------------------------------------------------

@pytest.fixture
def session():
    engine = create_engine('sqlite://')
    models.Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


def test_create_all_creates_every_table():
    engine = create_engine('sqlite://')
    models.Base.metadata.create_all(engine)

    assert set(TABLES) <= set(inspect(engine).get_table_names())


def test_permit_defaults_applied_on_insert(session):
    session.add(models.Permit(permit_number=1))
    session.commit()

    permit = session.get(models.Permit, 1)
    assert permit.is_admin is False
    assert permit.is_bikepacking is False
    assert permit.is_packrafting is False
    assert permit.is_mountaineering is False


def test_backcountry_unit_limit_column_roundtrips(session):
    # "limit" is an SQL reserved word; make sure it is quoted correctly
    session.add(models.BackcountryUnit(unit_number=5, unit_name='Unit 5', limit=12))
    session.commit()

    unit = session.execute(
        select(models.BackcountryUnit).where(models.BackcountryUnit.unit_number == 5)
    ).scalar_one()
    assert unit.limit == 12


def test_full_permit_graph_roundtrip(session):
    session.add_all([
        models.BackcountryUnit(unit_number=10, unit_name='Unit 10', limit=6),
        models.BackcountryUser(id=1, first_name='Ada', last_name='Lovelace'),
        models.Permit(permit_number=100, party_size=1, entered_by='ranger'),
    ])
    session.flush()
    session.add(models.PartyMember(id=1, permit_number=100, backcountry_user_id=1))
    session.flush()
    session.add(models.Itinerary(
        id=1,
        party_member_id=1,
        backcountry_unit_number=10,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
    ))
    session.add(models.BackcountryOrientation(
        id=1,
        backcountry_user_id=1,
        video_date=date(2026, 6, 1),
        safety_talk_date=date(2026, 6, 2),
        safety_talk_ranger='Ranger Smith',
    ))
    session.commit()

    itin = session.get(models.Itinerary, 1)
    assert itin.start_date == date(2026, 7, 1)
    assert itin.end_date == date(2026, 7, 5)
    assert session.get(models.Permit, 100).entered_by == 'ranger'


def test_brfc_checkout_roundtrip(session):
    session.add_all([
        models.BRFC(id=1, brfc_number='BRFC-001', date_added=date(2026, 5, 1)),
        models.Permit(permit_number=7),
    ])
    session.flush()
    session.add(models.BRFCCheckout(
        id=1, brfc_id=1, permit_number=7,
        checkout_time=datetime(2026, 7, 1, 9, 30),
    ))
    session.commit()

    checkout = session.get(models.BRFCCheckout, 1)
    assert checkout.is_longterm is False
    assert checkout.checkin_time is None
    assert checkout.checkout_time == datetime(2026, 7, 1, 9, 30)


@pytest.mark.parametrize(
    'obj_factory',
    [
        lambda: models.PartyMember(id=1, permit_number=None, backcountry_user_id=1),
        lambda: models.BRFCCheckout(id=1, brfc_id=None),
        lambda: models.Itinerary(
            id=1, party_member_id=1, backcountry_unit_number=1,
            start_date=None, end_date=date(2026, 1, 1),
        ),
        lambda: models.BackcountryOrientation(
            id=1, backcountry_user_id=1, video_date=date(2026, 1, 1),
            safety_talk_date=date(2026, 1, 1), safety_talk_ranger=None,
        ),
    ],
)
def test_not_null_constraints_enforced(session, obj_factory):
    from sqlalchemy.exc import IntegrityError

    session.add(obj_factory())
    with pytest.raises(IntegrityError):
        session.commit()


def test_code_table_code_must_be_unique(session):
    from sqlalchemy.exc import IntegrityError

    session.add_all([
        models.StateCode(id=1, code=2, name='Alaska'),
        models.StateCode(id=2, code=2, name='Duplicate'),
    ])
    with pytest.raises(IntegrityError):
        session.commit()


# --------------------------------------------------------------------------
# Known issue (documents current behavior; remove xfail once fixed)
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    'table, column',
    [('brfcs', 'date_added'), ('brfc_checkouts', 'checkout_time')],
)
def test_defaults_are_callables(table, column):
    assert callable(TABLES[table].c[column].default.arg)