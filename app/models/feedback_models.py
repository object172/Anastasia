# -*- encoding: utf-8 -*-

import datetime
import json
import os
import traceback
import base64

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy import (
    or_ as sql_or
)
from app_utils.db_utils import IS_ORACLE_DB
from app_utils.db_utils.models import JSONB

from app_models import Client_lk, DeviceData
from app_sbtelecom.api import SbtSmsApi
from app.models.mixins import (
    AppDeclBase, BaseModel,
    jsonb_property
)
from app.texts import _t
from app_utils.email_utils import send_email
from app_utils.os_utils import check_or_create_path
from app_utils.wrappers import memorizing, memorizing_file_descriptior
from utils.crypto_utils import encrypt, decrypt


from settings import DATA_PATH


__all__ = (
    'FeedbackOrder',
)


FEEDBACK_PATH = check_or_create_path(
    os.path.join(DATA_PATH, "feedbacks")
)


class FeedbackOrder(AppDeclBase, BaseModel):
    __tablename__ = "feedbacks_orders"

    DT_FORMAT = '%Y.%m.%dT%H:%M:%S'

    ORDER_STATUS_NEED_SEND = 'need_send'
    ORDER_STATUS_SENDED = 'sended'

    ORDER_STATUS_ERROR = 'error'

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)  # , primary_key=IS_ORACLE_DB)
    token = Column(String)

    order_status = Column(String)

    data = Column(JSONB, default={})
    _sdata = Column(String, default="", name='sdata_' if IS_ORACLE_DB else '_sdata')

    completed = Column(DateTime)
    order_sent = Column(DateTime)

    created = Column(
        DateTime,  # primary_key=IS_ORACLE_DB,
        default=datetime.datetime.utcnow
    )
    updated = Column(DateTime)
    deleted = Column(DateTime)

    _uid = jsonb_property('data', 'uid', None)
    __sdata = None

    @property
    def sdata(self):
        if self.__sdata is None:
            sdata = self._sdata and decrypt(self._sdata) or '{}'
            self.__sdata = json.loads(sdata)
        return self.__sdata

    @sdata.setter
    def sdata(self, sdata):
        self.__sdata = sdata

    @property
    def uid(self):
        if self._uid is None and self.id:
            self._uid = 10 ** 8 + self.id
        return str(self._uid)

    def save(self, *args, **kwargs):
        if self.__sdata is not None:
            sdata = json.dumps(self.__sdata or {})
            self._sdata = encrypt(sdata)
        self.updated = datetime.datetime.utcnow()
        resp = super(FeedbackOrder, self).save(*args, **kwargs)
        if not resp._uid:
            resp._uid = self.uid
            resp = super(FeedbackOrder, self).save(*args, **kwargs)
        return resp

    @staticmethod
    def format_number(number):
        number = number or '7__________'
        msisdn = number if number[0] == '7' else '7' + number
        formated_number = '+{} ({}) {}-{}-{}'.format(
            msisdn[0], msisdn[1:4], msisdn[4:7], msisdn[7:9], msisdn[9:]
        )
        return formated_number

    @property
    def formated_client_id(self):
        return self.format_number(self.client_id)

    @property
    @memorizing
    def base_path(self):
        return check_or_create_path(os.path.join(
            FEEDBACK_PATH,
            unicode(self.created.year),
            unicode(self.created.month),
            unicode(self.created.day),
            unicode(self.uid),
        ))

    os = jsonb_property('data', 'os', '-')
    app_version = jsonb_property('data', 'app_version', '-')

    error = jsonb_property('data', 'error', None)
    order_data = jsonb_property('sdata', 'order_data', {})

    name = jsonb_property('order_data', 'name', '')

    contact_phone = jsonb_property('order_data', 'phone', '')
    sub_phone = jsonb_property('order_data', 'phone2', '')

    @property
    def formated_contact_phone(self):
        return self.format_number(self.contact_phone)

    @property
    def formated_sub_phone(self):
        return self.format_number(self.sub_phone)

    email = jsonb_property('order_data', 'email', '')
    question = jsonb_property('order_data', 'question', '')

    file1_name = jsonb_property('order_data', 'file1Name', '')
    file1_data = jsonb_property('order_data', 'file1Data', None)
    is_file1_exists = property(lambda self: bool(self.file1_data) or None)

    @property
    @memorizing
    def file1_path(self):
        return self.is_file1_exists and check_or_create_path(os.path.join(self.base_path, self.file1_name or 'file1'))

    @property
    def file1_file(self):
        if self.file1_path and not os.path.exists(self.file1_path):
            with open(self.file1_path, 'wb') as fd:
                fd.write(base64.b64decode(self.file1_data))
        return self.file1_path

    file2_name = jsonb_property('order_data', 'file2Name', '')
    file2_data = jsonb_property('order_data', 'file2Data', None)
    is_file2_exists = property(lambda self: bool(self.file2_data) or None)

    @property
    @memorizing
    def file2_path(self):
        return self.is_file2_exists and check_or_create_path(os.path.join(self.base_path, self.file2_name or 'file2'))

    @property
    def file2_file(self):
        if self.file2_path and not os.path.exists(self.file2_path):
            with open(self.file2_path, 'wb') as fd:
                fd.write(base64.b64decode(self.file2_data))
        return self.file2_path

    file3_name = jsonb_property('order_data', 'file3Name', '')
    file3_data = jsonb_property('order_data', 'file3Data', None)
    is_file3_exists = property(lambda self: bool(self.file3_data) or None)

    @property
    @memorizing
    def file3_path(self):
        return self.is_file3_exists and check_or_create_path(os.path.join(self.base_path, self.file3_name or 'file3'))

    @property
    def file3_file(self):
        if self.file3_path and not os.path.exists(self.file3_path):
            with open(self.file3_path, 'wb') as fd:
                fd.write(base64.b64decode(self.file3_data))
        return self.file3_path

    def complete(self, db_session, **kwargs):
        self.completed = datetime.datetime.utcnow()
        self.order_status = self.ORDER_STATUS_NEED_SEND
        self.save(db_session, **kwargs)

        self.send_order(db_session)

    def send_order(self, db_session, recipient_list=None, **kwargs):
        if self.order_status != self.ORDER_STATUS_NEED_SEND:
            return False

        try:
            images_paths = filter(bool, [
                self.file1_file and self.file1_file.encode('utf8'),
                self.file2_file and self.file2_file.encode('utf8'),
                self.file3_file and self.file3_file.encode('utf8'),
            ])

            send_email(
                subject=_t("feedback_email_sbj"),
                message=_t("feedback_email_msg").format(
                    id=self.id,
                    formated_created=(
                        self.created + datetime.timedelta(hours=3)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    formated_contact_phone=self.contact_phone,
                    os=self.os,
                    app_version=self.app_version,
                    name=self.name,
                    email=self.email,
                    formated_sub_phone_text=_t("feedback_email_msg_sub_phone").format(
                        formated_sub_phone=self.sub_phone
                    ) if self.sub_phone else '',
                    question=self.question,
                ),
                recipient_list=recipient_list or [
                    'pogovorim@sb-tele.com',
                    # 'support@sbt-tele.com',
                    # 'sb-telecom.drtariff@bk.ru',
                ],
                images_paths=images_paths or [],
                add_tail=False, is_html=True,
            )
        except Exception as err:
            print(
                'Feedback.send_order.err', err,
                self.id, self.order_type, traceback.format_exc()
            )
            try:
                self.alarm.error(u' '.join([
                    'Feedback.send_order.err', unicode(err),
                    unicode(self.id), self.order_type
                ]))
            except Exception as err1:
                print(
                    'Feedback.send_order.err', err1,
                    self.id, self.order_type, traceback.print_exc()
                )
        else:
            self.order_sent = datetime.datetime.utcnow()
            self.order_status = self.ORDER_STATUS_SENDED
        self.save(db_session, **kwargs)
        return True
