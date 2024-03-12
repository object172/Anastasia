# -*- encoding: utf-8 -*-

from app.api import PodkliuchiServerApi
from app.exceptions import ApiError
from app.handlers import BaseHandler, RedirectHandler
from app.models import SubscriberContractOrder, Confirm
from app.services import get_subscriber_contract_data
from app.texts import _t
from app.wrappers import client_token_required, validate

from app_utils.wrappers import memorizing


__all__ = (
    'SubscriberContractEditDetailsHandler',
    'SubscriberContractEditFilesHandler',
    'SubscriberContractEditSignHandler',
    'SubscriberContractEditConfirmHandler',
    'SubscriberContractEditHandler',
    'GetSubscriberContractCancelLinkHandler',
    'SubscriberContractCancelFullHandler',
    'SubscriberContractCancelHandler',
    'SubscriberContractDetailsHandler',
)


class SubscriberContractEditMixin:

    SCO_REQUIRED = False

    @property
    @memorizing
    def sco(self):
        contract_edit_id = self.data.get('contract_edit_id')

        sco = contract_edit_id and self.db_session.query(
            SubscriberContractOrder
        ).filter_by(
            id=contract_edit_id,
            client_id=self.client_id,
            deleted=None
        ).first()

        if sco or self.SCO_REQUIRED:
            return sco

        sco = SubscriberContractOrder(
            client_id=self.client_id,
            order_type=SubscriberContractOrder.ORDER_TYPE_EDIT_SUBS_DATA,
        )
        return sco


class SubscriberContractEditDetailsHandler(BaseHandler, SubscriberContractEditMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        self.sco.order_data = self.data
        self.sco.save(self.db_session)
        return {
            "contract_edit_id": self.sco.id
        }


class SubscriberContractEditFilesHandler(BaseHandler, SubscriberContractEditMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.sco is None:
            return {"error": self._t("subs_contract_not_found")}
        elif self.sco.completed is not None:
            return {"error": self._t("subs_contract_is_completed")}

        self.sco.photo1 = self.data.get('photo1')
        self.sco.photo2 = self.data.get('photo2')
        self.sco.photo3 = self.data.get('photo3')

        self.sco.save(self.db_session)
        return {
            "contract_edit_id": self.sco.id
        }


class SubscriberContractEditSignHandler(BaseHandler, SubscriberContractEditMixin):

    SCO_REQUIRED = True

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.sco is None:
            return {"error": self._t("subs_contract_not_found")}
        elif self.sco.completed is not None:
            return {"error": self._t("subs_contract_is_completed")}

        self.sco.signature = self.data['signature']
        self.sco.save(self.db_session)
        return {}


class SubscriberContractEditConfirmHandler(BaseHandler, SubscriberContractEditMixin):

    SCO_REQUIRED = True

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.sco is None:
            return {"error": self._t("subs_contract_not_found")}
        elif self.sco.completed is not None:
            return {"error": self._t("subs_contract_is_completed")}

        self.sco.contact_phone = self.data.get('contact_phone')
        self.sco.save(self.db_session)

        confirm = Confirm(
            client_id=self.sco.client_id,
            confirm_item='SubscriberContract',
            confirm_item_id=self.sco.id,
        )
        confirm.contact_phone = self.sco.contact_phone
        confirm.save(self.db_session)
        status, message = confirm.send_secret_code(self.db_session,
            sms_text=self._t("confirm_subs_contract_edit_sms_text")
        )

        if status:
            return {
                "confirmation_id": confirm.id,
                "message": message,
                "result": 1,
            }
        else:
            return {
                "error": message,
                "result": 0,
            }


class SubscriberContractEditHandler(BaseHandler, SubscriberContractEditMixin):

    SCO_REQUIRED = True

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.sco is None:
            return {"error": self._t("subs_contract_not_found")}
        elif self.sco.completed is not None:
            return {"error": self._t("subs_contract_is_completed")}

        self.info(u"{} {}".format(self.sco.id, self.data))

        confirm = Confirm.get(
            self.db_session,
            confirm_item='SubscriberContract',
            confirm_item_id=self.sco.id,
            secret_code=self.data.get('code'),
        )

        if confirm is None:
            self.info(u"{} not confirmed {}".format(self.sco.id, self.data))
            resp = {
                "error": self._t("confirm_wrong_sms_code"),
                "result": 0,
            }
            return resp

        self.sco.contact_email = self.data["contact_email"]
        self.sco.complete(self.db_session)
        resp = {
            "message": self._t("subs_contract_completed"),
            "result": 1,
        }
        self.info(u"{} confirmed {}".format(self.sco.id, self.data))
        return resp


class GetSubscriberContractCancelLinkHandler(RedirectHandler):

    def get(self, order_hash, *args, **kwargs):
        try:
            resp_json = PodkliuchiServerApi.getCancelContractlLink(
                order_hash
            )
            link = resp_json['link']
        except:
            link = 'https://lk.sbt-tele.com'
        return self.redirect(link)


class SubscriberContractCancelFullHandler(BaseHandler):

    @client_token_required()
    def _post(self, *args, **kwargs):
        sco = SubscriberContractOrder(
            client_id=self.client_id,
            order_type=SubscriberContractOrder.ORDER_TYPE_CANCEL_SUBS,
        )
        sco.signature = self.data.pop("signature")
        sco.contact_phone = self.data.pop("contact_phone")
        sco.order_data = self.data
        sco.save(self.db_session)

        confirm = Confirm(
            client_id=sco.client_id,
            confirm_item='SubscriberContract',
            confirm_item_id=sco.id,
        )
        confirm.contact_phone = self.sco.contact_phone
        confirm.save(self.db_session)

        status, message = confirm.send_secret_code(
            self.db_session,
            sms_text=self._t("confirm_subs_contract_cancel_sms_text")
        )

        if status:
            return {
                "contract_cancel_id": sco.id,
                "confirmation_id": confirm.id,
                "message": message,
                "result": 1,
            }
        else:
            return {
                "contract_cancel_id": sco.id,
                "error": message,
                "result": 0,
            }


class SubscriberContractCancelHandler(BaseHandler):

    def _post(self, *args, **kwargs):
        confirm = Confirm.get(
            self.db_session,
            confirm_id=self.data.get('confirmation_id'),
            confirm_item='SubscriberContract',
            secret_code=self.data.get('code'),
        )
        if confirm is None:
            return {
                "error": 1,
                "reply": _t("confirm_wrong_sms_code"),
            }

        sco = self.db_session.query(SubscriberContractOrder).filter(
            SubscriberContractOrder.id == confirm.confirm_item_id,
        ).first()
        if sco is None:
            return {"error": self._t("subs_contract_not_found")}
        elif sco.completed is not None:
            return {
                "message": self._t("subs_contract_completed"),
                "result": 1,
            }

        sco.contact_email = self.data["contact_email"]
        sco.complete(self.db_session)
        return {
            "message": self._t("subs_contract_completed"),
            "result": 1,
        }


class SubscriberContractDetailsHandler(BaseHandler):

    @client_token_required()
    def _post(self, *args, **kwargs):
        return get_subscriber_contract_data(self.client)
