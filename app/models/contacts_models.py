# -*- encoding: utf-8 -*-

import datetime

from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy import (
    or_ as sql_or
)
from app_utils.db_utils import IS_ORACLE_DB
from app_utils.db_utils.models import JSONB

from app_models import Client_lk, DeviceData
from app.models.mixins import (
    AppDeclBase, BaseModel, jsonb_property
)

from app_utils.wrappers import memorizing
from methods_simple import (
    normalize_number_to_number,
    normalize_number_to_msisdn
)


__all__ = (
    'Contact',
)


class Contact(AppDeclBase, BaseModel):
    __tablename__ = "contacts"

    NO_ID_SEQUENCE = True
    id = Column(Integer, primary_key=True, autoincrement=(not IS_ORACLE_DB))
    device_uid = Column(String, primary_key=True, index=True)

    client_id = Column(String, primary_key=IS_ORACLE_DB, index=True)
    number = Column(
        String, index=True, primary_key=IS_ORACLE_DB,
        name='number_' if IS_ORACLE_DB else 'number'
    )
    operator = Column(String, index=True)
    region = Column(Integer, index=True)

    calls_available = Column(Boolean, default=False, index=True)

    data = Column(JSONB, default={})

    created = Column(
        DateTime,  # primary_key=IS_ORACLE_DB,
        default=datetime.datetime.utcnow
    )
    updated = Column(DateTime, default=datetime.datetime.utcnow)
    deleted = Column(DateTime)

    info = jsonb_property('data', 'info')

    def save(self, db_session, commit=True):
        self.updated = datetime.datetime.utcnow()
        return super(Contact, self).save(db_session, commit=commit)

    def delete(self, db_session, commit=True):
        self.deleted = datetime.datetime.utcnow()
        return self.save(db_session, commit=commit)

    @property
    def is_deleted(self):
        return bool(self.deleted)

    @classmethod
    def calls_available_for_client(
            cls, db_session,
            client=None, client_id=None,
            device_data=None
    ):
        if (
                client is not None and (
                    not client.has_sbtelecom_operator or (
                        not client.get_data('caller_login') and
                        not client.get_data('caller_login_s') and
                        not client.get_data('caller_login_h')
                    )
                )
        ):
            return False

        if client is None:

            client_id = client_id and normalize_number_to_number(unicode(client_id))
            if not client_id:
                raise ValueError('need client or valid client_id')

            client = db_session.query(Client_lk).filter(
                Client_lk.operator.in_(Client_lk.sbTELECOM_OPERATORS)
            ).filter_by(number=client_id).first()

            if (
                    client is None or
                    not client.has_sbtelecom_operator or (
                        not client.get_data('caller_login') and
                        not client.get_data('caller_login_s') and
                        not client.get_data('caller_login_h')
                    )
            ):
                return False

        if device_data is not None:
            return device_data.os in ['android', 'ios']

        calls_available = db_session.query(DeviceData.id).filter_by(
            client_id=client.number,
        ).filter(sql_or(
            DeviceData.os == 'android',
            DeviceData.os == 'ios'
        )).first() is not None

        return calls_available

    @classmethod
    def update(cls, db_session, number, **kwargs):
        update_data = dict()
        filters = []

        number = number and normalize_number_to_msisdn(unicode(number))
        if not number:
            raise ValueError(u'need valid number')

        if kwargs.get('calls_available') is not None:
            update_data['calls_available'] = kwargs['calls_available']
            filters.append(Contact.calls_available != bool(update_data['calls_available']))

        if kwargs.get('operator') is not None:
            update_data['operator'] = kwargs['operator']
            filters.append(Contact.operator != update_data['operator'])

        if kwargs.get('region') is not None:
            update_data['region'] = kwargs['region']
            filters.append(Contact.region != update_data['region'])

        if update_data:
            update_data['updated'] = datetime.datetime.utcnow()

            db_query = db_session.query(cls).filter_by(number=number)

            if len(filters) == 1:
                db_query = db_query.filter(filters[0])

            elif len(filters) > 1:
                db_query = db_query.filter(sql_or(*filters))

            db_query.update(update_data, synchronize_session='fetch')
            db_session.commit()

            return True
        return False
