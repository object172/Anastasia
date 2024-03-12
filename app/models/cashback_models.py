# -*- encoding: utf-8 -*-

import datetime

from sqlalchemy import (
    Column, Integer, String,
    DateTime, Boolean
)
from sqlalchemy import (
    or_ as sql_or
)
from app_utils.db_utils import IS_ORACLE_DB
from app_utils.db_utils.models import JSONB
from app.models.mixins import (
    AppDeclBase, BaseModel,
    jsonb_property,
)
from app.texts import _t
from app_utils.wrappers import memorizing
from methods_simple import get_reg_op


__all__ = (
    'Cashback',
)


class Cashback(AppDeclBase, BaseModel):
    __tablename__ = "cashbacks"

    STATUS_REJECT = -1
    STATUS_OPEN = 0
    STATUS_APPROVED = 1

    STATUSES_TO_ID = {
        'reject': STATUS_REJECT,
        'open': STATUS_OPEN,
        'approved': STATUS_APPROVED,
    }

    STATUSES_TO_TEXT = {
        'reject': u'Отклонён',
        'open': u'Открыт',
        'approved': u'Выполнен',
    }

    NO_ID_SEQUENCE = True
    id = Column(Integer, primary_key=True, autoincrement=(not IS_ORACLE_DB))
    client_id = Column(String, primary_key=IS_ORACLE_DB, index=True)

    status_id = Column(Integer, default=STATUS_OPEN)
    data = Column(JSONB, default={})

    created = Column(
        DateTime,  # primary_key=IS_ORACLE_DB,
        default=datetime.datetime.utcnow
    )
    deleted = Column(DateTime)

    device_id = jsonb_property('data', 'device_id')
    name = jsonb_property('data', 'offer_name', '')
    target = jsonb_property('data', 'target_name', '')
    amount = jsonb_property('data', 'amount', '')
    currency = jsonb_property('data', 'currency', '')
    status = jsonb_property('data', 'status', '')
    status_text = property(lambda self: self.STATUSES_TO_TEXT.get(
        self.status, self.STATUSES_TO_TEXT['open']
    ))
    clicked = jsonb_property('data', 'click_tm', '')

    category = jsonb_property('data', 'category', '')
    reward = jsonb_property('data', 'reward', '')
    _reward_delay = jsonb_property('data', 'reward_delay', '?')
    reward_delay = property(lambda self: u'{} дн'.format(self._reward_delay))
    favicon = jsonb_property('data', 'favicon', None)

    def save(self, *args, **kwargs):
        status_id = self.STATUSES_TO_ID.get(self.status, self.STATUS_OPEN)
        if self.status_id != status_id:
            self.status_id = status_id

        if self.created is None:
            self.created = datetime.datetime.utcfromtimestamp(self.clicked)

        return super(Cashback, self).save(*args, **kwargs)
