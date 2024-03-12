# -*- encoding: utf-8 -*-

import datetime
import uuid

import settings
from app.api import PdServerApi
from app.exceptions import ApiError
from app.handlers import BaseHandler, RedirectHandler
from app.models import Confirm, SubscriberContractOrder
from app.services import create_mnp_token, get_subscriber_contract_data
from app.texts import _t
from app.wrappers import client_token_required, sbt_client_required, validate
from app_models import Client, ClientToken, DeviceData, Port
from app_regions.services import normalize_region_dt_id
from app_sbtelecom.api import sbTelecomApi
from app_utils.wrappers import memorizing
from methods_simple import get_reg_op

__all__ = (
    'MnpRequestInfoHandler',
    'MnpRequestDetailsHandler',
    'MnpRequestConfirmationHandler',
    'MnpRequestSignHandler',
    'MnpRequestConfirmHandler',
    'MnpRequestHandler',
    'MnpRequestDataHandler',
    'MnpRequestCreateHandler',
)


AVAILABLE_MNP_REGIONS = [31, 64]


class GetContractDataMixin:

    def _get_contract_data(self, sco=None):
        if sco:
            if sco.client_id in settings.TEST_SBT_USERS:
                contract_data = self._get_test_contract_data()
            else:
                contract_data = self._get_sbt_contract_data(sco)
        else:
            if self.client_id in settings.TEST_SBT_USERS:
                contract_data = self._get_test_contract_data()
            else:
                contract_data = self._get_sbt_contract_data(sco)
        return contract_data

    def _get_sbt_contract_data(self, sco=None):
        if (
                sco is None or
                self.client.client_id == sco.client_id
        ):
            client = self.client
        else:
            client = self.db_session.query(Client).filter_by(
                client_id=sco.client_id
            ).first()

        contract_data = get_subscriber_contract_data(client)
        if contract_data.get('birthdate'):
            contract_data['birthdate'] = contract_data['birthdate'].strftime('%d.%m.%Y')
        if contract_data.get('issued'):
            contract_data['issued'] = contract_data['issued'].strftime('%d.%m.%Y')
        return contract_data

    def _get_test_contract_data(self):
        return {
            "fio": u"Тест Тест",
            "sex": u"Муж",
            "birthdate": u"12.12.2000",
            "citizenship": u"РФ",
            "doctype": u"Паспорт РФ",
            "serial": u"1234",
            "docid": u"123456",
            "ufmscode": u"123-456",
            "issuer": u"Тест",
            "issued": u"21.12.2018",
            "address": u"Тест",
        }


TEST_MNP_NUMBERS = ['9038425244']


class MnpRequestInfoHandler(BaseHandler, GetContractDataMixin):
    u'''
    ->{
        token: "asd",
        number: "958124567",
        iccid: "1234567890...",
        mnp_date: "22.03.2078",
        mnp_time: "...",

        mnp_request_id: 123 | null,  // null для старых API (до 01.10.2019)
        temp_number: “958124567” | null,  // null для старых API (до 01.10.2019)
    }
    <-{
        mnp_request_id: 123
    }
    '''

    @client_token_required()
    def _post(self, *args, **kwargs):
        print('MnpRequestInfoHandler:')
        reg, op = get_reg_op(self.data['number'], self.db_session, force=True)
        print(self.data['number'], reg, op)
        if op == 'tele2':
            try:
                dates = PdServerApi.getMnpDates(self.region, self.data['mnp_date']).get('dates')
                if self.data['mnp_date'] not in dates:
                    answer = 'Выберите пожалуйста другую дату'
                    if dates:
                        answer += ', ближайшая доступная {}'.format(dates[0])
                    return {"error": answer}
            except Exception as error:
                print('cant get data from PdServerApi.getMnpDates({}, {}): {}'.format(
                    self.region,
                    self.data['mnp_date'],
                    error,
                ))
                return {"error": 'Ошибка проверки даты у учетом лимитов, попробуйте еще раз'}

        if self.data.get('mnp_request_id'):
            sco = self.db_session.query(
                SubscriberContractOrder
            ).filter(
                SubscriberContractOrder.id == self.data['mnp_request_id']
            ).first()
            if sco is None:
                return {"error": self._t("subs_contract_not_found")}
        else:
            sco = SubscriberContractOrder(
                client_id=self.client_id,
                order_type=SubscriberContractOrder.ORDER_TYPE_MNP,
            )
            sco.src = settings.SERVER_NAME

        if self.data.get('temp_number'):
            is_temp_number_from_current_device = self.db_session.query(
                DeviceData.id
            ).join(
                ClientToken, ClientToken.token == DeviceData.token
            ).filter(
                DeviceData.device_id == self.device.device_id,
                DeviceData.client_id == self.data['temp_number'],
                ClientToken.deleted == None,
            ).first()

            if not is_temp_number_from_current_device:
                return {"error": self._t("mnp_sbt_required")}

            sco.client_id = self.data['temp_number']

        if not sco.client_id:
            return {"error": self._t("mnp_sbt_required")}

        temp_sbt_region, temp_sbt_operator = get_reg_op(
            sco.client_id, self.db_session,
            force=True
        )

        if temp_sbt_operator != "sbt":
            return {"error": self._t("mnp_sbt_required")}

        mnp_region, mnp_operator = get_reg_op(
            self.data['number'], self.db_session,
            force=True
        )
        if (
                normalize_region_dt_id(mnp_region) != normalize_region_dt_id(temp_sbt_region)
                and sco.client_id not in settings.TEST_SBT_USERS
                and self.data['number'] not in TEST_MNP_NUMBERS
        ):
            return {"result": 0, "error": self._t('mnp_diff_regs')}

        if mnp_operator == temp_sbt_operator:
            return {"result": 0, "error": self._t('mnp_equal_operators')}

        if sco.client_id in settings.TEST_SBT_USERS:
            self.data['iccid'] = '0' * 20
        else:

            self.data['iccid'] = sbTelecomApi(
                number=sco.client_id,
                db_session=self.db_session
            ).iccid

        last_mnp = self.db_session.query(Port).filter_by(
            number=self.data['number']
        ).order_by(Port.port_date.desc()).first()

        if last_mnp and (
            (
                datetime.datetime.utcnow() +
                datetime.timedelta(hours=3)
            ) - last_mnp.port_date
        ).days < 60:
            return {"result": 0, "error": self._t('mnp_60days')}

        sco.order_data = self.data.copy()
        if sco.client_id in settings.TEST_SBT_USERS:
            sco.is_test = True

        contract_data = self._get_contract_data(sco)

        try:
            if contract_data.get('doctype') in [None, '', u'Иной документ']:
                return {"result": 0, "error": 'В биллинге нет данных о документе абонента'}
        except:
            pass

        sco.order_data.update(contract_data)

        sco.save(self.db_session)
        response = {
            "mnp_request_id": sco.id
        }

        if sco.mnp_app_api_version == sco.MNP_APP_API_V2:
            response.update({
                "details": contract_data
            })
        return response


class MnpMixin:

    @property
    @memorizing
    def sco(self):
        return self.db_session.query(
            SubscriberContractOrder
        ).filter_by(
            id=self.data['mnp_request_id'],
            # client_id=self.client_id,
            deleted=None
        ).first()


class MnpRequestDetailsHandler(BaseHandler, MnpMixin):
    u'''
    ->{
        token: "asd",
        mnp_request_id: 123
        fio: "Суй Во Чай",
        sex: "Муж"/"Жен",
        birthdate: "12.12.2000",
        citizenship: "РФ",
        doctype: "Паспорт РФ",
        serial: null | "1234",
        docid: "12345678",
        ufmscode: "123456",
        issuer: "Загс ...",
        issued: "21.12.2112",
        address: "ул. Строителей,...",
    }
    <-{
        error: null|"Плохо пошло"
    }
    '''

    @client_token_required()
    @sbt_client_required
    def _post(self, *args, **kwargs):
        if self.sco is None:
            return {"error": self._t("subs_contract_not_found")}
        elif self.sco.completed is not None:
            return {"error": self._t("subs_contract_is_completed")}

        if self.sco.mnp_app_api_version == self.sco.MNP_APP_API_V2:
            return {}

        self.sco.order_data = self.sco.order_data.copy()
        self.sco.order_data.update(self.data)
        self.sco.save(self.db_session)
        return {}


class MnpRequestSignHandler(BaseHandler, MnpMixin):
    u'''
    ->{
        token: "asd",
        mnp_request_id: 123
        signature: "<base64>",
    }
    <- {
        error: null |  "неудача",
        message: "было отправлено SMS" | null
    }
    '''

    @client_token_required()
    @sbt_client_required
    def _post(self, *args, **kwargs):
        if self.sco is None:
            return {"error": self._t("subs_contract_not_found")}
        elif self.sco.completed is not None:
            return {"error": self._t("subs_contract_is_completed")}

        self.sco.signature = self.data['signature']
        self.sco.save(self.db_session)
        return {}


class MnpRequestConfirmationHandler(BaseHandler, MnpMixin):
    u'''
    ->{
        token: "asd",
        mnp_request_id: 123
        contact_phone: "9253241135",
    }
    <- {
        error: null |  "неудача",
        message: "было отправлено SMS" | null
    }
    '''

    @client_token_required()
    @sbt_client_required
    def _post(self, *args, **kwargs):
        try:
            if self.sco is None:
                return {"error": self._t("subs_contract_not_found")}
            elif self.sco.completed is not None:
                return {"error": self._t("subs_contract_is_completed")}

            if self.sco.mnp_app_api_version == self.sco.MNP_APP_API_V2:

                if (not self.data.get('contact_phone')):
                    return {"error": self._t("mnp_number_required")}

                mnp_number = self.data['contact_phone']
                mnp_number_operator = get_reg_op(
                    mnp_number, self.db_session,
                    force=True
                )[1]

                if mnp_number_operator == "sbt":
                    return {"error": self._t("mnp_equal_operators")}

                self.sco.mnp_number = self.data['contact_phone']

            self.sco.contact_phone = self.data.get('contact_phone')
            self.sco.save(self.db_session)

            confirm = Confirm(
                client_id=self.sco.client_id,
                confirm_item='SubscriberContract',
                confirm_item_id=self.sco.id,
            )
            confirm.contact_phone = self.sco.mnp_number
            confirm.save(self.db_session)
            status, message = confirm.send_secret_code(
                self.db_session,
                sms_text=self._t("confirm_subs_contract_mnp_sms_text")
            )
            print(u'CONFIRM ', confirm.contact_phone, confirm.secret_code)
            if status:
                return {
                    "confirmation_id": confirm.id,
                    "message": message,
                    "result": 1,
                }
            else:
                return {
                    "error": message,
                    "result": 0,
                }
        except Exception as e:
            return {
                'error': str(e),
                "result": 0,
            }

class MnpRequestHandler(BaseHandler, MnpMixin):
    u'''
    ->{
        token: “asd”,
        mnp_request_id: 12321,
        code: “80085” | null,  // null для нового api (после 01.10.2019)
        contact_email: “asd@dsa.sda” | null,   // null для нового api (после 01.10.2019)
        contact_phone: “9253241135” | null,
    }
    <- {
        error: 'Не удалось почему-то'|null,
        message: null|'Срок выполнения операции 3 календарных дня'
    }
    '''

    @client_token_required()
    @sbt_client_required
    def _post(self, *args, **kwargs):
        if self.sco is None:
            return {"error": self._t("subs_contract_not_found")}
        elif self.sco.completed is not None:
            return {"error": self._t("subs_contract_is_completed")}

        self.info(u"{} {}".format(self.sco.id, self.data))

        is_sco_confirmed = False
        if self.sco.mnp_app_api_version == self.sco.MNP_APP_API_V2:
            # new mnp app api(sco.mnp_confirmed earlier)

            if self.sco.mnp_confirmed:
                is_sco_confirmed = True

        else:  # old mnp app api
            confirm = Confirm.get(
                self.db_session,
                confirm_item='SubscriberContract',
                confirm_item_id=self.sco.id,
                secret_code=self.data.get('code'),
            )
            if confirm is not None:
                is_sco_confirmed = True

        if not is_sco_confirmed:
            self.info(u"{} not confirmed {}".format(self.sco.id, self.data))
            resp = {
                "error": self._t("confirm_wrong_sms_code"),
                "result": 0,
            }
            return resp

        # if self.client_id != '9809033502':
        if self.data.get("contact_email"):
            self.sco.contact_email = self.data["contact_email"]

        if self.data.get("contact_phone"):
            self.sco.contact_phone = self.data["contact_phone"]

        self.sco.complete(self.db_session)
        sco = self.sco
        # else:
        #     sco = self.db_session.query(SubscriberContractOrder).filter(
        #         SubscriberContractOrder.id == 58680,
        #     ).first()

        resp = {
            "message": (
                u'Номер будет перенесен {} {}. '
            ).format(
                sco.mnp_date, sco.mnp_time,
            ),
            "result": 1,
            "orderStatusToken": self._get_order_status_token(sco)
        }
        self.info(u"{} confirmed {}".format(sco.id, self.data))
        print('MNP HANDLER RESP', resp)
        return resp

    def _get_order_status_token(self, order):
        device_id = self.data.get('device_id', None)
        if not device_id:
            return None

        device = DeviceData(
            device_id=device_id,
            client_id=order.client_id,
            os=self.data.get('os'),
            data=self.data,
        )

        if (
                not device.os or
                not device.is_ios and not device.is_android or
                device.is_ios and device.app_ver <= '1.18.5' or
                device.is_android and device.app_ver <= '1.18.5'
        ):
            return None

        client_token = create_mnp_token(order, self.db_session, commit=False)

        device.token = client_token.token
        device.data['order_id'] = order.id

        self.db_session.add(device)

        self.db_session.commit()
        return client_token.token


class MnpRequestDataHandler(BaseHandler, MnpMixin, GetContractDataMixin):
    u'''
    ->{
        token: "asd",
        local_time:"yyyy.mm.ddTHH:MM:SS",
    }
    <- {
        mnp_dates: {
            "default": ["dd.mm.yyyy", …]
        },
        mnp_times: {
            "default": ["11:00 - 12:00", ...],
            "dd.mm.yyyy": ["11:00 - 12:00", ...],
            ...
        },
        "details": {
            fio: "Суй Во Чай",
            sex: "Муж"/"Жен",
            birthdate: "12.12.2000",
            citizenship: "РФ",
            doctype: "Паспорт РФ",
            serial: "1234",
            docid: "12345678",
            ufmscode: "123-456",
            issuer: "Загс ...",
            issued: "21.12.2112",
            address: "ул. Строителей,...",
            email: "director@мвд.рф"’
        },
        "icc_prefix:": ""
    }
    '''

    @property
    @memorizing
    def local_dt(self):
        local_dt = (
            self.data.get('local_time') and datetime.datetime.strptime(
                self.data['local_time'], "%Y.%m.%dT%H:%M:%S"
            )
        ) or (
            datetime.datetime.utcnow() +
            datetime.timedelta(hours=3)
        )
        local_dt += datetime.timedelta(hours=1)
        local_dt = local_dt.replace(minute=0, second=0)
        return local_dt

    @client_token_required()
    def _post(self, *args, **kwargs):
        return {
            "mnp_dates": {"default": self.mnp_dates},
            "mnp_times": self.mnp_times,
            "icc_prefix": self.icc_prefix,
            "details": self.user_details,
        }

    @property
    @memorizing
    def mnp_dates(self):
        resp = [
            (self.local_dt + datetime.timedelta(days=days_shift)).strftime('%d.%m.%Y') for days_shift in range(8, 180)
        ]

        return resp

    MNP_TIMES = [
        '23:00-00:00',
        '10:00-11:00',
        '11:00-12:00',
        '12:00-13:00',
        '13:00-14:00',
        '14:00-15:00',
        '15:00-16:00',
        '16:00-17:00',
        '17:00-18:00',
        '18:00-19:00',
        '19:00-20:00',
        '20:00-21:00',
        '21:00-22:00',
        '22:00-23:00',
    ]

    @property
    @memorizing
    def mnp_times(self):
        default_times = [
            t for t in self.MNP_TIMES
            if t >= self.local_dt.strftime('%H')
        ]
        mnp_times = {
            'default': default_times,
            self.mnp_dates[0]: default_times,
        }
        for mnp_date in self.mnp_dates[1:]:
            mnp_times[mnp_date] = self.MNP_TIMES
        return mnp_times

    @property
    @memorizing
    def icc_prefix(self):
        return ""

    @property
    @memorizing
    def user_details(self):
        contract_data = self._get_contract_data()
        return contract_data
        # return {
        #     "fio": "",
        #     "sex": "",
        #     "birthdate": "",
        #     "citizenship": "",
        #     "doctype": "",
        #     "serial": "",
        #     "docid": "",
        #     "ufmscode": "",
        #     "issuer": "",
        #     "issued": "",
        #     "address": "",
        #     "email": "",
        # }


class MnpRequestCreateHandler(BaseHandler):

    # @client_token_required()
    def _post(self, *args, **kwargs):
        print('MnpRequestCreateHandler', self.data)
        sco = SubscriberContractOrder()
        sco.order_type = SubscriberContractOrder.ORDER_TYPE_MNP
        sco.src = settings.SERVER_NAME
        sco.mnp_app_api_version = sco.MNP_APP_API_V2
        sco = sco.save(self.db_session)
        print(dict(mnp_request_id=sco.id))
        return dict(mnp_request_id=sco.id)


class MnpRequestConfirmHandler(BaseHandler, MnpMixin):
    '''-> {
        token: “asd”,
        mnp_request_id: 12321,
        code: “80085”
    }
    // for server: сохранять факт валидации номера
    <- {
        error: null |  “неудача”,
    }
    '''
    def _post(self):
        # print('conrirm', self.data)
        confirm = Confirm.get(
            self.db_session,
            confirm_item='SubscriberContract',
            confirm_item_id=self.sco.id,
            secret_code=self.data.get('code'),
        )

        if confirm is None:
            self.info(u"{} not confirmed {}".format(self.sco.id, self.data))
            resp = {
                "error": self._t("confirm_wrong_sms_code"),
                "result": 0,
            }
            return resp

        self.sco.mnp_confirmed = True
        self.sco.save(self.db_session)
        return {}
