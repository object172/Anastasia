# -*- encoding: utf-8 -*-

import datetime
import time

from app_utils.alarm_utils import get_alarm_bot
from app_utils.db_utils import IS_ORACLE_DB


__all__ = ('BaseModel', )


class BaseModel:

    id = None
    BASE_MODEL_FILTERS = None
    NO_ID_SEQUENCE = False
    alarm = get_alarm_bot()

    def save(self, db_session, commit=True, *args, **kwargs):
        if (
                self.id is None and
                IS_ORACLE_DB and self.NO_ID_SEQUENCE
        ):
            self.id = int(time.time()) % 2147483647

        if self._sa_instance_state.session_id is None:
            db_session.add(self)

        commit and db_session.commit()
        return self

    MIN_UNIX_DT = datetime.datetime(1970, 1, 1, tzinfo=None)

    @classmethod
    def utc_datetime_to_timestamp(cls, utc_dt):
        utc_dt = utc_dt.replace(tzinfo=None)
        return int((utc_dt - cls.MIN_UNIX_DT).total_seconds())
