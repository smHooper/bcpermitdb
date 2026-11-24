from datetime import datetime
from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Column, ForeignKey, INTEGER, VARCHAR, BOOLEAN, NUMERIC
from sqlalchemy.dialects.postgresql import TEXT, DATE, TIMESTAMP
from sqlalchemy.ext.declarative import as_declarative
from sqlalchemy.orm import relationship, declared_attr, backref
from .db import (
    Base,
    CodeMixin,
    MetadataMixin
)


class UserRoleCode(Base, CodeMixin):
    __tablename__ = 'user_role_codes'

class StateCode(Base, CodeMixin):
    __tablename__ = 'state_codes'

class CountryCode(Base, CodeMixin):
    __tablename__ = 'country_codes'

class BRFCStatusCode(Base, CodeMixin):
    __tablename__ = 'brfc_status_codes'

class User(Base):
    __tablename__ = 'users'

    id = Column(INTEGER, primary_key=True)
    ad_username = Column(VARCHAR(50))
    role = Column(INTEGER, ForeignKey(UserRoleCode.code))

class BackcountryUnit(Base):
    __tablename__ = 'backcountry_units'

    unit_number =       Column(INTEGER, primary_key=True)
    unit_name =         Column(VARCHAR(100))
    limit =             Column(INTEGER)

class BackcountryUser(Base, MetadataMixin):
    __tablename__ = 'backcountry_users'

    id =                Column(INTEGER, primary_key=True)
    first_name =        Column(VARCHAR(50))
    last_name =         Column(VARCHAR(50))
    email =             Column(VARCHAR(100))
    phone_number =      Column(VARCHAR(20))
    address_1 =         Column(VARCHAR(100))
    address_2 =         Column(VARCHAR(100))
    city =              Column(VARCHAR(50))
    state_province_code =\
                        Column(INTEGER, ForeignKey(StateCode.code))
    country_code =      Column(INTEGER, ForeignKey(CountryCode.code))

class Permit(Base, MetadataMixin):
    __tablename__ = 'permits'

    permit_number =     Column(INTEGER, primary_key=True)
    is_admin =          Column(BOOLEAN, default=False)
    license_plate =     Column(VARCHAR(20))
    license_plate_state_code =\
                        Column(INTEGER, ForeignKey(StateCode.code))
    vehicle_color =     Column(VARCHAR(50))
    vehicle_make =      Column(VARCHAR(50))
    vehicle_model =     Column(VARCHAR(50))
    parking_location =  Column(VARCHAR(100))
    party_size =        Column(INTEGER)
    tent_colors =       Column(VARCHAR(100))
    is_bikepacking =    Column(BOOLEAN, default=False)
    bike_descriptions = Column(VARCHAR(255))
    is_packrafting =    Column(BOOLEAN, default=False)
    packraft_descriptions =\
                        Column(VARCHAR(255))
    is_mountaineering = Column(BOOLEAN, default=False)
    emergency_contact_name =\
                        Column(VARCHAR(100))
    emergency_contact_phone =\
                        Column(VARCHAR(20))
    emergency_contact_city =\
                        Column(VARCHAR(50))
    emergency_contact_state_code =\
                        Column(INTEGER, ForeignKey(StateCode.code))
    emergency_contact_country_code =\
                        Column(INTEGER, ForeignKey(CountryCode.code))
    comments =          Column(TEXT)  

class BRFC(Base, MetadataMixin):
    __tablename__ = 'brfcs'

    id =                Column(INTEGER, primary_key=True)
    brfc_number =       Column(VARCHAR(20))
    brfc_status_code =  Column(INTEGER, ForeignKey(BRFCStatusCode.code))
    date_added =        Column(DATE, default=datetime.now())
    date_decommissioned =\
                        Column(DATE)

class BRFCCheckout(Base, MetadataMixin):
    __tablename__ = 'brfc_checkouts'

    id =                Column(INTEGER, primary_key=True)
    brfc_id =           Column(INTEGER, ForeignKey(BRFC.id), nullable=False)
    permit_number =     Column(INTEGER, ForeignKey(Permit.permit_number))
    is_longterm =       Column(BOOLEAN, default=False)
    checkout_time =     Column(TIMESTAMP, default=datetime.now())
    checkin_time =      Column(TIMESTAMP)

class PartyMember(Base, MetadataMixin):
    __tablename__ = 'party_members'

    id =                Column(INTEGER, primary_key=True)
    permit_number =     Column(
                            INTEGER, 
                            ForeignKey(Permit.permit_number), 
                            nullable=False
                        )
    backcountry_user_id = Column(
                            INTEGER, 
                            ForeignKey(BackcountryUser.id), 
                            nullable=False
                        )

class Itinerary(Base, MetadataMixin):
    __tablename__ = 'itineraries'

    id =                Column(INTEGER, primary_key=True)
    party_member_id =   Column(
                            INTEGER, 
                            ForeignKey(PartyMember.id), 
                            nullable=False
                        )
    backcountry_unit_number = Column(
                            INTEGER, 
                            ForeignKey(BackcountryUnit.unit_number), 
                            nullable=False
                        )
    start_date =        Column(DATE, nullable=False)
    end_date =          Column(DATE, nullable=False)


class BackcountryOrientation(Base, MetadataMixin):
    __tablename__ = 'backcountry_orientations'

    id =                Column(INTEGER, primary_key=True)
    backcountry_user_id = Column(
                            INTEGER, 
                            ForeignKey(BackcountryUser.id), 
                            nullable=False
                        )
    video_date =        Column(DATE, nullable=False)
    safety_talk_date =  Column(DATE, nullable=False)
    safety_talk_ranger =\
                        Column(VARCHAR(50), nullable=False)