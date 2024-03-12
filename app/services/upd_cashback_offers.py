# -*- encoding: utf-8 -*-

from app.api import SbtCashbackApi
from app.models import Cashback
from app_models import DeviceData


__all__ = ('upd_cashback_offers', )


def upd_cashback_offers(db_session, number, start_dt=None, end_dt=None):
    (device_id, device_uid) = db_session.query(
        DeviceData.id, DeviceData.device_id
    ).distinct(
        DeviceData.device_id
    ).filter(
        DeviceData.client_id == number,
        DeviceData.device_id != None,
    ).order_by(
        DeviceData.device_id,
        DeviceData.id.desc()
    ).first() or (None, None)

    if not device_uid:
        return

    try:
        api = SbtCashbackApi(device_uid, number)
        success_offers = api.api.success_user_offers(
            start_dt=start_dt, end_dt=end_dt
        )

        if not success_offers:
            return

        available_offers = dict(
            (of["name"], of)
            for of in api.available_offers()
        )
    except:
        return

    closed_cashbacks_items_data = [
        item.data for item in db_session.query(
            Cashback.data,
        ).filter(
            Cashback.status != Cashback.STATUS_OPEN,
            Cashback.client_id == number,
            Cashback.deleted == None,
        ).all()
    ]

    closed_cashbacks = set((
        (cacheback_data or {}).get('offer_name'),
        (cacheback_data or {}).get('click_tm'),
    ) for cacheback_data in closed_cashbacks_items_data)

    opened_cashbacks = dict(
        ((c.name, c.clicked), c)
        for c in db_session.query(Cashback).filter(
            Cashback.status == Cashback.STATUS_OPEN,
            Cashback.client_id == number,
            Cashback.deleted == None,
        ).all()
    )

    for offer in success_offers:
        offer_key = (offer['offer_name'], offer['click_tm'])
        if offer_key in opened_cashbacks:
            if offer['status'] == 'open':
                continue

            cashback = opened_cashbacks.get(offer_key)
            cashback.amount = offer['amount']
            cashback.status = offer['status']
            cashback.save(db_session, commit=False)

        elif offer_key in closed_cashbacks:
            continue

        else:
            cashback = Cashback(
                client_id=number,
            )

            if offer.get("offer_name") in available_offers:
                offer.update(available_offers[offer["offer_name"]])

            if offer.get("id"):
                offer_details = api.offer_details(offer['id'])
                if offer_details:
                    offer['reward_delay'] = offer_details['reward_delay']

            cashback.data = offer
            cashback.device_id = device_id
            cashback.save(db_session, commit=False)

    db_session.commit()
