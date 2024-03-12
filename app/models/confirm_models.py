# -*- encoding: utf-8 -*-

import datetime
import json
import random
import string
import traceback

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy import (
    or_ as sql_or
)
from app_utils.db_utils import IS_ORACLE_DB
from app_utils.db_utils.models import JSONB

from app_sbtelecom.api import SbtSmsApi
from app.models.mixins import (
    AppDeclBase, BaseModel, jsonb_property
)
from app.texts import _t
from app_utils.wrappers import memorizing
from methods_simple import get_reg_op
from utils.crypto_utils import encrypt, decrypt


__all__ = (
    'Confirm',
)


class Confirm(AppDeclBase, BaseModel):
    __tablename__ = "confirms"

    READ_COUNT = 5

    id = Column(Integer, primary_key=True)

    client_id = Column(String)
    confirm_item = Column(String)
    confirm_item_id = Column(Integer)

    data = Column(JSONB, default={})
    _sdata = Column(String, default="", name='sdata_' if IS_ORACLE_DB else '_sdata')

    read_count = jsonb_property('data', 'read_count', 0)

    created = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)

    __sdata = None
    contact_phone = jsonb_property('data', 'contact_phone', None)

    @property
    def sdata(self):
        if self.__sdata is None:
            sdata = self._sdata and decrypt(self._sdata) or '{}'
            self.__sdata = json.loads(sdata)
        return self.__sdata

    @sdata.setter
    def sdata(self, sdata):
        self.__sdata = sdata

    def save(self, *args, **kwargs):
        if self.__sdata is not None:
            sdata = json.dumps(self.__sdata or {})
            self._sdata = encrypt(sdata)
        super(Confirm, self).save(*args, **kwargs)

    @staticmethod
    def format_number(number):
        number = number or '7__________'
        msisdn = number if number[0] == '7' else '7' + number
        formated_number = '+{} ({}) {}-{}-{}'.format(
            msisdn[0], msisdn[1:4], msisdn[4:7], msisdn[7:9], msisdn[9:]
        )
        return formated_number

    @property
    def formated_contact_phone(self):
        return self.format_number(self.contact_phone)

    secret_code = jsonb_property('sdata', 'secret_code', None)
    code_value = jsonb_property('sdata', 'code_value', None)

    secret_code_sent = jsonb_property('data', 'sent', None)
    code_value_received = jsonb_property('data', 'received', None)
    error = jsonb_property('data', 'error', None)
    log = jsonb_property('data', 'log', None)

    def send_secret_code(
            self, db_session,
            sms_text=_t("confirm_sent_sms_code_text"),
            code_length=4,
            **kwargs
    ):
        self.secret_code_sent = datetime.datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%S:%f"
        )

        self.secret_code = self._generate_secret_code(length=code_length)
        self.save(db_session, **kwargs)

        try:
            _, operator = get_reg_op(self.contact_phone, db_session)
            status, log_txt = SbtSmsApi(self.contact_phone, operator).send(
                sms_text.format(self.secret_code)
            )
        except Exception as err:
            status = False
            log_txt = u'Can\'t send confirm SMS: {}\n{}'.format(err, traceback.format_exc())
            try:
                print(log_txt)
                self.alarm.alarm(log_txt)
            except:
                pass

        if status:
            try:
                self.log = log_txt
                self.save(db_session, **kwargs)
            except:
                pass

            return True, _t('confirm_sent_sms_code').format(
                self.formated_contact_phone
            )

        try:
            self.error = log_txt
            self.save(db_session, **kwargs)
        except:
            pass

        try:
            self.alarm.error(
                u'Confirm(id={}).send_secret_code error: {}'.format(
                    self.id, log_txt
                )
            )
        except:
            pass

        return False, _t('confirm_sent_sms_code_try_later').format(
            self.formated_contact_phone
        )

    @staticmethod
    def _generate_secret_code(length=4):
        chars = string.digits
        secret_code_items = [
            random.SystemRandom().choice(chars)
            for _ in xrange(length)
        ]

        random.SystemRandom().shuffle(secret_code_items)
        secret_code = ''.join(secret_code_items)
        return secret_code

    @classmethod
    def get(
            cls, db_session,
            confirm_id=None, confirm_item=None, confirm_item_id=None,
            secret_code=None, delete_confirmation=True,
    ):
        if (not confirm_id and not confirm_item_id):
            return None

        confirm = db_session.query(Confirm)
        if confirm_id:
            confirm = confirm.filter(Confirm.id == confirm_id)

        if confirm_item_id:
            confirm = confirm.filter(Confirm.confirm_item_id == confirm_item_id)

        confirm = confirm.filter(
            Confirm.confirm_item == confirm_item,
            Confirm.deleted == None
        ).order_by(Confirm.created.desc()).first()

        if confirm is None:
            return None

        confirm.read_count += 1
        confirm.save(db_session)

        if not secret_code:
            return confirm

        confirm.code_value = secret_code.strip()
        confirm.code_value_received = datetime.datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%S:%f"
        )
        if delete_confirmation:
            confirm.deleted = datetime.datetime.utcnow()
        confirm.save(db_session)

        if confirm.secret_code != confirm.code_value:
            return None

        return confirm
