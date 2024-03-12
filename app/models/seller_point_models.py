# -*- encoding: utf-8 -*-

import datetime
import json
import geocoder
import random
import string
import time
import traceback
import xlrd

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy import (
    or_ as sql_or
)
from app_utils.db_utils.models import JSONB

from app.models.mixins import (
    AppDeclBase, BaseModel, jsonb_property
)
from app_utils.wrappers import memorizing


__all__ = (
    'SellerPoint',
)


class SellerPoint(AppDeclBase, BaseModel):
    __tablename__ = "seller_points"

    SP_TYPE_VSP = 'vsp'
    SP_TYPE_PICK_POINT = 'pick_point'

    id = Column(Integer, primary_key=True)

    region = Column(Integer, index=True)
    operator = Column(String, index=True)

    sp_type = Column(String, default=SP_TYPE_VSP)
    name = Column(String)
    address = Column(String)

    data = Column(JSONB, default={})

    created = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)

    _schedule = jsonb_property('data', 'schedule', list)
    schedule_from = jsonb_property('data', 'schedule_from', '')
    schedule_till = jsonb_property('data', 'schedule_till', '')
    coords = jsonb_property('data', 'coords', dict)

    near_subway = jsonb_property('data', 'near_subway', '')
    _is_pilot_sp = jsonb_property('data', 'is_pilot_sp', False)

    def get_name(self):
        if self.sp_type == self.SP_TYPE_VSP:
            return u'Офис №{}'.format(self.name)
        return self.name

    @property
    def is_pilot_sp(self):
        return self._is_pilot_sp

    @is_pilot_sp.setter
    def is_pilot_sp(self, value):
        self._is_pilot_sp = bool(value)

    @property
    def schedule(self):
        return self._schedule

    @schedule.setter
    def schedule(self, schedule_str):
        schedule_paths = schedule_str.split(',')
        schedule_data = []
        for schedule_path in schedule_paths:
            schedule_day, schedule_time = schedule_path.split(".:")
            _, schedule_from, _, schedule_till = schedule_time.strip().split()
            schedule_data.append({
                "day": schedule_day.strip().lower(),
                "from": schedule_from,
                "till": schedule_till,
            })

        schedule = []
        prev_schedule_day, prev_schedule_time = (
            schedule_data[0]["day"],
            (schedule_data[0]["from"], schedule_data[0]["till"])
        )
        start_schedule_day = prev_schedule_day
        for schedule_item in schedule_data[1:]:
            current_schedule_day, current_schedule_time = (
                schedule_item["day"],
                (schedule_item["from"], schedule_item["till"])
            )
            if prev_schedule_time != current_schedule_time:
                if prev_schedule_day != start_schedule_day:
                    schedule.append({
                        "days": u"{}-{}".format(
                            start_schedule_day,
                            prev_schedule_day,
                        ),
                        "from": prev_schedule_time[0],
                        "till": prev_schedule_time[1],
                    })
                else:
                    schedule.append({
                        "days": prev_schedule_day,
                        "from": prev_schedule_time[0],
                        "till": prev_schedule_time[1],
                    })
                start_schedule_day = current_schedule_day
            prev_schedule_day = current_schedule_day
            prev_schedule_time = current_schedule_time

        if not schedule:
            if (
                    start_schedule_day == u'пн' and
                    prev_schedule_day in [u'вс', u'вск']
            ):
                schedule.append({
                    "days": u'ежедневно',
                    "from": prev_schedule_time[0],
                    "till": prev_schedule_time[1],
                })
            elif prev_schedule_day != start_schedule_day:
                schedule.append({
                    "days": u"{}-{}".format(
                        start_schedule_day,
                        prev_schedule_day,
                    ),
                    "from": prev_schedule_time[0],
                    "till": prev_schedule_time[1],
                })
            else:
                schedule.append({
                    "days": prev_schedule_day,
                    "from": prev_schedule_time[0],
                    "till": prev_schedule_time[1],
                })

        else:
            schedule.append({
                "days": prev_schedule_day,
                "from": prev_schedule_time[0],
                "till": prev_schedule_time[1],
            })

        self._schedule = schedule
        self.schedule_from = schedule[0]["from"]
        self.schedule_till = schedule[0]["till"]

    def get_info(self):
        return {
            "id": self.id,
            "name": self.get_name(),
            "address": self.address,
            "from": self.schedule_from,
            "till": self.schedule_till,
            "schedule": self.schedule,
            "coords": self.coords,
        }

    @classmethod
    def load_vsp_sp_from_xls(cls, db_session, operator, region, file_path, sp_type=None):
        wb = xlrd.open_workbook(file_path)
        sheet = wb.sheet_by_index(0)
        HEADERS = ['_', 'name', 'is_pilot_sp', 'address', 'near_subway', 'schedule']
        for rownum in xrange(sheet.nrows):
            if not rownum:
                continue

            row = sheet.row_values(rownum)
            row = map(lambda s: unicode(s).strip(), row)
            row_data = dict(zip(HEADERS, row))

            sp = db_session.query(cls).filter_by(
                region=region, operator=operator,
                name=row_data['name']
            ).first() or cls(
                region=region, operator=operator,
            ).save(db_session, commit=False)

            sp.sp_type = sp_type or cls.SP_TYPE_VSP
            for key, value in row_data.items():
                setattr(sp, key, value)

            for _ in xrange(10):
                latlng = geocoder.google(sp.address.split(u'пом.')[0].strip()).latlng
                if latlng:
                    sp.coords = dict(zip(["lat", "lng"], latlng))
                    break
                else:
                    time.sleep(1)
            else:
                print(sp.id, "not found coords")
            sp.save(db_session)
