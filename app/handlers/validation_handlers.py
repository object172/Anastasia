# -*- encoding: utf-8 -*-

from app.handlers import BaseHandler
from app.services import get_bank_name, check_account_number
from app_bercut.api import MnpApi
from app_podkliuchi.api import ServerApi
from app_utils.alarm_utils import error as bot_error


__all__ = (
    'MnpPhoneCheckHandler',
    'ValidateBankBikHandler',
    'ValidateBankAccountHandler',
)


class MnpPhoneCheckHandler(BaseHandler):

    def _post(self):
        phone = self.data.get('phone')
        if not phone:
            return dict(
                result=0,
                error='required: phone'
            )
        if not phone.startswith('7'):
            phone = '7' + phone

        operator = None

        try:
            number_info = MnpApi().getNumberInfo(phone).json['GetNumberInfoResponse']
            operator = number_info['operatorName']
        except:
            pass

        return dict(
            isValid=bool(operator),
            operator=operator
        )


class ValidateBankBikHandler(BaseHandler):

    def _post(self):
        bank_id = self.data.get('bank_id')
        if not bank_id:
            return dict(
                result=0,
                error=u'Не указан БИК, проверьте ввод!',
            )

        bank_name = get_bank_name(bank_id)
        if bank_name:
            return dict(
                result=1,
                name=bank_name,
            )
        return dict(
            result=0,
            error=u'Не найден банк с указанным БИК!',
        )


class ValidateBankAccountHandler(BaseHandler):

    def _post(self):
        try:
            account_number = self.data['account_number']
            bank_id = self.data['bank_id']
            if not bank_id.isdigit() or len(bank_id) != 9:
                raise ValueError('bad bank_id')
        except Exception as e:
            print(e)
            return dict(
                error=u'Проверьте ввод!',
            )

        e = None
        try:
            is_valid = check_account_number(account_number, bank_id)
            return dict(
                isValid=is_valid,
                # account_number=account_number,
                # bank_id=bank_id,
            )
        except Exception as e:
            print(e)
            bot_error(str(e))

        return dict(
            isValid=False,
            # e=str(e),
        )
