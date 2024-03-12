# -*- encoding: utf-8 -*-

import re
import sys
import datetime

from itertools import izip_longest
from sqlalchemy import or_ as sa_or
from sqlalchemy.orm import subqueryload

from app_models import UserInfo
from app.handlers import BaseHandler
from app.models import ClientFavourite, ClientFavouriteNumber
from app.services import get_region_timezone_by_dt_id
from app.texts import _t
from app.wrappers import client_token_required
from app_sbtelecom.connectors import sbTelecomConnector
from app_utils.datetime_utils import get_rus_date
from app_utils.wrappers import json_property, memorizing
from methods_simple import get_reg_op




__all__ = (
    'ClientFavouritesGetHandler',
    'ClientFavouritesEditHandler',
)


class AbsClientFavouritesHandler(BaseHandler):

    DATE_FORMAT = '%Y-%m-%d'

    @property
    @memorizing
    def client_favourites(self):
        utcnow = datetime.datetime.utcnow()
        if self.client_id:
            client_favourites = self.db_session.query(
                ClientFavourite
            ).options(
                subqueryload('numbers')
            ).filter(
                ClientFavourite.client_id == self.client_id,
                ClientFavourite.deleted == None,
            ).order_by(
                ClientFavourite.from_dt.nullslast(),
                ClientFavourite.id
            ).limit(2).all()
        else:
            client_favourites = []
        return client_favourites


class ClientFavouritesGetHandler(AbsClientFavouritesHandler):
    u'''
    -> {    token: string   }
    <- {
        result: 1,
        favourites: [{
            numbers: ['+79253241135', ...],
            until: '2018-06-04' | null,
            from: null | '2018-06-20',
        }, ...],
        next_numbers: '2018-07-15',
    }
    '''

    @client_token_required()
    def _post(self, *args, **kwargs):
        if (
            self.client_favourites and
            self.client_favourites[0].until_dt >= datetime.datetime.utcnow() and
            len(self.client_favourites[0].numbers) >= ClientFavourite.MAX_NUMBERS_COUNT
        ):
            next_numbers_dt = self.client_favourites[0].until_dt
        else:
            next_numbers_dt = (datetime.datetime.utcnow() + datetime.timedelta(
                hours=get_region_timezone_by_dt_id(self.client.region)
            ))

        if len(self.client_favourites) == 1:
            cf = self.client_favourites[0]
            favourites = [{
                "numbers": [cfn.msisdn for cfn in cf.numbers],
                "until": None, "from": None,
            }]
        else:
            favourites = [{
                "numbers": [cfn.msisdn for cfn in cf.numbers],
                "until": cf.until_dt and cf.until_dt.strftime(self.DATE_FORMAT) if not num else None,
                "from": cf.from_dt and cf.from_dt.strftime(self.DATE_FORMAT) if num else None,
            } for num, cf in enumerate(self.client_favourites)]
            
        return {
            "result": 1,
            "favourites": favourites,
            "next_numbers": next_numbers_dt.strftime(self.DATE_FORMAT),
        }


class ClientFavouritesEditHandler(AbsClientFavouritesHandler):
    u'''
    -> {
        token: string,
        numbers: ['+79253241135', ...]
    }
    <- {
        message: 'Успешно подключено',
        ok: true,
    }
    '''

    NUMBER_EXP = re.compile(ur'^\+7(\d{10})$')

    data_numbers = json_property('data', 'numbers', default=list)

    @property
    @memorizing
    def numbers(self):
        numbers = map(
            lambda number: self.NUMBER_EXP.search(number).group(1),
            self.data_numbers
        )[:ClientFavourite.MAX_NUMBERS_COUNT]
        return numbers

    @client_token_required()
    def _post(self, *args, **kwargs):
        if not self.client.has_sbtelecom_operator:
            return {
                "message": self._t("favourite_number_not_available"),
                "result": 1, "ok": False
            }

        info = self.db_session.query(UserInfo).filter_by(
            client_id=self.client.number
        ).order_by(UserInfo.id.desc()).first()

        sbt_connector = sbTelecomConnector(self.client)
        current_tariff_obj = info and sbt_connector.TARIFFS_BY_OLD_NAME.get(
            (self.client.operator, self.client.region), {}
        ).get(info.name)

        if not current_tariff_obj:
            sbt_connector.login_client(self.client, db_session=self.db_session, autologin=True)
            current_tariff_obj = sbt_connector._get_current_tariff(need_obj=True)

        if (
            not current_tariff_obj or
            not current_tariff_obj.is_favourite_segment
        ):
            return {
                "message": self._t("favourite_number_not_available"),
                "result": 1, "ok": False
            }

        if not self.data_numbers:
            return {
                "message": self._t("favourite_numbers_required"),
                "result": 1, "ok": False
            }

        if not all(map(self.NUMBER_EXP.match, self.data_numbers)):
            return {
                "message": self._t("favourite_wrong_number"),
                "result": 1, "ok": False
            }

        if not all(map(lambda number: (
                get_reg_op(number, self.db_session) == (self.client.region, 'sbt')
            ), self.data_numbers
        )):
            return {
                "message": self._t("not_favourite_number"),
                "result": 1, "ok": False
            }

        utcnow = datetime.datetime.utcnow()
        now = utcnow + datetime.timedelta(
            hours=get_region_timezone_by_dt_id(self.client.region)
        )
        today_dt = datetime.datetime(now.year, now.month, now.day)
        if not len(self.client_favourites):
            self._add_client_favourite(
                today_dt, today_dt + datetime.timedelta(
                    days=ClientFavourite.TIMEOUT
                )
            )
        elif len(self.client_favourites) == 1 and self.client_favourites[0].until_dt < now:
            if (
                len(self.client_favourites[0].numbers) == len(self.numbers) and
                all(cl_fav_num.number == number for (cl_fav_num, number) in izip_longest(
                    self.client_favourites[0].numbers, self.numbers
                ))
            ):
                return {
                    "message": self._t("favourite_edit_success"),
                    "result": 1, "ok": True
                }

            self.client_favourites[0].deleted = utcnow
            self._add_client_favourite(
                today_dt, today_dt + datetime.timedelta(
                    days=ClientFavourite.TIMEOUT
                )
            )
        elif len(self.client_favourites[0].numbers) < ClientFavourite.MAX_NUMBERS_COUNT:
            for (cl_fav_num, number) in izip_longest(
                self.client_favourites[0].numbers, self.numbers
            ):
                if cl_fav_num and (cl_fav_num.number != number):
                    sys.stderr.write('{}: "{}" != "{}"'.format(cl_fav_num, cl_fav_num and cl_fav_num.number, number))
                    return {
                        "message": self._t("favourite_numbers_changed_error").format(
                            get_rus_date(self.client_favourites[0].until_dt, need_year=False)
                        ), "result": 1, "ok": False
                    }

            if (
                len(self.client_favourites[0].numbers) == len(self.numbers) and
                all(cl_fav_num.number == number for (cl_fav_num, number) in izip_longest(
                    self.client_favourites[0].numbers, self.numbers
                ))
            ):
                return {
                    "message": self._t("favourite_edit_success"),
                    "result": 1, "ok": True
                }

            self.client_favourites[0].deleted = utcnow
            self._add_client_favourite(
                self.client_favourites[0].from_dt,
                self.client_favourites[0].until_dt,
            ) 
        elif len(self.client_favourites) == 2:
            if (
                len(self.client_favourites[1].numbers) == len(self.numbers) and
                all(cl_fav_num.number == number for (cl_fav_num, number) in izip_longest(
                    self.client_favourites[1].numbers, self.numbers
                ))
            ):
                return {
                    "message": self._t("favourite_edit_success"),
                    "result": 1, "ok": True
                }

            self.client_favourites[1].deleted = utcnow
            self._add_client_favourite(
                self.client_favourites[0].until_dt,
                self.client_favourites[0].until_dt + datetime.timedelta(
                    days=ClientFavourite.TIMEOUT
                ),
            )
        elif len(self.client_favourites) == 1:
            if (
                len(self.client_favourites[0].numbers) == len(self.numbers) and
                all(cl_fav_num.number == number for (cl_fav_num, number) in izip_longest(
                    self.client_favourites[0].numbers, self.numbers
                ))
            ):
                return {
                    "message": self._t("favourite_edit_success"),
                    "result": 1, "ok": True
                }

            self._add_client_favourite(
                self.client_favourites[0].until_dt,
                self.client_favourites[0].until_dt + datetime.timedelta(
                    days=ClientFavourite.TIMEOUT
                )
            )

        return {
            "message": self._t("favourite_edit_success"),
            "result": 1, "ok": True
        }

    def _add_client_favourite(self, from_dt, until_dt):
        client_favourite = ClientFavourite(
            client_id=self.client_id,
            from_dt=from_dt, until_dt=until_dt,
        ).save(db_session=self.db_session, commit=False)

        for position, number in enumerate(self.numbers, 1):
            ClientFavouriteNumber(
                client_favourite=client_favourite,
                number=number, position=position,
            ).save(db_session=self.db_session, commit=False)

        self.db_session.commit()
        return client_favourite
