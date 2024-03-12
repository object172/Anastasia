# -*- encoding: utf-8 -*-
from wtforms import Form, Field, validators

from app.exceptions import ApiError, ApiDataError
from app.texts import _t


__all__ = (
    'AbsApiForm', 'AbsModelForm',
    
    'validator_data_required',
    
    'ValidatorChoice',
    'ValidatorDateTime',
    'ValidatorInteger',
    
    'FieldRequired',
    'FieldOptional',
    'FieldInteger',
)


class AbsApiForm(Form):
    ExceptionClass = ApiError


class AbsModelForm(Form):
    ExceptionClass = ApiDataError


validator_data_required = validators.DataRequired(
    message=_t('required_field'),
)


def ValidatorChoice(choices, message=None):
    message = message or _t('wrong_value')
    def validator(form, field):
        if (field.data and field.data.strip()) not in choices:
            raise validators.ValidationError(message)
    return validator


def ValidatorDateTime(dt_format, message=None):
    message = message or _t('wrong_value')
    def validator(form, field):
        try:
            datetime.datetime.strptime(field.data.strip(), dt_format)
        except:
            raise validators.ValidationError(message)
    return validator


def ValidatorInteger(message=None):
    message = message or _t('wrong_value')
    def validator(form, field):
        try:
            int(field.data.strip(), dt_format)
        except:
            raise validators.ValidationError(message)
    return validator


def FieldRequired(*extra_validators, **kwargs):
    return Field(validators=[
        validators.DataRequired(message=(
            kwargs.get('message') or _t('required_field')
        ))
    ] + list(extra_validators))


def FieldOptional(*extra_validators, **kwargs):
    return Field(validators=[validators.Optional()] + list(extra_validators))


def FieldInteger(*extra_validators, **kwargs):
    return Field(validators=[
        ValidatorInteger(
            message=(kwargs.get('message') or _t('wrong_value')))
    ] + list(extra_validators))
