# -*- encoding: utf-8 -*-

import datetime
import re

import app.services  # DON'T DELETE!

from app.exceptions import ApiError
from app.handlers import BaseHandler
from app.models import Confirm
from app.texts import _t


__all__ = (
    'ConfirmHandler',
    'ConfirmVerificationHandler',
)


class ConfirmHandler(BaseHandler):

    PHONE_REGEXP = re.compile(ur'^(\d{10,11})$')
    CLEAN_PHONE_REGEXP = re.compile(ur'[\s\(\)\-\+\—]+')

    def _post(self, *args, **kwargs):
        phone = (self.data.get('phone') or u'').strip()
        phone = self.CLEAN_PHONE_REGEXP.sub(u'', phone)
        phone = self.PHONE_REGEXP.search(phone)
        if phone is None:
            return {
                "error": self._t("wrong_phone"),
                "result": 0,
            }
        phone = phone.group(1)[-10:]

        self.db_session.query(Confirm).filter(
            Confirm.confirm_item == 'Confirm',
            Confirm.client_id == phone,
            Confirm.deleted == None,
        ).update({
            "deleted": datetime.datetime.utcnow()
        }, synchronize_session='fetch')

        confirm = Confirm(
            confirm_item='Confirm',
            client_id=phone,
        )
        confirm.contact_phone = phone
        confirm.save(self.db_session)

        status, message = confirm.send_secret_code(self.db_session,
            sms_text=self._t("confirm_sent_sms_code_text")
        )
        if status:
            return {
                "confirmation_id": confirm.id,
                "message": message,
                "result": 1,
            }

        return {
            "error": message,
            "result": 0,
        }


class ConfirmVerificationHandler(BaseHandler):

    def _post(self, *args, **kwargs):
        confirm = Confirm.get(self.db_session,
            confirm_id=self.data.get('confirmation_id'),
            confirm_item='Confirm',
            secret_code=self.data.get('code'),
        )

        if confirm is None:
            return {
                "error": self._t("confirm_wrong_sms_code"),
                "result": 0,
            }

        return {
            "message": self._t("confirmed_sms_code"),
            "result": 1,
        }
