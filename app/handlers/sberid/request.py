# -*- encoding: utf-8 -*-

import uuid
from app.handlers import BaseHandler
# from app.models import sbIdData
from app_models import (
    ClientToken, DeviceData
)
from app_sbt.api.sbid_api import sbIdApi
from app_utils.wrappers import json_property


__all__ = (
    'RequestsbIdHandler',
)


class RequestsbIdHandler(BaseHandler):

    data_device_id = json_property('data', 'device_id')
    data_os = json_property('data', 'os')

    def _post(self):
        client_token = ClientToken(
            client_id=self.client_id or None,
            token='sbid:{}'.format(uuid.uuid4()),
            status=ClientToken.STATUS_CONFIRMED,
            code=ClientToken.CODE_sbID_ORDER,
        )
        self.db_session.add(client_token)

        device = DeviceData(
            device_id=self.data_device_id,
            client_id=self.client_id or None,
            os=self.data_os,
            data=self.data,
            token=client_token.token,
        )
        self.db_session.add(device)

        api = sbIdApi(device)
        register_data = api.register()
        self.db_session.commit()

        response = {
            "sbid_token": client_token.token,
            "client_id": register_data["client_id"],
            "scope": register_data["scope"],
            "state": register_data["state"],
            "nonce": register_data["nonce"],
        }
        return response
