# -*- encoding: utf-8 -*-

import datetime

from sqlalchemy import (
    Column,
    Integer, String, DateTime,
)

from app.models.mixins import (
    AppDeclBase, BaseModel
)
from app_utils.db_utils.models import JSONB, jsonb_property


__all__ = ('ChangeNumberOrder',)


class ChangeNumberOrder(AppDeclBase, BaseModel):
    __tablename__ = "change_number_orders"

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)
    new_number = Column(String, index=True)

    data = Column(JSONB)

    created = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)

    log = jsonb_property('data', 'log')
