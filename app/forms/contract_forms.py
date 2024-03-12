# -*- encoding: utf-8 -*-

from wtforms import StringField, PasswordField, validators

from app.forms.base_forms import AbsApiForm, AbsModelForm
from app.texts import _t


__all__ = (
    'SendContractToEmailModelForm',
)


class SendContractToEmailModelForm(AbsModelForm):
    email = StringField('email', [
        validators.DataRequired(message=_t('email_required')),
        validators.Email(message=_t('email_not_valid'))
    ])
