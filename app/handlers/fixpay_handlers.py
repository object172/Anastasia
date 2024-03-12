# -*- encoding: utf-8 -*-

import base64

from app.exceptions import ApiError
from app.handlers import BaseHandler
from app.models import FixPayOrder
from app.texts import _t
from app.wrappers import client_token_required, validate

from app_utils.wrappers import memorizing
from methods_simple import get_reg_op


__all__ = (
    'FixPayMoveHandler',
    'FixPayRefundHandler',
    'FixPayRefundDetailsHandler',
    'FixPayMovePayHandler',
    'FixPayMovePayDetailsHandler',
    'FixPaySignHandler',
    'FixPayConfirmHandler',
    'FixPayHandler',
    'FixPayInfoHandler',
)


class FixPayMixin:

    OPERATORS_INFO = {
        'mts': {
            'message': u'Обратитесь в службу поддержки "МТС"',
            'phone': '8 800 250 0890',
            'phone_caption': u'Для звонков по России (бесплатный)',
            "info": u'Номер {number} принадлежит "МТС"',
        },
        'megafon': {
            'message': u'Обратитесь в службу поддержки "МегаФон"',
            'phone': '8 800 550 05 00',
            'phone_caption': u'Для звонков по России (бесплатный)',
            "info": u'Номер {number} принадлежит "Мегафон"',
        },
        'beeline': {
            'message': u'Обратитесь в службу поддержки "Билайн"',
            'phone': '8 800 700 0611',
            'phone_caption': u'Для звонков по России (бесплатный)',
            "info": u'Номер {number} принадлежит "Билайн"',
        },
        'tele2': {
            'message': u'Обратитесь в службу поддержки "Теле2"',
            'phone': '8 800 555 0611',
            'phone_caption': u'Для звонков по России (бесплатный)',
            "info": u'Номер {number} принадлежит "Теле2"',
        },
        'yota': {
            'message': u'Обратитесь в службу поддержки "Yota"',
            'phone': '',
            'phone_caption': u'',
            "info": u'Номер {number} принадлежит "Yota"',
        },
        'city': {
            'message': u'Обратитесь в службу поддержки Вашего оператора',
            'phone': '',
            'phone_caption': u'',
            "info": u'',
        },
        'sbt': {
            "error": u'Номер {number} принадлежит ООО «Сбербанк-Телеком»',
        },
        'com:unity': {
            "error": u'Номер {number} принадлежит ООО «Сбербанк-Телеком»',
        }
    }

    @property
    @memorizing
    def fpo(self):
        return self.db_session.query(FixPayOrder).filter_by(
            id=self.data['fixpay_id'],
            client_id=self.client_id,
            deleted=None
        ).first()


class FixPayMoveHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        fpo = FixPayOrder(
            client_id=self.client_id,
            order_type=FixPayOrder.ORDER_TYPE_MOVE,
        )
        fpo.number = self.data['number']
        fpo.region, fpo.operator = get_reg_op(
            fpo.number, self.db_session
        )
        fpo.order_data = self.data
        fpo.save(self.db_session)
        return {
            "fixpay_id": fpo.id
        }


class FixPayRefundHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        fpo = FixPayOrder(
            client_id=self.client_id,
            order_type=FixPayOrder.ORDER_TYPE_REFUND,
        )
        fpo.order_data = self.data
        fpo.contact_email = self.data.get('email', '')
        fpo.save(self.db_session)
        return {
            "fixpay_id": fpo.id
        }


class FixPayRefundDetailsHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.fpo is None:
            return {"error": self._t("fixpay_not_found")}
        elif self.fpo.completed is not None:
            return {"error": self._t("fixpay_is_completed")}

        self.fpo.card_data = self.data
        self.fpo.save(self.db_session)
        return {}


class FixPaySignHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.fpo is None:
            return {"error": self._t("fixpay_not_found")}
        elif self.fpo.completed is not None:
            return {"error": self._t("fixpay_is_completed")}

        self.fpo.signature = self.data['signature']
        self.fpo.save(self.db_session)
        return {}


class FixPayMovePayHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        fpo = FixPayOrder(
            client_id=self.client_id,
            order_type=FixPayOrder.ORDER_TYPE_MOVE,
        )
        fpo.number = self.data['number']
        fpo.region, fpo.operator = get_reg_op(
            fpo.number, self.db_session
        )
        fpo.save(self.db_session)

        if fpo.operator in ["sbt", "com:unity"]:
            info = None
        else:
            formated_number = FixPayOrder.format_number(fpo.number)
            info = self.OPERATORS_INFO.get(
                fpo.operator, self.OPERATORS_INFO['city']
            )
            for key, value in info.iteritems():
                info[key] = value.format(number=formated_number)

        return {
            "fixpay_id": fpo.id,
            "info": info,
        }


class FixPayMovePayDetailsHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.fpo is None:
            return {"error": self._t("fixpay_not_found")}
        elif self.fpo.completed is not None:
            return {"error": self._t("fixpay_is_completed")}

        self.fpo.order_data = self.data
        self.fpo.contact_email = self.data.get('email', '')
        if self.fpo.dst_number:
            (
                self.fpo.dst_number_region,
                self.fpo.dst_number_operator
            ) = get_reg_op(self.fpo.dst_number, self.db_session)

        self.fpo.save(self.db_session)
        return {}


class FixPayConfirmHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.fpo is None:
            return {"error": self._t("fixpay_not_found")}
        elif self.fpo.completed is not None:
            return {"error": self._t("fixpay_is_completed")}

        self.fpo.contact_phone = self.data['contact_phone']
        self.fpo.save(self.db_session, commit=False)

        status, sent_msg = self.fpo.send_secret_code(self.db_session)
        if not status:
            return {"error": sent_msg}
        return {"message": sent_msg}


class FixPayHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if self.fpo is None:
            return {"error": self._t("fixpay_not_found")}
        elif self.fpo.completed is not None:
            return {"error": self._t("fixpay_is_completed")}

        if self.data['code'].strip() != self.fpo.secret_code:
            error = self._t("fixpay_wrong_sms_code")
            _, sent_msg = self.fpo.send_secret_code(self.db_session)
            return {"error": error + sent_msg}

        self.fpo.complete(self.db_session)
        return {"message": self._t("fixpay_completed")}


class FixPayInfoHandler(BaseHandler, FixPayMixin):

    @client_token_required()
    def _post(self, *args, **kwargs):
        _, operator = get_reg_op(self.data['number'], self.db_session)
        formated_number = FixPayOrder.format_number(self.data['number'])

        response = self.OPERATORS_INFO.get(
            operator, self.OPERATORS_INFO['city']
        )
        for key, value in response.iteritems():
            response[key] = value.format(
                number=formated_number
            )
        return response
