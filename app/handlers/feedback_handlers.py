# -*- encoding: utf-8 -*-

from app.exceptions import ApiError
from app.handlers import BaseHandler, RedirectHandler
from app.models import FeedbackOrder
from app.texts import _t
from app.wrappers import client_token_required, validate
from app_utils.wrappers import memorizing


__all__ = ('FeedbackHandler', )


class FeedbackHandler(BaseHandler):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if not self.data.get('name'):
            return {"error": self._t("feedback_enter_name")}
        elif not self.data.get('phone'):
            return {"error": self._t("feedback_enter_contact_phone")}
        elif not self.data.get('email'):
            return {"error": self._t("feedback_enter_email")}
        elif not self.data.get('question'):
            return {"error": self._t("feedback_enter_question")}

        order = FeedbackOrder(client_id=self.client_id)
        order.order_data = self.data
        order.os = self.device.os or '-'
        order.app_version = self.device.app_version or '-'
        order.complete(self.db_session)
        return {
            "message": self._t("feedback_success")
        }
