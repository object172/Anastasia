# -*- encoding: utf-8 -*-

import jwt

from app.api import PdServerApi
from app.exceptions import ApiError
from app.handlers import BaseHandler, RedirectHandler
from app.models import SubscriberContractOrder, Confirm
from app.services import get_subscriber_contract_data
from app.texts import _t
from app.wrappers import client_token_required, validate

from app_utils.wrappers import memorizing
from settings import JWT_PODKLIUCHI_POGOVORIM_SECRET


__all__ = (
    'GetSubscriberContractCancelLinkHandler',
    'SubscriberContractCancelFullHandler',
    'SubscriberContractCancelHandler',
)


class CORSMixin:

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, DELETE')
        self.set_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')


class GetSubscriberContractCancelLinkHandler(CORSMixin, RedirectHandler):

    def get(self, order_hash, *args, **kwargs):
        try:
            resp_json = PdServerApi.getCancelContractlLink(
                order_hash
            )
            link = resp_json['link']
        except:
            link = 'https://lk.sbt-tele.com'
        return self.redirect(link)


class SubscriberContractCancelFullHandler(CORSMixin, BaseHandler):

    def _post(self, *args, **kwargs):
        url_query = self.data.get('urlQueryString') or ''
        jwt_token = url_query.split('token=')[-1].split('&')[0]

        try:
            token_data = jwt.decode(
                jwt_token, JWT_PODKLIUCHI_POGOVORIM_SECRET,
            )
        except jwt.exceptions.ExpiredSignatureError:
            return {
                "result": 0,
                "error": u'Ссылка для расторжения договора истекла',
            }
        except:
            return {
                "result": 0,
                "error": u'Невалидная ссылка для расторжения договора',
            }

        number = unicode(self.data.get('number') or '')
        if token_data.get('omsisdn') != '7' + number:
            return {
                "result": 0,
                "error": u'Данная ссылка выдана для другого номера',
            }

        sco = SubscriberContractOrder(
            client_id=number,
            order_type=SubscriberContractOrder.ORDER_TYPE_CANCEL_SUBS,
        )
        sco.signature = self.data.pop("signature")
        sco.contact_phone = self.data.pop("contact_phone")
        sco.order_data = self.data

        client_data = get_subscriber_contract_data(number=number) or {}
        if not (
                self.data.get('docid') == client_data.get('docid') and
                self.data.get('serial') == client_data.get('serial'),
        ):
            return {
                'result': 0,
                'error': 'Проверка данных не пройдена. Проверьте ввод',
            }
        sco.fio = client_data.get('fio', '')
        sco.save(self.db_session)

        confirm = Confirm(
            client_id=sco.client_id,
            confirm_item='SubscriberContract',
            confirm_item_id=sco.id,
        )
        confirm.contact_phone = sco.contact_phone
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


class SubscriberContractCancelHandler(CORSMixin, BaseHandler):

    def _post(self, *args, **kwargs):
        confirm = Confirm.get(
            self.db_session,
            confirm_id=self.data.get('confirmation_id'),
            confirm_item='SubscriberContract',
            secret_code=self.data.get('code'),
        )
        if confirm is None:
            return {"error": self._t("confirm_wrong_sms_code")}

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

        sco.contact_email = self.data["email"]
        sco.complete(self.db_session)
        return {
            "message": self._t("subs_contract_completed"),
            "result": 1,
        }
