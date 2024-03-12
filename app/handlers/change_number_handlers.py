# -*- encoding: utf-8 -*-

from app.api import MVNOApi
from app.constants import MsisdnType, MSISDN_TYPE_PRICES
from app.exceptions import ApiError
from app.handlers import BaseHandler
from app.models import ChangeNumberOrder
from app.texts import _t
from app.wrappers import client_token_required, validate
from app_sbtelecom.api import sbTelecomApi
from app_sbt.api import SbtBillingApi
from app_regions.services import get_region_name_by_dt_id
from app_utils.wrappers import json_property, memorizing
from mc_cache_msisdn_pool import remove_cached_number, get_cached_numbers, get_cached_numbers_info
from methods_simple import trace_print, get_reg_op
from utils.login_util import create_connector


__all__ = (
    'AvailableChangeNumbersHandler',
    'ChangeNumberHandler',
)


TIERS = [
    MsisdnType.BRONZE.value,
    MsisdnType.SILVER.value,
]


class AvailableChangeNumbersHandler(BaseHandler):
    u'''
-> {
    token: 'fgsfds',
    search: '958',
    tier: null | 'Бронзовые', #строка берется из поля tiers в корне ответа, не из поля tier внутри массива номеров
    offset: 0,
    count: 10,
}
<- {
    tiers: ['Платиновые', 'Золотые', 'Бронзовые'],
    numbers: [{
        number: '9581234567',
        price: 300,
        tier: 'Бронзовый',
        isBuyable: true, #хватает денег, можно сменить на этот
    }, ...]
}
    '''

    data_search = json_property('data', 'search', default='')
    data_tier = json_property('data', 'tier', default=None)
    data_offset = json_property('data', 'offset', default=0, handler=int)
    data_count = json_property('data', 'count', default=20, handler=int)

    @client_token_required()
    def _post(self, *args, **kwargs):
        if not self.client.has_sbtelecom_operator:
            return {
                "result": 0,
                "reply": self._t("change_number_only_for_sbt"),
                "error": self._t("change_number_only_for_sbt"),
            }

        balance = create_connector(self.client).get_balance(
            self.client, db_session=self.db_session,
            autologin=True
        )['balance']

        if not self.data_search:
            numbers = [(number, tier) for tier, reg_dt_id, number in get_cached_numbers_info(
                self.data_tier or '*',
                self.region,
            )][self.data_offset:self.data_offset + self.data_count]
            print(u'GET NUMBERS: {} numbers[{}:{}]'.format(len(numbers), self.data_offset, self.data_offset + self.data_count))
        else:
            numbers = []

        if not numbers:
            print('GET NUMBERS: old way')
            numbers = self.get_numbers()

        return {
            "tiers": TIERS,
            "numbers": [{
                "number": number,
                "price": MSISDN_TYPE_PRICES[msisdn_type],
                "tier": '',  # msisdn_type,
                "isBuyable": (
                    balance is None or
                    balance >= MSISDN_TYPE_PRICES[msisdn_type]
                ),
            } for (number, msisdn_type) in numbers],
        }

    def get_numbers(self):
        print('AvailableChangeNumbersHandler', self.data_tier, self.data)
        if self.data_tier is None or self.data_tier not in TIERS:
            numbers = []
            for count, msisdn_type in enumerate(reversed(TIERS), 1):
                if msisdn_type == MsisdnType.BRONZE.value:
                    count = max(self.data_count - len(numbers), 0)

                _numbers = count and MVNOApi().getMsisdns(
                    self.region,
                    msisdn_search=self.data_search,
                    msisdn_type=msisdn_type,
                    offset=self.data_offset,
                    count=count,
                    need_msisdn_format=False,
                ) or []
                numbers += zip(_numbers, [msisdn_type] * len(_numbers))
            numbers.reverse()
        else:
            msisdn_type = self.data_tier
            numbers = MVNOApi().getMsisdns(
                self.region,
                msisdn_search=self.data_search,
                msisdn_type=msisdn_type,
                offset=self.data_offset,
                count=self.data_count,
                need_msisdn_format=False,
            )
            numbers = zip(numbers, [msisdn_type] * len(numbers))

        return numbers


class ChangeNumberHandler(BaseHandler):
    u'''
-> {
    token: 'fgsfds',
    number: '9581111112'
}
<- {
    result: 0, #единица если всё ок
    reply: 'Не вышло' #опциональное поле
    #никакие поля кроме result и reply не учитываются
}
    '''

    data_new_number = json_property('data', 'number', default=10, handler=int)

    @client_token_required()
    def _post(self, *args, **kwargs):
        if not self.client.has_sbtelecom_operator:
            print(str(self.client), 'not has_sbtelecom_operator')
            return {
                "result": 0,
                "reply": self._t("change_number_only_for_sbt"),
            }

        sbt_api = sbTelecomApi(client=self.client, db_session=self.db_session)
        if not sbt_api.isActive:
            return dict(result=0, reply=self._t("change_number_user_not_found"))

        sbt_api = SbtBillingApi(
            self.client_id,
            region=get_region_name_by_dt_id(self.client.region)
        )
        success = 1

        chn_order = ChangeNumberOrder(
            client_id=self.client_id,
            new_number=self.data_new_number,
        )

        log = {}
        try:
             r = sbt_api.replaceMsisdn(self.data_new_number)
            if not r.json:
                success = 0
            log = {
                "url": r.request_url,
                "req": r.request_text,
                "resp": r.text,
                "dt": r.request_dt.strftime(
                    '%Y-%m-%dT%H:%M:%S'
                ),
                "status": r.json
            }
        except Exception as err:
            success = 0
            if hasattr(err, 'resp_obj'):
                log = {

                    "url": err.resp_obj.request_url,
                    "req": err.resp_obj.request_text,
                    "dt": str(err.resp_obj.request_dt),
                    "resp": err.resp_obj.text,
                    "user_resp": unicode(err),
                    "status": False
                }
            else:
                try:
                    err_text = unicode(err)
                except:
                    err_text = 'error'
                log = {
                    "err": err_text,
                    "status": False,
                    "user_resp": self._t("something_wrong"),
                }
            try:
                print(err)
            except:
                pass
            try:
                trace_print()
            except:
                pass

        chn_order.log = log
        chn_order.save(self.db_session)

        if success:
            reply = None
            remove_cached_number(self.data_new_number)
        else:
            reply = log and log['user_resp'] or self._t("something_wrong")
        return {"result": success, "reply": reply}
