# -*- encoding: utf-8 -*-

import sys
import datetime
from sqlalchemy import or_ as sa_or

from app_models import DeviceData, Client
from app_sbtelecom.api import SbtBercutBillingApi
from app_sbtelecom.connectors import sbTelecomConnector
from app.handlers import BaseHandler
from app.models import ActiveDeviceClient, ActiveDeviceWiFi
from app.wrappers import client_token_required
from app_utils.db_utils.models import jsonb_property
from app_regions.services import is_wifi_available_for_client


__all__ = (
    'ActiveDeviceClientHandler',
    'ChangeDeviceWiFiHandler',
    'DeviceWiFiStatusHandler',
)


class ActiveDeviceClientHandler(BaseHandler):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if (
                not self.device or
                not self.device.is_mobile
        ):
            return {}

        is_active_device_client = self.db_session.query(
            ActiveDeviceClient.id
        ).filter(
            ActiveDeviceClient.device_id == self.device.id,
            ActiveDeviceClient.client_id == self.client_id,
            ActiveDeviceClient.deleted == None,
        ).order_by(
            ActiveDeviceClient.id.desc()
        ).first()

        print('device_uid', self.device_uid)

        if not is_active_device_client:
            deleted = datetime.datetime.utcnow()
            adcs_for_delete = self.db_session.query(
                ActiveDeviceClient
            ).join(
                DeviceData, DeviceData.id == ActiveDeviceClient.device_id,
            ).filter(
                sa_or(
                    DeviceData.device_id == self.device_uid,
                    ActiveDeviceClient.client_id == self.client_id,
                ),
                ActiveDeviceClient.deleted == None,
            ).all()
            for adc in adcs_for_delete:
                adc.deleted = deleted

            new_adc = ActiveDeviceClient(
                device_id=self.device.id,
                client_id=self.client_id,
            ).save(self.db_session)
        return {}


class ChangeDeviceWiFiHandler(BaseHandler):

    data_active = jsonb_property('data', 'active')

    @client_token_required()
    def _post(self, *args, **kwargs):
        if (
                not self.device or
                not self.device.is_mobile
        ):
            return {
                "result": 0,
                "error": u'Не удалось подключить WiFi Звонки',
            }

        active_device_wifi = self.db_session.query(
            ActiveDeviceWiFi
        ).join(
            DeviceData, DeviceData.id == ActiveDeviceWiFi.device_id,
        ).filter(
            DeviceData.device_id == self.device_uid,
            ActiveDeviceWiFi.client_id == self.client_id,
            ActiveDeviceWiFi.deleted == None,
        ).order_by(
            ActiveDeviceWiFi.id.desc()
        ).first()

        if self.data_active == False and active_device_wifi:
            active_device_wifi.deleted = datetime.datetime.utcnow()
            active_device_wifi.save(self.db_session)

            if self.off_wifi(active_device_wifi):
                return {"result": 1}
            else:
                return {
                    "result": 0,
                    "error": u'Не удалось отключить WiFi Звонки',
                }
        elif self.data_active == True:
            if not is_wifi_available_for_client(self.client):
                return {
                    "result": 0,
                    "error": u'WiFi Звонки недоступны в вашем регионе',
                }

            if not active_device_wifi:
                deleted = datetime.datetime.utcnow()
                adwfs_for_delete = self.db_session.query(
                    ActiveDeviceWiFi
                ).join(
                    DeviceData, DeviceData.id == ActiveDeviceWiFi.device_id,
                ).filter(
                    sa_or(
                        DeviceData.device_id == self.device_uid,
                        ActiveDeviceWiFi.client_id == self.client_id,
                    ),
                    ActiveDeviceWiFi.deleted == None,
                ).all()
                for active_device_wifi in adwfs_for_delete:
                    active_device_wifi.deleted = deleted
                    self.off_wifi(active_device_wifi)

                active_device_wifi = ActiveDeviceWiFi(
                    device_id=self.device.id,
                    client_id=self.client_id,
                ).save(self.db_session)

            if self.on_wifi(active_device_wifi):
                return {"result": 1}
            else:
                return {
                    "result": 0,
                    "error": u'Не удалось подключить WiFi Звонки',
                }
        return {"result": 1}

    def on_wifi(self, active_device_wifi):
        client = Client(
            number=active_device_wifi.client_id,
            operator='sbt',
        )
        connector = sbTelecomConnector(client)
        connector.login_client(
            client, db_session=self.db_session,
            autologin=True
        )
        on_services = connector.on_services(
            on_services=[u'WiFi Звонки'],
            on_services_ids=[1530, ]
        ) or []

        status = 0
        for item in on_services:
            _, status, _ = item
            break
        connector.do_log('', self.db_session, 'on_wifi')
        return status  # or 1

    def off_wifi(self, active_device_wifi):
        client = Client(
            number=active_device_wifi.client_id,
            operator='sbt',
        )
        connector = sbTelecomConnector(client)
        connector.login_client(
            client, db_session=self.db_session,
            autologin=True
        )
        off_services = connector.off_services(
            off_services=[u'WiFi Звонки'],
            off_services_ids=[1530, ]
        ) or []

        status = 0
        for item in off_services:
            _, status, _ = item
            break

        connector.do_log('', self.db_session, 'off_wifi')
        return status  # or 1


class DeviceWiFiStatusHandler(BaseHandler):

    @client_token_required()
    def _post(self):
        active_device_wifi = self.db_session.query(
            ActiveDeviceWiFi
        ).join(
            DeviceData, DeviceData.id == ActiveDeviceWiFi.device_id,
        ).filter(
            DeviceData.device_id == self.device_uid,
            ActiveDeviceWiFi.deleted == None,
        ).order_by(
            ActiveDeviceWiFi.id.desc()
        ).first()
        if not active_device_wifi:
            print('ACTIVE DEVICE WIFI IS NONE', self.data)
            r = self.get_wifi_data(0, 10)
            r.update(dict(
                result=1,
                wifi=False,
            ))
            return r

        status = active_device_wifi and self.get_wifi_service_status(active_device_wifi.client_id)
        wifi_data = self.get_wifi_data(
            status,
            (datetime.datetime.utcnow() - active_device_wifi.created).total_seconds(),
        )
        response = {
            "result": 1,
            "wifi": bool(active_device_wifi),
            "client_id": (
                active_device_wifi and
                active_device_wifi.client_id or None
            ),
        }
        response.update(wifi_data)
        return response

    @staticmethod
    def get_wifi_service_status(client_id):
        try:
            api = SbtBercutBillingApi(
                number=client_id
            )
            r = api.getEnabledSubscriberServices()
            services = r.json['getEnabledSubscriberServicesResponseParams']['subscriberServicesList']['service']
            params = {s['billingServiceId']: s for s in services}
            if params.get(1530):
                status = params[1530]['serviceStatus']
                if status == 'active':
                    return 1
                elif status == 'disabled':
                    return 0
                return 2
        except Exception as e:
            print(e)
        return 0

    @staticmethod
    def get_wifi_data(status, elapsed_seconds):
        if status == 1:
            return dict(
                wifi_status_timeout=None,
                wifi_status=1,
                wifi=True,
            )
        if elapsed_seconds > 5 * 60:
            return dict(
                wifi_status_timeout=None,
                wifi_status=0,
                wifi=False,
            )

        wifi_data = dict(
            wifi_status=2,
            wifi=True,
        )
        if elapsed_seconds < 60:
            timeout = 5
        elif elapsed_seconds < 120:
            timeout = 10
        else:
            timeout = 30
        wifi_data['wifi_status_timeout'] = timeout
        return wifi_data
