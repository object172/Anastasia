# -*- encoding: utf-8 -*-

import datetime
import traceback
from collections import defaultdict
from itertools import groupby, izip

from app.models.mixins import AppDeclBase, BaseModel, jsonb_property
from app_models import DeviceData, PushLog
from app_utils.db_utils import IS_ORACLE_DB
from app_utils.db_utils.models import JSONB
from app_utils.fcm_utils import fcm, send_pushs
from app_utils.wrappers import memorizing
from sqlalchemy import Boolean, Column, DateTime, Integer, String

__all__ = (
    'PushSchedule',
)


class PushSchedule(BaseModel, AppDeclBase):
    __tablename__ = 'pushes_shedule'

    AVAILABLE_DT_HOUR_START = 9
    AVAILABLE_DT_HOUR_END = 22

    id = Column(Integer, primary_key=True)
    name = Column(String)
    trigger = Column(DateTime, name='trigger_' if IS_ORACLE_DB else 'trigger')

    data = Column(JSONB, default={})

    created = Column(DateTime, default=datetime.datetime.utcnow)
    completed = Column(DateTime)
    deleted = Column(DateTime)

    title = jsonb_property('data', 'title', '')
    message = jsonb_property('data', 'message', '')
    link = jsonb_property('data', 'link', '')

    stats = jsonb_property('data', 'stats', dict)
    progress = jsonb_property('stats', 'progress', dict)
    progress_current = jsonb_property('progress', 'current', int)
    progress_total = jsonb_property('progress', 'total', int)

    count_success = jsonb_property('stats', 'count_success', int)
    count_failed = jsonb_property('stats', 'count_failed', int)

    _devices_to_send = jsonb_property('data', 'devices_to_send', list)
    devices_success = jsonb_property('data', 'devices_success', list)
    devices_failed = jsonb_property('data', 'devices_failed', dict)

    @property
    @memorizing
    def push_data(self):
        data = {"sbt_push": 1}
        if self.link:
            data["url"] = self.link
        return data

    @property
    def devices_to_send(self):
        return self._devices_to_send

    @devices_to_send.setter
    def devices_to_send(self, devices_to_send):
        if not self.progress_total:
            self.progress_total = len(devices_to_send)
        self._devices_to_send = devices_to_send

    def send(self, db_session):
        utcnow = datetime.datetime.utcnow()

        if self.created < utcnow - datetime.timedelta(days=2):
            self.completed = utcnow
            self.save(db_session)
            return

        if not self.devices_success:
            self.devices_success = ['']

        if not self.devices_failed:
            self.devices_failed = {'': ''}

        STEP = 1000
        devices_data = []
        for i in range(0, len(self.devices_to_send) + STEP, STEP):
            _devices_to_send = self.devices_to_send[i:i + STEP]
            devices_data += (
                _devices_to_send
                and db_session.query(
                    DeviceData.id,
                    DeviceData.client_id,
                    DeviceData.data,
                ).filter(
                    DeviceData.id.in_(_devices_to_send),
                ).all()
            )

        devices_data = [(did, cid, data['fcm_token'])
            for (did, cid, data) in devices_data
            if data and data.get('fcm_token')
        ]
        devices_data.sort(key=lambda (did, cid, fcmt): (
            fcmt, -1 * did
        ))

        fcm_token_devices = defaultdict(list)
        device_client_ids = {}
        for (did, cid, fcmt) in devices_data:
            fcm_token_devices[fcmt].append(did)
            device_client_ids[did] = cid

        fcm_tokens = fcm_token_devices.keys()
        for idx in xrange(0, len(fcm_tokens), fcm.FCM_MAX_RECIPIENTS):
            _fcm_tokens = fcm_tokens[idx:(idx + fcm.FCM_MAX_RECIPIENTS)]

            try:
                _, response = send_pushs(
                    self.title, self.message,
                    _fcm_tokens,
                    data=self.push_data,
                )
                resp = response[0]
            except:
                continue

            self.count_success = self.count_success + resp['success']
            self.count_failed = self.count_failed + resp['failure']

            device_to_remove = set([])
            for fcm_token, result in izip(_fcm_tokens, resp['results']):
                device_ids = fcm_token_devices[fcm_token]
                device_to_remove.update(device_ids)

                if 'error' in result:
                    for device_id in device_ids:
                        self.devices_failed[device_id] = result
                else:
                    self.devices_success += device_ids
                    for device_id in device_ids:
                        db_session.add(PushLog(
                            client_id=device_client_ids[device_id],
                            data={
                                "title": self.title,
                                "message": self.message,
                                "data": self.push_data
                            }
                        ))

            self.progress_current = (
                self.progress_current +
                len(device_to_remove)
            )
            self.devices_to_send = list(
                set(self.devices_to_send) -
                device_to_remove
            )
            self.save(db_session)

        if not self.devices_to_send:
            self.completed = utcnow

        self.save(db_session)
