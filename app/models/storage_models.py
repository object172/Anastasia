import datetime
import json

from sqlalchemy import Column, Integer, String, DateTime, Sequence

from app_utils.db_utils.models import JSONB

from app.models import AppDeclBase
from app.models.mixins import BaseModel

__all__ = ('UploadOrder',)


class UploadOrder(AppDeclBase, BaseModel):

    __tablename__ = "upload_orders_v6"

    UPLOAD_ORDER_STATUS_NEW = 0
    UPLOAD_ORDER_STATUS_DONE = 1
    UPLOAD_ORDER_STATUS_ERROR = 2
    UPLOAD_ORDER_STATUS_CANCEL = 3

    id = Column(Integer, Sequence('upload_order_id_seq'), primary_key=True)

    order_id = Column(Integer, index=True)
    subscriber_id = Column(Integer, index=True)
    doctype = Column(String(50), index=True)
    filename = Column(String(500), index=True)

    status = Column(Integer, nullable=False, default=UPLOAD_ORDER_STATUS_NEW, index=True)

    data = Column(JSONB)

    created = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)
    order_created = Column(DateTime)
    last_upload_try = Column(DateTime, index=True)

    logs = Column(JSONB, default={})

    def print_logs(self):
        for title, log in self.logs.items():
            print(title)
            print(log.get('datetime'))
            print(json.dumps(log.get('logs', {}), indent=4, ensure_ascii=False))
            print('===')

    def update_logs(self, data, db_session):
        dt = str(datetime.datetime.utcnow())
        logs = {}
        for k, v in self.logs.items():
            if type(v) is dict and v.get('datetime'):
                log = v
            else:
                log = {
                    'logs': v,
                    'datetime': dt
                }
            logs[k] = log

        for k, v in data.items():
            key = k
            i = 1
            while key in logs:
                key = '{}({})'.format(k, i)
                i += 1

            logs[key] = {
                'logs': v,
                'datetime': dt
            }
        self.logs = logs
        db_session.commit()
        return self.logs




