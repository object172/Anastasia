# -*- encoding: utf-8 -*-

import datetime

from app.models.mixins import AppDeclBase, BaseModel
from app_utils.db_utils import IS_ORACLE_DB
from sqlalchemy import Column, DateTime, Integer, String

__all__ = (
    'BillingEvent',
)


class BillingEvent(AppDeclBase, BaseModel):
    __tablename__ = "billing_events_2020"

    message_id = Column(String(128), primary_key=True, autoincrement=False, unique=True)
    subscriber_id = Column(String(128), index=True)

    type = Column(String(128), index=True)
    msisdn = Column(String(128), index=True)

    headers = Column(String(1024))
    message = Column(String(4000))

    created = Column(DateTime, default=datetime.datetime.utcnow)
    completed = Column(DateTime)
    checked = Column(DateTime)
    deleted = Column(DateTime)
