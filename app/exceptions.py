# -*- encoding: utf-8 -*-

import json

from app.texts import _t


__all__ = (
    'AppError', 'AuthError',
    'ApiError', 'ApiDataError',
    'ServerError', 'ServerDataError',
)


class AppError(Exception):
    ERROR = 'server_error'

    response_data = {
        'result': 0,
        'error_text': _t('something_wrong'),
    }

    def __init__(self, error=None, **response_data):
        error_text = (
            response_data.get('error_text') or
            self.response_data.get('error_text', _t('something_wrong'))
        )

        self.response_data = self.response_data or {}
        self.response_data.update(response_data)
        self.response_data['exception'] = error or self.ERROR
        self.response_data['error'] = self.error
        self.response_data['error_text'] = error_text

        super(AppError, self).__init__(
            self.response_data['error']
        )

    @property
    def error_text(self):
        return self.response_data.get('error_text', _t('something_wrong'))

    @property
    def error(self):
        return self.error_text

    def __str__(self):
        try:
            return json.dumps(self.response_data, ensure_ascii=False, indent=2)
        except:
            return str(self.response_data)


class AuthError(AppError):
    ERROR = 'auth_error'

    response_data = {
        'error': ERROR,
        'error_text': _t('auth_error'),
        'result': 0,
    }

    @property
    def error(self):
        return self.ERROR


class ApiError(AppError):
    ERROR = 'api_error'


class ApiDataError(ApiError):
    ERROR = 'not_valid_input'


class ServerError(AppError):
    ERROR = 'server_error'


class ServerDataError(ServerError):
    ERROR = 'server_data_error'
