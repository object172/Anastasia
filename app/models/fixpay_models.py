# -*- encoding: utf-8 -*-

import base64
import datetime
import io
import json
import os
import random
import string
import tempfile
import traceback

import PyPDF2 as pypdf
from app.models.mixins import (AppDeclBase, BaseModel, GeneratePdfMixin,
                               jsonb_property)
from app.texts import _t
from app_models import Client_lk, DeviceData
from app_sbtelecom.api import sbTelecomApi, SbtSmsApi
from app_utils.db_utils import IS_ORACLE_DB
from app_utils.db_utils.models import JSONB
from app_utils.email_utils import send_email
from app_utils.os_utils import check_or_create_path
from app_utils.wrappers import memorizing, memorizing_file_descriptior
from methods_simple import get_reg_op
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph
from settings import DATA_PATH
from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy import or_ as sql_or
from utils.crypto_utils import decrypt, encrypt

FIXPAY_PATH = check_or_create_path(
    os.path.join(DATA_PATH, "contracts", "fixpay")
)


__all__ = (
    'FixPayOrder',
)


class FixPayOrder(AppDeclBase, BaseModel, GeneratePdfMixin):
    __tablename__ = "fix_pay_orders"

    ORDER_TYPE_MOVE = 'move'
    ORDER_TYPE_REFUND = 'refund'

    id = Column(Integer, primary_key=True)
    client_id = Column(String, index=True)

    order_type = Column(String)

    data = Column(JSONB, default={})
    _sdata = Column(String, default="", name='sdata_' if IS_ORACLE_DB else '_sdata')

    created = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)

    completed = Column(DateTime)

    secret_code_sent = Column(DateTime)
    last_order_sent = Column(DateTime)
    order_sent = Column(DateTime)

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
        return self._uid

    def save(self, *args, **kwargs):
        if self.__sdata is not None:
            sdata = json.dumps(self.__sdata or {})
            self._sdata = encrypt(sdata)
        resp = super(FixPayOrder, self).save(*args, **kwargs)
        if not self._uid:
            self._uid = self.uid
            resp = super(FixPayOrder, self).save(*args, **kwargs)
        return resp

    @property
    def sign_date(self):
        return self.completed + datetime.timedelta(hours=3)

    @property
    @memorizing
    def base_path(self):
        return check_or_create_path(os.path.join(
            FIXPAY_PATH,
            unicode(self.created.year),
            unicode(self.created.month),
            unicode(self.created.day),
            unicode(self.uid),
        ))

    @staticmethod
    def format_number(number):
        number = number or '7__________'
        msisdn = number if number[0] == '7' else '7' + number
        formated_number = '+{} ({}) {}-{}-{}'.format(
            msisdn[0], msisdn[1:4], msisdn[4:7], msisdn[7:9], msisdn[9:]
        )
        return formated_number

    error = jsonb_property('data', 'error', None)

    client_operator = jsonb_property('data', 'client_operator', None)
    client_region = jsonb_property('data', 'client_region', None)

    number = jsonb_property('data', 'number', None)

    @property
    def src_number(self):
        return self.number

    @property
    def formated_src_number(self):
        return self.format_number(self.src_number)

    operator = jsonb_property('data', 'operator', None)

    @property
    def src_number_operator(self):
        return self.operator

    region = jsonb_property('data', 'region', None)
    region_dt_id = jsonb_property('data', 'region', None)

    contact_phone = jsonb_property('data', 'contact_phone', None)
    contact_email = jsonb_property('data', 'contact_email', '')

    @property
    def formated_contact_phone(self):
        return self.format_number(self.contact_phone)

    signature = jsonb_property('sdata', 'signature', None)
    @property
    @memorizing_file_descriptior
    def signature_img(self):
        return Image.open(io.BytesIO(
            base64.b64decode(self.signature)
        ))

    order_data = jsonb_property('sdata', 'order_data', {})

    @property
    @memorizing
    def client_fio(self):
        if self.order_data.get('client_fio') is None:
            try:
                sbt_api = sbTelecomApi(
                    number=self.client_id,
                    region_dt_id=self.region_dt_id,
                )
                r = sbt_api.getClientParams()
                self.order_data["client_fio"] = r.json['getClntSubsResponseParams']['client']['personalProfileData']['fullName']
            except:
                pass
        return self.order_data.get('client_fio', '').title()

    @property
    @memorizing
    def fio(self):
        if self.order_data.get("fio") is None:
            return self.client_fio
        return self.order_data.get("fio", '').title()

    dst_number = jsonb_property('order_data', 'number', None)
    dst_number_operator = jsonb_property('order_data', 'operator', None)
    dst_number_region = jsonb_property('order_data', 'region', None)

    @property
    def formated_dst_number(self):
        return self.format_number(self.dst_number)

    is_partial = jsonb_property('order_data', 'partial_ok', None)
    photo = jsonb_property('order_data', 'photo', None)

    @property
    @memorizing
    def photo_path(self):
        return check_or_create_path(os.path.join(
            self.base_path, u'check.png'
        ))

    @property
    @memorizing_file_descriptior
    def photo_img(self):
        return Image.open(io.BytesIO(
            base64.b64decode(self.photo)
        ))

    @property
    def photo_file(self):
        if (
                not os.path.exists(self.photo_path) or
                os.path.getsize(self.photo_path) == 0
        ):
            self.photo_img.save(self.photo_path)
            self.photo_img.close()
        return self.photo_path

    card_data = jsonb_property('sdata', 'card_data', {})
    card_number = jsonb_property('card_data', 'card_number', None)

    @property
    def formated_card_number(self):
        if not self.card_number:
            return ""
        return u"*" * 12 + unicode(self.card_number)[12:]

    @property
    def formated_client_id(self):
        return self.format_number(self.client_id)

    secret_code = jsonb_property('sdata', 'secret_code', None)

    def send_secret_code(self, db_session, **kwargs):
        self.secret_code_sent = datetime.datetime.utcnow()

        self.secret_code = self._generate_secret_code()
        self.save(db_session, **kwargs)

        try:
            _, operator = get_reg_op(self.contact_phone, db_session)
            status, error_reason = SbtSmsApi(self.contact_phone, operator).send(
                _t("fixpay_sent_sms_code_text").format(self.secret_code)
            )
        except Exception as err:
            status = False
            error_reason = u'Can\'t send confirm SMS: {}'.format(err)
            try:
                print(error_reason)
                self.alarm.alarm(error_reason)
            except:
                pass

        if status:
            return True, _t('fixpay_sent_sms_code').format(
                self.formated_contact_phone
            )

        try:
            self.error = error_reason
            self.save(db_session, **kwargs)
        except:
            pass

        try:
            self.alarm.error(
                u'FixPayOrder(id={}).send_secret_code error: {}'.format(
                    self.id, error_reason
                )
            )
        except:
            pass

        return False, _t('fixpay_sent_sms_code_try_later').format(
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

    def complete(self, db_session, **kwargs):
        self.completed = datetime.datetime.utcnow()
        self.save(db_session, **kwargs)

        # self.send_order(db_session, **kwargs)

    ORDER_TYPE_EMAIL_TEMPLATES = {
        'move': u'''<div>Добрый день.</div>
<br>
<div>Запрошен перенос платежа.</div>
<div>Абонент {is_partial_word}согласен на перенос части платежа</div>
<br>
<div>Id заказза: <b>{id}</b></div>
<div>Дата: <b>{formated_created}</b> (по мск)</div>
<div>Контактный телефон: <b>{formated_contact_phone}</b></div>
<div>E-mail: <b>{email}</b></div>
<div>Номер телефона, на который перевели деньги по ошибке: <b>{formated_src_number}</b> (оператор: <b>{formated_src_number_operator}</b>)</div>
<div>Перевести ошибочный платеж на новый номер: <b>{formated_dst_number}</b> (оператор: <b>{formated_dst_number_operator}</b>)</div>
<br>
<br>
<div><b>С уважением,<br>ООО «Сбербанк-Телеком»</b></div>
''',
        'refund': u'''<div>Добрый день.</div>
<br>
<div>Запрошен возврат средств.</div>
<div>Абонент {is_partial_word}согласен на возврат части платежа</div>
<br>
<div>Id заказза: <b>{id}</b></div>
<div>Дата: <b>{formated_created}</b> (по мск)</div>
<div>Контактный телефон: <b>{formated_contact_phone}</b></div>
<div>E-mail: <b>{email}</b></div>
<br>
<div>Информация об ошибочном платеже:</div>
<div>ФИО: <b>{fio}</b></div>
<div>Дата платежа: <b>{date}</b></div>
<div>Сумма платежа: <b>{amount}</b> руб</div>
<br>
<div>Данные банковской карты для возврата платежа</div>
<div>Фамилия Имя владельца: <b>{card_holder}</b></div>
<div>Номер карты: <b>{formated_card_number}</b></div>
<div>БИК банка: <b>{card_bik}</b></div>
<div>Расчетный счет получателя: <b>{card_account}</b></div>
<br>
<br>
<div><b>С уважением,<br>ООО «Сбербанк-Телеком»</b></div>
'''
    }

    OPERATORS = {
        'beeline': u'Билайн',
        'megafon': u'Мегафон',
        'mts': u'МТС',
        'yota': u'YOTA',
        'city': u'неизвестен',
        'sbt': u'ООО «Сбербанк-Телеком»',
        'com:unity': u'ООО «Сбербанк-Телеком»',
    }

    def send_order(self, db_session, recipient_list=None, **kwargs):
        if (
                not self.completed or
                self.order_sent
        ):
            return False

        self.last_order_try_sent = datetime.datetime.utcnow()

        template_data = {
            "id": self.id,
            "formated_created": (
                self.created + datetime.timedelta(hours=3)
            ).strftime("%Y-%m-%d %H:%M:%S"),
            "formated_contact_phone": self.format_number(self.contact_phone),
            "email": self.contact_email or '-',
            "is_partial_word": "" if self.is_partial else u"не "
        }

        if self.order_type == self.ORDER_TYPE_MOVE:
            template_data.update({
                "formated_src_number": self.formated_src_number,
                "formated_src_number_operator": self.OPERATORS.get(
                    self.src_number_operator, self.OPERATORS['city']
                ),
                "formated_dst_number": self.formated_dst_number,
                "formated_dst_number_operator": self.OPERATORS.get(
                    self.dst_number_operator, self.OPERATORS['city']
                ),
            })
        elif self.order_type == self.ORDER_TYPE_REFUND:
            template_data.update({
                "fio": self.order_data.get("fio", "???"),
                "date": self.order_data.get("date", "???"),
                "amount": self.order_data.get("amount", "???"),
                "formated_card_number": self.formated_card_number,
            })
            template_data.update(self.card_data)

            # t_png = tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False)


            #     with open(t_pdf.name, 'wb') as pdf_fd:
            #         pdf_writer.write(pdf_fd)

            #     with open(t_pdf.name, 'rb') as pdf_fd:
            #         pdf_data = pdf_fd.read()
        if self.client_id in ['9581234567', '9581111111']:
            recipient_list = ['sb-telecom.qstudio@bk.ru', 'akar@qstudio.org']
        try:
            send_email(
                subject=u'Заявка на корректировку платежа',
                message=self.ORDER_TYPE_EMAIL_TEMPLATES[self.order_type].format(
                    **template_data
                ),
                recipient_list=recipient_list or [
                    'pogovorim@sb-tele.com',
                    # 'support@sbt-tele.com',
                    # 'sb-telecom.qstudio@bk.ru',
                ],
                images_paths=[self.photo_file, ],
                files_paths=[self.order_pdf, ],
                add_tail=False, is_html=True,
            )
        except Exception as err:
            print(
                'FixPayOrder.send_order.err', err,
                self.id, self.order_type
            )
            traceback.print_exc()
            try:
                self.alarm.error(u' '.join([
                    'FixPayOrder.send_order.err', unicode(err),
                    unicode(self.id), self.order_type
                ]))
            except Exception as err1:
                print(
                    'FixPayOrder.send_order.err', err1,
                    self.id, self.order_type
                )
                traceback.print_exc()
        else:
            self.order_sent = datetime.datetime.utcnow()
        self.save(db_session, **kwargs)
        return True

    @property
    @memorizing
    def order_path(self):
        return check_or_create_path(os.path.join(
            self.base_path,
            u'edit payment contract {uid} {sign_dt}.pdf'.format(
                uid=self.uid, sign_dt=self.sign_date.strftime('%d.%m.%Y')
            )
        ))

    @property
    def order_pdf(self):
        # if os.path.exists(self.order_path):
        #     return self.order_path

        now = datetime.datetime.now()

        packet = io.BytesIO()

        styles = getSampleStyleSheet()
        styleBH = styles["Normal"]

        can = Canvas(packet, pagesize=A4)
        can.translate(self.MARGIN_LEFT_RIGHT, self.MARGIN_TOP_BOTTOM)

        current_x = 0
        current_y = self.WRAPPED_HEIGHT + 20

        _, current_y = self.draw_string(can, 6, current_y, u'В ООО Сбербанк-Телеком от', 'Arial', 10, text_align='right')
        _, current_y = self.draw_string(can, 6, current_y, self.client_fio or "Абонента {}".format(
            self.formated_client_id
        ), 'ArialBold', 10, text_align='right')

        current_x, _ = self.draw_string(can, 6, current_y, self.formated_contact_phone, 'ArialBold', 10, text_align='right')
        _, current_y = self.draw_string(can, 6, current_y, 'Контактный номер: ', 'Arial', 10, text_align='right', max_x=current_x)
        current_x, _ = self.draw_string(can, 6, current_y, self.contact_email or '-', 'ArialBold', 10, text_align='right')
        _, current_y = self.draw_string(can, 6, current_y, 'E-mail: ', 'Arial', 10, text_align='right', max_x=current_x)

        current_x, _ = self.draw_string(can, 6, current_y, self.formated_client_id, 'ArialBold', 10, text_align='right')
        _, current_y = self.draw_string(can, 6, current_y, 'Номер Сбербанк-Телеком: ', 'Arial', 10, text_align='right', max_x=current_x)

        current_y -= 30

        _, current_y = self.draw_string(can, 6, current_y, 'Заявление о корректировке платежа', 'ArialBold', 12, text_align='center')

        current_y -= 20

        current_x, _ = self.draw_string(can, 6, current_y, 'Абонент', 'Arial', 10)
        current_x, _ = self.draw_string(can, current_x + 6, current_y, self.client_fio or self.formated_client_id, 'ArialBold', 10)
        current_x, current_y = self.draw_string(
            can, current_x, current_y,
            ', настоящим заявлением выражает желание скорректировать платеж',
            'Arial', 10, new_line_offset_x=6
        )

        current_y -= 20

        if self.client_fio != self.fio:
            current_x, _ = self.draw_string(can, 6, current_y, u'Плательщик:', 'ArialBold', 10, )
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.fio, 'Arial', 10)
            current_y -= 20

        current_x, _ = self.draw_string(can, 6, current_y, u'Причина корректировки:', 'Arial', 10,)
        if self.order_type == self.ORDER_TYPE_MOVE:
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, u"Ошибка в номере телефона", 'ArialBold', 10)
        elif self.order_type == self.ORDER_TYPE_REFUND:
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, u"Ошибка в сумме пополнения", 'ArialBold', 10)

        if self.order_type == self.ORDER_TYPE_MOVE:
            current_x, _ = self.draw_string(can, 6, current_y, u'Номер телефона, на который перевели деньги по ошибке:', 'Arial', 10,)
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.formated_src_number, 'ArialBold', 10)
            current_x, _ = self.draw_string(can, 6, current_y, u'Ошибочный номер:', 'Arial', 10,)
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.formated_dst_number, 'ArialBold', 10)
        elif self.order_type == self.ORDER_TYPE_REFUND:
            current_x, _ = self.draw_string(can, 6, current_y, u'Дата платежа:', 'Arial', 10,)
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.order_data["date"], 'ArialBold', 10)
            current_x, _ = self.draw_string(can, 6, current_y, u'Сумма платежа:', 'Arial', 10,)
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, u"{} руб".format(self.order_data["amount"]), 'ArialBold', 10)

            current_y -= 20

            _, current_y = self.draw_string(can, 6, current_y, 'Данные банковской карты для возврата платежа', 'ArialBold', 12)
            block_y = current_y

            current_x, _ = self.draw_string(can, 6, current_y, u'Фамилия Имя владельца:', 'Arial', 9)
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.card_data["card_holder"], 'ArialBold', 9, max_x=self.WRAPPED_HALF_WIDTH - 10, new_line_offset_x=6)

            current_x, _ = self.draw_string(can, 6, current_y, u'Номер карты:', 'Arial', 9)
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.formated_card_number, 'ArialBold', 9, max_x=self.WRAPPED_HALF_WIDTH - 10, new_line_offset_x=6)

            # current_x, _ = self.draw_string(can, 6, current_y, u'Наименование банка:', 'Arial', 9)
            # current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.card_data["card_issuer"], 'ArialBold', 9, max_x=self.WRAPPED_HALF_WIDTH - 10, new_line_offset_x=6)

            left_y = current_y

            current_y = block_y

            current_x, _ = self.draw_string(can, self.WRAPPED_HALF_WIDTH + 6, current_y, u'БИК банка:', 'Arial', 9)
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.card_data["card_bik"], 'ArialBold', 9, new_line_offset_x=self.WRAPPED_HALF_WIDTH + 6)
            current_x, _ = self.draw_string(can, self.WRAPPED_HALF_WIDTH + 6, current_y, u'Расчетный счет получателя:', 'Arial', 9)
            current_x, current_y = self.draw_string(can, current_x + 6, current_y, self.card_data["card_account"], 'ArialBold', 9, new_line_offset_x=self.WRAPPED_HALF_WIDTH + 6)

            right_y = current_y

            current_y = min(left_y, right_y)

        current_y -= 20

        text = u'Если денежных средств на ошибочном номере недостаточно для полного возврата {}согласен(-на) на частичный возврат.'.format(
            u"" if self.is_partial else u"не "
        )

        current_x, current_y = self.draw_string(can, 6, current_y, text, 'Arial', 10, new_line_offset_x=6)

        current_y -= 20

        current_x, current_y = self.draw_string(can, 6, current_y, u'C условиями предоставления ознакомлен и согласен.', 'Arial', 10, new_line_offset_x=6)

        current_y -= 30

        sign_x = self.WRAPPED_WIDTH - 200

        _, _ = self.draw_string(can, 6, current_y, u'Абонент', 'Arial', 10, new_line_offset_x=6, max_x=100)
        _, _ = self.draw_string(can, 100, current_y, self.client_fio or self.formated_client_id, 'ArialBold', 10, new_line_offset_x=100, max_x=sign_x)

        if self.signature:
            current_x, current_y = self.draw_signature(can, sign_x, current_y - 15, self.signature_img, max_height=40)
        else:
            current_y -= 40

        current_y -= 20

        current_x, _ = self.draw_string(can, 6, current_y, self.sign_date.strftime('%d.%m.%Y'), 'ArialBold', 10, text_align='right')

        can.showPage()
        can.save()

        if self.signature:
            self.signature_img.close()

        packet.seek(0)
        temp_pdf = pypdf.PdfFileReader(packet)

        order_pdf = pypdf.PdfFileWriter()
        for page_index in range(0, temp_pdf.getNumPages()):
            order_pdf.addPage(temp_pdf.getPage(page_index))

        with open(self.order_path, 'wb') as order_pdf_fd:
            order_pdf.write(order_pdf_fd)

        return self.order_path
