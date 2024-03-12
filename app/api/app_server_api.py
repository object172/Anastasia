# -*- encoding: utf-8 -*-

import sys
import datetime
import json
import jwt
import requests
import time
import traceback

from io import BytesIO
from functools import wraps
from uuid import uuid4


if (sys.version_info > (3, 0)):
    unicode = str

from app.texts import _t
from app.exceptions import (
    ServerError, ApiError, ApiDataError
)

from settings import (
    JWT_APP_SERVER_SECRET,
)


__all__ = ('AppServerApi', )


def error_wrapper(
        error_retry_count=1, sleep=1,
        default_error_text=_t('default_api_error'),
):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            local_error_retry_count = error_retry_count
            for _ in range(local_error_retry_count):
                try:
                    return func(self, *args, **kwargs)
                except ApiError as err:
                    print(err)
                    raise err.__class__(
                        err.error_text,
                        traceback_text=traceback.format_exc(),
                        func_name=func.__name__, func_args=args,
                        func_kwargs=kwargs,
                    )
                except Exception as err:
                    print(err)
                    local_error_retry_count -= 1
                    if local_error_retry_count <= 0:
                        raise ServerError(
                            default_error_text,
                            err_obj=err,
                            traceback_text=traceback.format_exc(),
                            func_name=func.__name__, func_args=args,
                            func_kwargs=kwargs,
                        )
                    time.sleep(sleep)
        return wrapper
    return decorator


class AppServerApi:

    # alarm = get_alarm_bot()

    # prev_r = None

    AUTORIZATION_HEADER = 'Server-Authorization'

    @classmethod
    def create_jwt_token(cls, server, state):
        if not JWT_APP_SERVER_SECRET:
            raise ServerError('need JWT_APP_SERVER_SECRET')

        return jwt.encode(dict(
            iss='sbmobile',
            server=server,
            state=state,
        ), JWT_APP_SERVER_SECRET, algorithm='HS256').decode('utf8')

    @classmethod
    def validateToken(cls, jwt_token):
        try:
            token_data = jwt.decode(
                jwt_token, JWT_APP_SERVER_SECRET,
                options=dict(verify_exp=False)
            )
        except Exception as err:
            raise ApiError(error_text=_t('bad_token'))
        return token_data

    @classmethod
    def validateRequest(cls, request, servers):
        jwt_token = request.headers.get(
            cls.AUTORIZATION_HEADER, ''
        ).strip()

        if not jwt_token:
            raise ApiError(error_text='need header: "{}"'.format(
                cls.AUTORIZATION_HEADER
            ))

        token_data = cls.validateToken(jwt_token)
        if token_data.get('state') != servers.get(token_data.get('server')):
            raise ApiDataError(error_text='wrong token')
        return True
