# -*- encoding: utf-8 -*-

import datetime

from sqlalchemy import (
    or_ as sql_or,
    and_ as sql_and
)

from app_models import Client_lk
from app.exceptions import ApiError
from app.forms import ContactApiForm
from app.handlers import BaseHandler
from app.models import Contact
from app.texts import _t
from app.wrappers import client_token_required, validate
from methods_simple import (
    get_reg_op, normalize_number_to_msisdn,
)


__all__ = (
    'SbtContactsHandlerV1', 'ComUnityContactsHandlerV2',
)


class AbsContactsHandler(BaseHandler):

    DT_FORMAT = '%Y-%m-%dT%H:%M:%S'

    @validate(ContactApiForm)
    def _post_handler(self, *args, **kwargs):
        self._add_contacts()
        self._del_contacts()

        utcnow = datetime.datetime.utcnow()
        contacts = self._get_contacts()

        upd_contacts, del_contacts = [], []
        for contact in contacts:
            if contact.is_deleted:
                del_contacts.append(contact.number)
            else:
                upd_contacts.append(dict(
                    number=contact.number,
                    calls_available=bool(contact.calls_available),
                    info=contact.info,
                    op=contact.operator,
                    reg=contact.region,
                ))

        return dict(
            last_datetime=utcnow.strftime(self.DT_FORMAT),
            upd_contacts=upd_contacts,
            del_contacts=del_contacts,
        )

    def _add_contacts(self):
        if not self.data.get('add_contacts'):
            return

        for num, contact_data in enumerate(self.data['add_contacts']):
            number = normalize_number_to_msisdn(contact_data.get('number'))
            if not number:
                continue

            contact = self.db_session.query(Contact).filter_by(
                client_id=self.client_id,
                number=number,
            ).first() or Contact(
                client_id=self.client_id,
                number=number,
            )

            if not contact.device_uid:
                contact.device_uid = (
                    self.device and self.device.device_id
                )

            region, operator = get_reg_op(number, self.db_session)

            if operator in Client_lk.sbTELECOM_OPERATORS:
                contact.calls_available = Contact.calls_available_for_client(
                    self.db_session, client_id=number
                )
            else:
                contact.calls_available = False

            contact.operator = operator
            contact.region = region
            contact.info = (contact_data.get('info') or contact.info)
            contact.deleted = None

            commit = True if num and not num % 100 else False
            contact.save(self.db_session, commit=commit)

        self.db_session.commit()

    def _del_contacts(self):
        del_contacts = self.data.get('del_contacts') or []
        del_contacts = map(normalize_number_to_msisdn, del_contacts)
        del_contacts = filter(bool, del_contacts)

        if not del_contacts:
            return

        self.db_session.query(Contact).filter_by(
            client_id=self.client_id,
        ).filter(
            Contact.number.in_(del_contacts)
        ).update(dict(
            deleted=datetime.datetime.utcnow()
        ), synchronize_session='fetch')
        self.db_session.commit()

    def _get_contacts(self):
        contacts_query = self.db_session.query(Contact).filter_by(
            client_id=self.client_id,
        )

        if self.data.get('last_datetime'):
            last_datetime = datetime.datetime.strptime(
                self.data['last_datetime'], self.DT_FORMAT
            )

            contacts_query = contacts_query.filter(sql_and(
                Contact.updated != None,
                Contact.updated >= last_datetime
            ))

        if self.data.get('only_sbt'):
            contacts_query = contacts_query.filter(
                Contact.operator.in_(Client_lk.sbTELECOM_OPERATORS)
            )

        if self.data.get('calls_available'):
            contacts_query = contacts_query.filter(
                Contact.calls_available == True
            )

        return contacts_query.all()


def sbt_client_required(func):
    def decorator(self, *args, **kwargs):
        _, op = get_reg_op(self.client_id, self.db_session)
        if op != 'sbt':
            raise ApiError(error_text=self._t('contacts_only_for_sbt'))
        return func(self, *args, **kwargs)
    return decorator


class SbtContactsHandlerV1(AbsContactsHandler):

    @client_token_required()
    @sbt_client_required
    def _post(self, *args, **kwargs):
        return self._post_handler(*args, **kwargs)


def com_unity_client_required(func):
    def decorator(self, *args, **kwargs):
        _, op = get_reg_op(self.client_id, self.db_session)
        if op != 'com:unity':
            raise ApiError(error_text=self._t('contacts_only_for_com:unity'))
        return func(self, *args, **kwargs)
    return decorator


class ComUnityContactsHandlerV2(AbsContactsHandler):

    @client_token_required()
    @com_unity_client_required
    def _post(self, *args, **kwargs):
        return self._post_handler(*args, **kwargs)
