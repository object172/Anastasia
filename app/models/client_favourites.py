# -*- encoding: utf-8 -*-

import datetime

from sqlalchemy import (
    Column,
    Integer, String, DateTime,
    or_ as sa_or, and_ as sa_and,
)
from sqlalchemy.orm import relationship
from sqlalchemy.schema import ForeignKey

from app.models.mixins import (
    AppDeclBase, BaseModel
)
from app_utils.db_utils import IS_ORACLE_DB
from app_utils.db_utils.models import JSONB


__all__ = (
    'ClientFavourite', 'ClientFavouriteNumber',
    'ClientFavouriteBillingLog',
)


class ClientFavourite(AppDeclBase, BaseModel):
    __tablename__ = "client_favourites"

    MAX_NUMBERS_COUNT = 3
    TIMEOUT = 30  # days

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    created = Column(DateTime, default=datetime.datetime.utcnow)
    activated = Column(DateTime)
    from_dt = Column(DateTime)
    until_dt = Column(DateTime)
    deleted = Column(DateTime)

    numbers = relationship(
        'ClientFavouriteNumber',
        back_populates='client_favourite',
        order_by='ClientFavouriteNumber.position',
    )

    is_active = property(lambda self: bool(self.activated and not self.deleted))


class ClientFavouriteNumber(AppDeclBase, BaseModel):
    __tablename__ = "client_favourite_numbers"

    id = Column(Integer, primary_key=True)
    client_favourite_id = Column(
        Integer, ForeignKey('client_favourites.id')
    )
    number = Column(String, name='number_' if IS_ORACLE_DB else 'number')
    position = Column(Integer)

    created = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)

    client_favourite = relationship(
        'ClientFavourite',
        back_populates='numbers',
    )

    @property
    def msisdn(self):
        return '+7' + self.number


class ClientFavouriteBillingLog(AppDeclBase, BaseModel):
    __tablename__ = "client_favourite_logs"

    # NO_ID_SEQUENCE = True
    id = Column(Integer, primary_key=True, autoincrement=(not IS_ORACLE_DB))
    client_favourite_id = Column(
        Integer, ForeignKey('client_favourites.id'),
        primary_key=IS_ORACLE_DB,
    )
    data = Column(JSONB)
    created = Column(
        DateTime, primary_key=IS_ORACLE_DB,
        default=datetime.datetime.utcnow
    )
