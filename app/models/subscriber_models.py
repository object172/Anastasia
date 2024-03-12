# -*- encoding: utf-8 -*-

import datetime

from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import synonym
from app_utils.db_utils import IS_ORACLE_DB
from app_utils.db_utils.models import JSONB

from app.models.mixins import (
    AppDeclBase, BaseModel, jsonb_property
)
from app_utils.wrappers import memorizing


__all__ = (
    'Subscriber',
)


class Subscriber(AppDeclBase, BaseModel):
    __tablename__ = "subscribers"

    NO_ID_SEQUENCE = True
    id = Column(Integer, primary_key=True, autoincrement=(not IS_ORACLE_DB))
    client_id = Column(String, primary_key=IS_ORACLE_DB, index=True)
    subs_id = Column(String, primary_key=IS_ORACLE_DB, index=True)              # billing.clientId

    data = Column(JSONB, default={})
    email = jsonb_property('data', 'email', '')

    created = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)

    msisdn = synonym('client_id')                                             # billing.msisdn
    clientId = synonym('subs_id')                                             # billing.clientId
    subscriberId = jsonb_property('data', 'subscriberId')                     # billing.subsId
