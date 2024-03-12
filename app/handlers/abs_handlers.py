# -*- encoding: utf-8 -*-

import json
import re
import sys
import traceback
from distutils.version import LooseVersion

import lazy_object_proxy
from app.exceptions import (ApiDataError, ApiError, AppError, AuthError,
                            ServerDataError, ServerError)
from app.texts import _t
from app_models import Client_lk, ClientToken, DeviceData
from app_utils.alarm_utils import get_alarm_bot
from app_utils.db_utils import get_current_dbsession
from app_utils.logger_utils import get_logger
from app_utils.redis_utils import get_current_redis_session
from app_utils.wrappers import memorizing
from methods_simple import get_reg_op
from tornado import gen, web
from tornado.concurrent import run_on_executor
from tornado.escape import utf8

__all__ = ('BaseHandler', 'RedirectHandler', )


DB_SESSION = lazy_object_proxy.Proxy(get_current_dbsession)
REDIS_SESSION = lazy_object_proxy.Proxy(get_current_redis_session)


class BaseHandler(web.RequestHandler):

    db_session = DB_SESSION
    redis = REDIS_SESSION
    redis_session = REDIS_SESSION
    alarm = get_alarm_bot()
    logger = get_logger('app')

    api_regexp = re.compile('^/v(\d[\d.]*?)/')

    @property
    @memorizing
    def api_version(self):
        api_ver = self.api_regexp.match(self.request.uri)
        api_ver = api_ver and api_ver.group(1) or '0'
        return LooseVersion(api_ver)

    api_ver = api_version

    def _t(self, key, **kwargs):
        return _t(key, handler=self, **kwargs)

    @property
    def executor(self):
        return self.application.executor

    def _print(self, *strings):
        try:
            sys.stderr.write(u'{}\n'.format(strings))
        except:
            pass

    # @run_on_executor
    def info(self, *texts):
        text = ''
        try:
            for _text in texts:
                text += _text + u'\n'
        except Exception as err:
            # self.error('send info', error=err)
            pass

        if text:
            self.alarm.info(text)
            self.logger.info(text)

    # @run_on_executor
    def debug(self, *texts):
        text = ''
        try:
            for _text in texts:
                text += _text + '\n'
        except Exception as err:
            # self.error('send debug', error=e)
            pass

        if text:
            self.alarm.debug(text)
            self.logger.debug(text)

    # @run_on_executor
    def error(self, texts, error=None, traceback_text='', trace=True):
        try:
            traceback_text = (
                traceback_text or
                trace and traceback.format_exc()
            ) or ''
        except Exception as err:
            print(err)
            traceback_text = u'Can\'t get traceback_text'

        if isinstance(texts, basestring):
            texts = [texts, ]

        text = ''
        try:
            try:
                for _text in texts:
                    text += _text + u'\n'
            except:
                pass

            try:
                error_text = (
                    'error' if error is None else unicode(error)
                )
            except Exception as err:
                print(err)
                error_text = u'Can\'t get error_text'

            text += u'\n{}: {}'.format(error_text, traceback_text)
        except Exception as err:
            self.error('send error', error=err)

        if text:
            self.alarm.error(text, trace=False)
            self.logger.error(text)

    @property
    @memorizing
    def data(self):
        data = {}
        for field, values in self.request.arguments.items():
            if isinstance(values, (list, tuple)):
                values = [val.decode('utf-8') for val in values]
                if len(values) == 1:
                    values = values[0]
            else:
                values = values.decode('utf-8')
            data[field] = values

        data.update(self.get_json())
        return data

    @memorizing
    def get_json(self):
        try:
            return self.request.body and json.loads(
                self.request.body.decode('utf8')
            ) or {}
        except Exception as err:
            # self.error('get_json', error=err)
            return {}

    @property
    @memorizing
    def token(self):
        return (
            self.data.get('orderStatusToken') or
            self.data.get('token') or
            None
        )

    @property
    @memorizing
    def client_token(self):
        client_token = self.token and self.db_session.query(ClientToken).filter_by(
            token=self.token, status=1, deleted=None
        ).first()
        return client_token

    @property
    @memorizing
    def client_id(self):
        return self.client_token and self.client_token.client_id

    @property
    @memorizing
    def client(self):
        return self.client_id and self.db_session.query(Client_lk).filter_by(
            number=self.client_id,
        ).first()

    @property
    @memorizing
    def region(self):
        region, _ = get_reg_op(self.client_id, self.db_session)
        return region

    @property
    @memorizing
    def number(self):
        client_token = self.token and self.db_session.query(ClientToken).filter_by(
            token=self.token, deleted=None
        ).first()
        return client_token and client_token.client_id

    @property
    @memorizing
    def device(self):
        return self.token and self.client_id and self.db_session.query(
            DeviceData
        ).filter_by(
            token=self.token,
            client_id=self.client_id,
        ).order_by(DeviceData.id.desc()).first()

    @property
    @memorizing
    def device_uid(self):
        return self.device and self.device.device_id

    WRIGHT_AUTH_CODES = ClientToken.WRIGHT_AUTH_CODES

    @property
    @memorizing
    def is_auth(self):
        return (
            self.client_token and
            self.client_token.status == ClientToken.STATUS_CONFIRMED and
            self.client_token.code in self.WRIGHT_AUTH_CODES
        )

    def send(self, data):
        self.set_header('Content-type', 'application/json')
        self.write(json.dumps(data, indent=2))

    NEED_SERVER_ERROR_ALERT = True

    def handle_request(self, handler, args, kwargs):
        try:
            response_data = handler(*args, **kwargs)
        except (AuthError, ApiDataError) as err:
            response_data = err.response_data
            self.debug(
                u'{} {}:\n{}\n{}\n{}'.format(
                    err.__class__.__name__,
                    self.__class__.__name__,
                    self.client_id, self.data,
                    err
                )
            )
        except AppError as err:
            response_data = err.response_data
            self.error(
                u'{} {}:\n{}\n{}'.format(
                    err.__class__.__name__,
                    self.__class__.__name__,
                    self.client_id, self.data,
                ), error=err, trace=False
            )
        except Exception as err:
            response_data = {
                'exception':  'unexpected_error',
                'error': self._t('something_wrong'),
                'error_text': self._t('something_wrong'),
                'result': 0,
            }

            self.error(
                u'{} {}:\n{}\n{}'.format(
                    err.__class__.__name__,
                    self.__class__.__name__,
                    self.client_id, self.data,
                ), error=err
            )

            self.db_session.rollback()

        self.send(response_data)

    # @gen.coroutine
    def get(self, *args, **kwargs):
        self.handle_request(self._get, args, kwargs)

    def _get(self, *args, **kwargs):
        raise ApiError(error_text='not valid method')

    # @gen.coroutine
    def post(self, *args, **kwargs):
        self.handle_request(self._post, args, kwargs)

    def _post(self, *args, **kwargs):
        raise ApiError(error_text='not valid method')

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def set_default_headers(self):
        self.set_header('Access-Control-Allow-Origin', '*')
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, DELETE')
        self.set_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')


class RedirectHandler(web.RequestHandler):

    db_session = DB_SESSION

    def redirect(self, url, permanent=False, status=None):
        """Sends a redirect to the given (optionally relative) URL.

        If the ``status`` argument is specified, that value is used as the
        HTTP status code; otherwise either 301 (permanent) or 302
        (temporary) is chosen based on the ``permanent`` argument.
        The default is 302 (temporary).
        """
        if self._headers_written:
            raise Exception("Cannot redirect after headers have been written")

        if status is None:
            status = 301 if permanent else 302
        else:
            assert isinstance(status, int) and 300 <= status <= 399

        self.set_status(status)
        self.set_header("Location", utf8(url))
        self.finish()