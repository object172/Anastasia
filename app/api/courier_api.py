# -*- encoding: utf-8 -*-

import sys

import datetime
import traceback

from app.exceptions import ServerError, ApiDataError
from app.texts import _t

from app_sbt.api import CourierIMLApi
from app_utils.json_utils import json
from app_utils.redis_utils import get_current_redis


if (sys.version_info > (3, 0)):
    unicode = str


__all__ = ('CourierApi', )


class CourierApi:

    COURIER_IML = 'IML'

    redis_session = get_current_redis()

    CACHE_ORDER_STATUS_KEY_TEMPLATE = 'cache:courier:order:status:{uid}'
    CACHE_ORDER_STATUS_TIMEOUT = 5 * 60  # sec

    @classmethod
    def get_cache_order_status_key(cls, uid):
        return cls.CACHE_ORDER_STATUS_KEY_TEMPLATE.format(uid=uid)

    def __init__(self, courier='IML', is_test_mode=False):
        self.courier = courier
        if courier == self.COURIER_IML:
            self.api = CourierIMLApi(is_test_mode=is_test_mode)

    def get_order_status(self, uid):
        order_status_data = self.redis_session.get(self.get_cache_order_status_key(uid))
        if order_status_data is not None:
            order_status_data = json.loads(order_status_data)
            return order_status_data

        try:
            json_resp = self.api.get_order_status(uid)
        except Exception as err:
            raise ServerError(
                alert_text=_t('courier_not_available'),
                error_reason='request to courier api "getStatus" is failed',
                courier=self.courier, err_obj=unicode(err),
            )

        if not json_resp:
            order_status_data = dict(
                order_status=_t('courier_not_found_order_title'),
            )
        else:
            order_data = json_resp[0]

            order_status = order_data.get("OrderStatusDescription") or ''
            if not order_status or order_status == u'-':
                order_status = ''

            state_status = order_data.get("StateDescription") or ''
            if not state_status or state_status == u'-':
                state_status = ''

            order_status_data = dict(
                updated=order_data.get('StatusDate'),
                order_status=order_status,
                state_status=state_status,
                delivery_date=order_data['DeliveryDate'].split('T')[0],
            )

        self.redis_session.setex(
            self.get_cache_order_status_key(uid),
            self.CACHE_ORDER_STATUS_TIMEOUT,
            json.dumps(order_status_data)
        )
        return order_status_data
