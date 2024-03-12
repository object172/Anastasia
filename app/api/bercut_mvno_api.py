# -*- encoding: utf-8 -*-
import traceback

import sys
from functools import wraps

from app.exceptions import ApiDataError, ServerError, ServerDataError
from app_regions.data import SPB_REG_DT_ID
from app_regions.services import get_bercut_branch_id_by_dt_reg_id
from app.texts import _t
from app_bercut.api.web_dealer_api import WebDealerApi
from app_bercut.exceptions import (
    BercutApiError, BercutApiValueError
)
from app_sbtelecom.api import SbtBercutBillingApi

__all__ = ('MVNOApi', )


def raise_api_error(**params):
    raise BercutApiError(**params)


def raise_value_error(**params):
    raise BercutApiValueError(**params)


def error_wrapper():
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                try:
                    return func(*args, **kwargs)
                except BercutApiValueError as err:
                    raise ApiDataError(
                        alert_title=getattr(err, 'error_title', None),
                        alert_text=getattr(err, 'error_text', None),
                        error_info=getattr(err, 'error_text', None),
                        error_reason=getattr(err, 'error_reason', None),
                    )
                except BercutApiError as err:
                    raise ServerError(
                        alert_title=getattr(err, 'error_title', None),
                        alert_text=getattr(err, 'error_text', None),
                        error_info=getattr(err, 'error_text', None),
                        error_reason=getattr(err, 'error_reason', None),
                    )
            except Exception as err:
                try:
                    print(err)
                except:
                    pass
                try:
                    print(traceback.format_exc())
                except:
                    pass
                raise err

        return wrapper
    return decorator


class MVNOApi:

    api = WebDealerApi()

    def format_msisdn(self, msisdn):
        if msisdn.startswith('7'):
            msisdn = msisdn[1:]
        return msisdn

    def get_subscriber_id(self, msisdn, fio, docid=None):
        try:
            sbt_api = SbtBercutBillingApi(number=msisdn)
            resp = sbt_api.getSubscriberInfo().json['getClntSubsResponseParams']

            if (
                fio.lower() == resp['client']['personalProfileData']['fullName'].lower() and
                self.format_msisdn(msisdn) == self.format_msisdn(resp['subscriber']['subscriberBaseParameters']['msisdn'])
            ):
                if docid:
                    assert docid == resp['client']['personalProfileData']['identityDocument']['number']
                return resp['subscriber']['subscriberBaseParameters']['subsId']
        except Exception as e:
            pass

    @classmethod
    @error_wrapper()
    def get_branch_id(cls, dt_region_id):
        branch_id = get_bercut_branch_id_by_dt_reg_id(dt_region_id)
        if branch_id is None:
            raise ServerDataError(u'Not found branch_id for dt region: {}'.format(dt_region_id))
        return branch_id

    @classmethod
    @error_wrapper()
    def get_msisdn_type_id(cls, msisdn_type, region):
        if region == SPB_REG_DT_ID:
            _msisdn_type = u'{} СПб'.format(msisdn_type)
            if _msisdn_type in cls.api.MSISDN_TYPES:
                return cls.api.MSISDN_TYPES[_msisdn_type]
        return cls.api.MSISDN_TYPES[msisdn_type]

    @classmethod
    @error_wrapper()
    def getMsisdns(
            cls, region, msisdn_search='',
            msisdn_type=None, offset=0, count=10,
            need_msisdn_format=True,
            **kwargs
    ):
        branch_id = cls.get_branch_id(region)
        msisdn_type_id = msisdn_type and cls.get_msisdn_type_id(msisdn_type, region)

        try:
            data_list = cls.api.getMsisdnListPool(
                msisdnMask=msisdn_search,
                countRecord=offset * count + count,
                msisdnTypeId=msisdn_type_id,
                branchId=branch_id,
            ).json['getMsisdnListPoolResponse'].get(
                'MsisdnPoolList', []
            )
        except:
            data_list = []

        msisdns = [
            data['msisdn']
            for data in data_list if data['msisdn']
        ][offset * count:]
        if need_msisdn_format:
            msisdns = [cls.api.get_msisdn(msisdn) for msisdn in msisdns]
        return msisdns

    @classmethod
    @error_wrapper()
    def getMsisdn(
            cls, region, msisdn,
            msisdn_type=None, need_msisdn_format=True,
            **kwargs
    ):
        branch_id = cls.get_branch_id(region)
        msisdn_type_id = msisdn_type and cls.get_msisdn_type_id(msisdn_type, region)

        try:
            data_list = cls.api.getMsisdnListPool(
                msisdnMask=msisdn,
                countRecord=1,
                msisdnTypeId=msisdn_type_id,
                branchId=branch_id,
            ).json['getMsisdnListPoolResponse'].get(
                'MsisdnPoolList', []
            )
        except:
            data_list = []
        data = data_list and data_list[0] or None
        if data and need_msisdn_format:
            data['msisdn'] = cls.api._get_msisdn(data['msisdn'])
        return data

    @classmethod
    @error_wrapper()
    def reserveMsisdn(cls, order):
        msisdn = cls.api.get_msisdn(order.msisdn)

        try:
            branch_id = order.branch_id or cls.get_branch_id(order.region)
            r = cls.api.reserveMsisdn(order.msisdn, branchId=branch_id)
        except Exception as err:
            try:
                if order and hasattr(err, 'resp_obj'):
                    r = err.resp_obj
                    order.log_reserve_msisdn_url = r.request_url
                    order.log_reserve_msisdn_request = r.request_text
                    order.log_reserve_msisdn_response = r.text
                    order.log_reserve_msisdn_datetime = str(r.request_dt)
            except:
                pass
            raise err
        else:
            if order:
                try:
                    order.log_reserve_msisdn_url = r.request_url
                    order.log_reserve_msisdn_request = r.request_text
                    order.log_reserve_msisdn_response = r.text
                    order.log_reserve_msisdn_datetime = str(r.request_dt)
                except:
                    pass
        return True

    @classmethod
    @error_wrapper()
    def returnMsisdn(cls, order):
        branch_id = order.branch_id or cls.get_branch_id(order.region)
        cls.api.reserveMsisdnReturn(order.msisdn, branchId=branch_id)

        try:
            order.log_return_msisdn_url = r.request_url
            order.log_return_msisdn_request = r.request_text
            order.log_return_msisdn_response = r.text
            order.log_return_msisdn_datetime = str(r.request_dt)
        except:
            pass
        return True
