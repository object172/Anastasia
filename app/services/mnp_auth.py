# -*- encoding: utf-8 -*-
import uuid

from app_models import ClientToken
from app_sbtelecom.api.sbt_sms_api import SbtSmsApi
from app_sbtelecom.models import SbtApiReg
from app_utils.password_utils import generate_password
from app_utils.alarm_utils import get_alarm_bot


__all__ = (
    'create_mnp_token',
    'send_mnp_auth_code',
    'send_new_mnp_auth_code',
)


alarm_bot = get_alarm_bot()


def create_mnp_token(scorder, db_session, commit=True):
    client_token = db_session.query(ClientToken).filter(
        ClientToken.client_id == scorder.client_id,
        ClientToken.token.like('order:{}:mnp:%'.format(scorder.id)),
        ClientToken.status == ClientToken.STATUS_CONFIRMED,
        ClientToken.code == ClientToken.CODE_MNP_ORDER,
        ClientToken.deleted != None,
    ).first()
    if client_token is None:
        client_token = ClientToken(
            client_id=scorder.client_id,
            token='order:{}:mnp:{}'.format(scorder.id, uuid.uuid4()),
            status=ClientToken.STATUS_CONFIRMED,
            code=ClientToken.CODE_MNP_ORDER,
        )
        db_session.add(client_token)
        commit and db_session.commit()
    return client_token


def send_mnp_auth_code(scorder, db_session, commit=True):
    mnp_code = generate_password(
        need_lowercase_char=False,
        need_uppercase_char=False,
    )
    for api_reg in db_session.query(SbtApiReg).filter_by(
            client_id=scorder.client_id, device_id='mnp',
            deleted=None
    ).all():
        api_reg.delete(db_session, commit=False)

    for _ in range(3):
        api_reg = SbtApiReg(
            client_id=scorder.client_id,
            device_id='mnp',
        )
        api_reg.password = mnp_code
        db_session.add(api_reg)
    commit and db_session.commit()

    try:
        SbtSmsApi(
            scorder.mnp_number,
            scorder.mnp_operator,
        ).send((
            u'Уважаемый Клиент, узнайте cтатус заявки на перенос номера {mnp_msisdn} в МП «СберМобайл».\n'
            u'Логин: {msisdn}, пароль: {mnp_code}.'

        ).format(
            mnp_msisdn=scorder.mnp_number,
            msisdn=scorder.client_id,
            mnp_code=mnp_code,
        ))
    except Exception as err:
        log_txt = u'Can\'t send SMS with MNP code: {}'.format(err)
        try:
            print(log_txt)
            alarm_bot.alarm(log_txt)
        except:
            pass
    return True


def send_new_mnp_auth_code(scorder, db_session, commit=True):
    mnp_code = generate_password(
        need_lowercase_char=False,
        need_uppercase_char=False,
    )
    for api_reg in db_session.query(SbtApiReg).filter_by(
            client_id=scorder.client_id, device_id='mnp',
            deleted=None
    ).all():
        api_reg.delete(db_session, commit=False)

    for _ in range(3):
        api_reg = SbtApiReg(
            client_id=scorder.client_id,
            device_id='mnp',
        )
        api_reg.password = mnp_code
        db_session.add(api_reg)
    commit and db_session.commit()
    try:
        SbtSmsApi(
            scorder.mnp_number,
            scorder.mnp_operator,
        ).send((
            u'Уважаемый Клиент, узнайте cтатус заявки на перенос номера {mnp_msisdn} в МП «СберМобайл».\n'
            u'Логин: {msisdn}, пароль: {mnp_code}.'

        ).format(
            mnp_msisdn=scorder.mnp_number,
            msisdn=scorder.client_id,
            mnp_code=mnp_code,
        ))
    except Exception as err:
        log_txt = u'Can\'t send SMS with MNP code: {}'.format(err)
        try:
            print(log_txt)
            alarm_bot.alarm(log_txt)
        except:
            pass
    return True
