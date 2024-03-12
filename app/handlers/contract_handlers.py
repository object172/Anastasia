# -*- encoding: utf-8 -*-

import base64

from app.api import PodkliuchiServerApi
from app.exceptions import ApiError
from app.forms import SendContractToEmailModelForm
from app.handlers import BaseHandler
from app.models import ChangeNumberOrder
from app.texts import _t
from app.wrappers import client_token_required, validate
from app_sbtelecom.api import SbtBercutBillingApi
from app_sbt.api.contract_storage_api import ContractStorageApi
from app_utils.wrappers import memorizing

from methods_simple import get_reg_op


__all__ = (
    'SbtGetContractHandlerV1',
    'SbtSendToEmailContractHandlerV1',
    'ComUnityGetContractHandlerV2',
    'ComUnitySendToEmailContractHandlerV2',
)


#  --- SBT api V1 ---

def sbt_client_required(func):
    def decorator(self, *args, **kwargs):
        _, op = get_reg_op(self.client_id, self.db_session)

        if op != 'sbt':
            raise ApiError(error_text=self._t('contract_only_for_sbt'))

        return func(self, *args, **kwargs)
    return decorator


class SbtGetContractHandlerV1(BaseHandler):

    def get_replaced_msisdn(self):
        cn_order = self.db_session.query(ChangeNumberOrder).filter(
            ChangeNumberOrder.new_number == self.client_id
        ).order_by(ChangeNumberOrder.id.desc()).first()
        if cn_order and str(cn_order.data.get('log', {}).get('status')) == 'True':
            return cn_order.client_id

    @client_token_required()
    @sbt_client_required
    def _post(self, *args, **kwargs):
        api = ContractStorageApi(debug=True)
        doc = api.get_contract(self.client_id)
        if not doc:
            print('contract with {} not found in storage, use PodkliuchiServerApi')
        pdf_data = doc or PodkliuchiServerApi.getContract(self.client_id).getvalue()
        pdf = base64.b64encode(pdf_data).decode()
        return dict(pdf='data:application/pdf;base64,{}'.format(pdf))


class SbtSendToEmailContractHandlerV1(BaseHandler):

    @client_token_required()
    @sbt_client_required
    @validate(SendContractToEmailModelForm)
    def _post(self, *args, **kwargs):
        result = PodkliuchiServerApi.sendContractToEmail(
            self.client_id, self.data['email']
        )
        return dict(result=int(result))

#  ---

#  --- COM:UNITY api V2 ---


def com_unity_client_required(func):
    def decorator(self, *args, **kwargs):
        _, op = get_reg_op(self.client_id, self.db_session)

        if op != 'com:unity':
            raise ApiError(error_text=self._t('contract_only_for_com:unity'))

        return func(self, *args, **kwargs)
    return decorator


class ComUnityGetContractHandlerV2(BaseHandler):

    @client_token_required()
    @com_unity_client_required
    def _post(self, *args, **kwargs):
        bf = PodkliuchiServerApi.getContract(self.client_id)
        pdf = base64.b64encode(bf.getvalue()).decode()
        return dict(pdf='data:application/pdf;base64,{}'.format(pdf))


class ComUnitySendToEmailContractHandlerV2(BaseHandler):

    @client_token_required()
    @com_unity_client_required
    @validate(SendContractToEmailModelForm)
    def _post(self, *args, **kwargs):
        result = PodkliuchiServerApi.sendContractToEmail(
            self.client_id, self.data['email']
        )
        return dict(result=int(result))

#  ---


class TestSbtGetContractHandlerV1(SbtGetContractHandlerV1):

    @property
    def client_id(self):
        return self._client_id

    def __init__(self, client_id):
        self._client_id = client_id
