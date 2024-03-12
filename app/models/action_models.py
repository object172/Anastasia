# -*- encoding: utf-8 -*-

import datetime
import traceback

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app_utils.db_utils.models import JSONB

from app.models.mixins import (
    AppDeclBase, BaseModel, jsonb_property
)
from app_utils.wrappers import memorizing


__all__ = (
    'Action',
)


class Action(AppDeclBase, BaseModel):
    __tablename__ = "actions"

    NO_ID_SEQUENCE = True
    id = Column(Integer, primary_key=True)

    operator = Column(String, index=True)
    region = Column(Integer, index=True)

    name = Column(String)
    data = Column(JSONB, default={})

    created = Column(DateTime, default=datetime.datetime.utcnow)
    expired = Column(DateTime)
    deleted = Column(DateTime)

    title = jsonb_property('data', 'title', '')
    text = jsonb_property('data', 'text', '')
    url = jsonb_property('data', 'url', None)
    icon = jsonb_property('data', 'icon', None)
    scenes = jsonb_property('data', 'scenes', list)

    show_times = jsonb_property('data', 'show_times', None)

    backgrounds = jsonb_property('data', 'backgrounds', dict)
    background_default = jsonb_property('backgrounds', 'default', None)

    button1 = jsonb_property('data', 'button1', None)
    button1_already = jsonb_property('data', 'button1_already', None)

    button2 = jsonb_property('data', 'button2', None)

    @property
    def action_id(self):
        return self.id

    @property
    def expired_timestamp(self):
        return (
            self.expired and
            self.utc_datetime_to_timestamp(self.expired)
        )

    def get_params(self, device=None, os=None, screen=None, app=None):
        return {
            "background": self.get_background(
                os=os or device and device.os,
                screen=screen or device and device.screen,
                app=app or device and device.app,
            ),
            "button1": self.button1,
            "button1_already": self.button1_already,
            "button2": self.button2,
        }

    def get_background(self, os=None, screen=None, app=None):
        if screen and screen in self.backgrounds:
            return self.backgrounds[screen]
        return self.background_default
