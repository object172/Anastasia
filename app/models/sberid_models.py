# -*- encoding: utf-8 -*-

import datetime

from sqlalchemy import Column, Integer, String, DateTime
from app_utils.db_utils import IS_ORACLE_DB

from app.models.mixins import (
    AppDeclBase, BaseModel
)


__all__ = (
    'sbIdData',
)


class sbIdData(AppDeclBase, BaseModel):
    __tablename__ = "sbid_data"

    NO_ID_SEQUENCE = True
    id = Column(Integer, primary_key=True, autoincrement=(not IS_ORACLE_DB))

    back_client_id = Column(String)
    back_client_secret = Column(String)
    back_redirect_uri = Column(String)

    app_client_id = Column(String)
    app_client_secret = Column(String)
    app_scope = Column(String, default='openid+name+maindoc+birthdate+mobile')
    app_redirect_uri = Column(String)

    created = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)
