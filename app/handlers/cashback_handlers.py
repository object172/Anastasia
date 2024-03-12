# -*- encoding: utf-8 -*-

from app.handlers import BaseHandler
from app.models import Cashback
from app.wrappers import client_token_required
from app_utils.wrappers import memorizing


__all__ = ('CashbackHistoryHandler', )


class CashbackHistoryHandler(BaseHandler):

    @property
    @memorizing
    def on_page(self):
        try:
            return int(self.data['count'])
        except:
            return 50

    @property
    @memorizing
    def offset(self):
        try:
            return int(self.data['offset'])
        except:
            return 0

    @client_token_required()
    def _post(self, *args, **kwargs):
        cashbacks = self.db_session.query(Cashback).filter(
            Cashback.client_id == self.client_id,
            Cashback.deleted == None
        ).order_by(
            Cashback.created.desc()
        ).offset(self.offset).limit(self.on_page).all()

        response = {
            "result": 1,
            "history": [self.cashback_view(c) for c in cashbacks],
            "offset": self.offset,
            "count": self.on_page,
        }
        return response

    @classmethod
    def cashback_view(cls, cashback):
        return {
            "id": cashback.id,
            "amount": cashback.amount and float(cashback.amount) or 0,
            "datetime": cashback.created.strftime('%Y-%m-%dT%H:%M:%S'),
            "status": cashback.status_id,
            "status_text": cashback.status_text,
            "title": cashback.name,
            "category": cashback.category,
            "cashback": cashback.reward,
            "waiting": cashback.reward_delay,
            "favicon": cashback.favicon,
        }
