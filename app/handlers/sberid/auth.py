# -*- encoding: utf-8 -*-
import lazy_object_proxy
import re
import time
import tornado

from app.handlers import BaseHandler
from handlers import AsyncHandlerV2
# from app.models import sbIdData
from app_models import (
    DeviceData, Client
)
from app_sbt.api.sbid_api import sbIdApi
from app_utils.wrappers import json_property
from app_utils.logger_utils import get_logger


__all__ = (
    'AuthsbIdHandler',
    'AuthRedirectsbIdHandler',
)


class AuthsbIdHandler(AsyncHandlerV2):

    HANDLE_WITHOUT_AUTH = True
    TIMEOUT = 30

    logger = lazy_object_proxy.Proxy(lambda: get_logger('sbIdApi'))

    data_sbid_token = json_property('data', 'sbid_token')
    data_auth_code = json_property('data', 'auth_code')
    data_state = json_property('data', 'state')
    data_status = json_property('data', 'status')

    def _worker(self, db_session, redis_session, *args, **kwargs):
        self.logger.info('AuthsbIdHandler(sbid_token={}).start'.format(
            self.data_sbid_token
        ))
        start_time = time.time()
        _ = db_session.query(Client).filter_by(number="9581234567").first()
        self.logger.info('AuthsbIdHandler(sbid_token={}).test_client: {}'.format(
            self.data_sbid_token, round(time.time() - start_time, 3)
        ))
        start_time = time.time()
        device = (
            db_session.query(DeviceData).filter(
                DeviceData.token == self.data_sbid_token,
            ).first()
        )
        self.logger.info('AuthsbIdHandler(sbid_token={}).device: {}'.format(
            self.data_sbid_token, round(time.time() - start_time, 3)
        ))
        start_time = time.time()

        if (
                not device or not self.data_state or
                device.sbid_state != self.data_state
        ):
            if not device:
                error_reason = 'not device'
            elif not self.data_state:
                error_reason = 'not state'
            else:
                error_reason = '{}: {} != {}'.format(
                    device.id,
                    device.sbid_state,
                    self.data_state
                )
            self.answer_data = {
                "error": u"Заявка не найдена",
                "result": 0,
                "error_reason": error_reason,
            }
            try:
                print('AuthsbIdHandler: {} {}\n'.format(
                        self.data, self.answer_data
                    ))
            except:
                pass
            return

        self.logger.info('AuthsbIdHandler(sbid_token={}).check_device: {}'.format(
            self.data_sbid_token, round(time.time() - start_time, 3)
        ))
        start_time = time.time()

        api = sbIdApi(device, db_session=db_session)  # sbid_data,
        self.logger.info('AuthsbIdHandler(sbid_token={}).api.init: {}'.format(
            self.data_sbid_token, round(time.time() - start_time, 3)
        ))
        start_time = time.time()
        api.auth(self.data_auth_code)
        self.logger.info('AuthsbIdHandler(sbid_token={}).api.auth: {}'.format(
            self.data_sbid_token, round(time.time() - start_time, 3)
        ))
        start_time = time.time()

        if not device.sbid_auth_token:
            self.answer_data = {
                "error": u"Что-то пошло не так: данные не получены. Попробуйте позже",
                "result": 0,
            }
            try:
                print('AuthsbIdHandler: {} {}'.format(
                    self.data, self.answer_data
                ))
            except:
                pass
            return

        userinfo = api.get_userinfo()
        self.logger.info('AuthsbIdHandler(sbid_token={}).api.userinfo: {}'.format(
            self.data_sbid_token, round(time.time() - start_time, 3)
        ))
        start_time = time.time()
        self.answer_data = {"result": 1}
        self._parse_userinfo(userinfo)
        try:
            print('AuthsbIdHandler: {} {}'.format(
                self.data, self.answer_data
            ))
        except:
            pass
        self.logger.info('AuthsbIdHandler(sbid_token={})._parse_userinfo: {}'.format(
            self.data_sbid_token, round(time.time() - start_time, 3)
        ))
        return

    def _parse_userinfo(self, userinfo):
        msisdn = userinfo.get('phone_number') or ''
        msisdn = msisdn and u''.join(re.findall('\d', msisdn))

        fio = u' '.join(list(filter(bool, [
            userinfo.get('family_name'),
            userinfo.get('given_name'),
            userinfo.get('last_name'),
        ])))

        docid = userinfo.get('passport_number')
        if docid:
            serial = docid[:-6]
            docid = docid[-6:]
        else:
            serial = None

        birthdate = userinfo.get('birthdate') or ''
        birthdate = birthdate and u'-'.join(
            reversed(birthdate.split('.'))
        )
        self.answer_data.update({
            "msisdn": msisdn or None,
            "client": {
                "fio": fio or None,
                "birthdate": birthdate or None,
                "docid": docid or None,
                "serial": serial or None,
            },
        })


class AuthRedirectsbIdHandler(BaseHandler):

    def _get(self, *args, **kwargs):
        return {}

    def _post(self, *args, **kwargs):
        return {}
