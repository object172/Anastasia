# -*- encoding: utf-8 -*-
from __future__ import print_function

from functools import wraps

from app.exceptions import (AuthError, ApiError, )
from app.texts import _t


__all__ = (
    'client_token_required',
    'sbt_client_required',
    'validate',
)


def client_token_required():
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if not self.is_auth:
                raise AuthError()
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


def sbt_client_required(func):
    def decorator(self, *args, **kwargs):
        if not self.client.has_sbtelecom_operator:
            raise ApiError(error_text=self._t('only_for_sbt'))
        return func(self, *args, **kwargs)
    return decorator


def validate(*forms):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for FormClass in forms:
                form = FormClass(data=self.data)
                form.validate()

                if form.errors:
                    errors_info = form.errors.copy()

                    for field, errors in errors_info.items():
                        errors = list(set(errors))
                        errors_info[field] = errors

                    raise FormClass.ExceptionClass(
                        error_text=_t('wrong_input'),
                        errors_info=errors_info,
                    )

            return func(self, *args, **kwargs)
        return wrapper
    return decorator
