# -*- encoding: utf-8 -*-

import datetime

from sqlalchemy import (
    Column,
    Integer, String, DateTime
)
from sqlalchemy.orm import relationship
from sqlalchemy.schema import ForeignKey

from app.models.mixins import (
    AppDeclBase, BaseModel
)
from utils.crypto_utils import encrypt, decrypt
from app_utils.db_utils import IS_ORACLE_DB
from oracle_models import JSONB

__all__ = (
    'ActiveDeviceClient',
    'ActiveDeviceWiFi',
    'ChangeWifiPasswordLog',
)


class ActiveDeviceClient(AppDeclBase, BaseModel):
    __tablename__ = "active_device_clients"

    NO_ID_SEQUENCE = True
    id = Column(Integer, primary_key=True, autoincrement=(not IS_ORACLE_DB))
    device_id = Column(
        Integer, primary_key=IS_ORACLE_DB,
        index=True, autoincrement=False
    )
    client_id = Column(String, primary_key=IS_ORACLE_DB, index=True)

    created = Column(
        DateTime,  # primary_key=IS_ORACLE_DB,
        default=datetime.datetime.utcnow
    )
    deleted = Column(DateTime)


class ActiveDeviceWiFi(AppDeclBase, BaseModel):
    __tablename__ = "active_device_wifis"

    NO_ID_SEQUENCE = True
    id = Column(Integer, primary_key=True, autoincrement=(not IS_ORACLE_DB))
    device_id = Column(
        Integer, primary_key=IS_ORACLE_DB,
        index=True, autoincrement=False
    )
    client_id = Column(String, primary_key=IS_ORACLE_DB, index=True)

    created = Column(
        DateTime,  # primary_key=IS_ORACLE_DB,
        default=datetime.datetime.utcnow
    )
    deleted = Column(DateTime)


class ChangeWifiPasswordLog(AppDeclBase, BaseModel):
    __tablename__ = 'change_wifi_password_logs'

    NO_ID_SEQUENCE = True

    id = Column(Integer, primary_key=True, autoincrement=(not IS_ORACLE_DB))
    device_id = Column(
        Integer, primary_key=IS_ORACLE_DB,
        index=True, autoincrement=False, nullable=True
    )
    client_id = Column(String(30), primary_key=IS_ORACLE_DB, index=True)
    request = Column(String(4000))
    response = Column(JSONB, default={})
    _password = Column(String(4000), name='password_' if IS_ORACLE_DB else '_password')
    @property
    def password(self):
        return decrypt(self._password)

    @password.setter
    def password(self, password):
        self._password = encrypt(password)

    created = Column(DateTime, default=datetime.datetime.utcnow)
    confirmed = Column(DateTime)
    data = Column(JSONB, default={})

