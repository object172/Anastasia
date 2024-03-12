# -*- encoding: utf-8 -*-

import datetime

from wtforms import StringField, validators

from app.forms.base_forms import AbsApiForm, AbsModelForm
from app.texts import _t


__all__ = (
    'ContactApiForm',
)


class ContactApiForm(AbsApiForm):
    last_datetime = StringField('last_datetime', [
        validators.Optional(),
    ])

    def validate_last_datetime(form, field):
        if not field.data:
            return

        try:
            datetime.datetime.strptime(field.data, '%Y-%m-%dT%H:%M:%S')
        except:
            raise validators.ValidationError(message=_t('wrong_format'))
