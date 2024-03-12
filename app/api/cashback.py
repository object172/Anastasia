# -*- encoding: utf-8 -*-

import hashlib
import requests
import datetime
import settings
import json
import hashlib


__all__ = (
    'SbtCashbackApi',
    'CashbackApi'
)


MIN_UNIX_DT = datetime.datetime(1970, 1, 1, tzinfo=None)


def utc_datetime_to_timestamp(utc_dt):
    return int((utc_dt - MIN_UNIX_DT).total_seconds())


class SbtCashbackApi(object):

    def __init__(self, device_uid, msisdn, hash=None):
        msisdn = self._get_msisdn(msisdn)
        uid = device_uid + msisdn
        self.api = CashbackApi(uid, msisdn, hash=hash)
        self.offer_details = self.api.offer_details
        self.success_offers = self.api.success_offers
        self.available_offers = self.api.available_offers
        self.success_user_offers = self.api.success_user_offers

    @staticmethod
    def _get_msisdn(msisdn):
        if msisdn and not msisdn.startswith('7'):
            msisdn = '7' + msisdn
        return msisdn


class CashbackApi(object):

    try:
        API_KEY = settings.CASHBACK_API_KEY
    except:
        API_KEY = 'TEST_API_KEY'

    session = requests.Session()

    def __init__(
            self, uid, msisdn, hash=None,
            domain='https://api.rtm.sbt-tele.com', v='1'
    ):
        self.hash = hash or hashlib.sha1(uid).hexdigest()
        self.msisdn = msisdn
        self.base_url = u'{}/v{}'.format(domain, v)

    def _url(self, path, base_url=None, need_hash=True):
        url = '{}{}{}'.format(
            (base_url or self.base_url),
            path, self.hash if need_hash else ''
        )
        return url

    def success_user_offers(self, start_dt=None, end_dt=None):
        headers = {
            'Authorization': self.API_KEY,
            'Accept': 'application/json',
        }
        params = {}
        if start_dt:
            params['start'] = utc_datetime_to_timestamp(start_dt)
        if end_dt:
            params['stop'] = utc_datetime_to_timestamp(end_dt)

        r = self._get(
            '/success_user_offers/%s' % self.msisdn,
            headers=headers, need_hash=False,
            params=params or None,
        )
        try:
            return r.json()
        except Exception as err:
            try:
                print(err, str(r))
                print(r.text)
            except:
                pass
            raise err

    def success_offers(self):
        r = self._get('/success_offers/')
        return r.json()

    def available_offers(self):
        r = self._get('/available_offers/')
        return r.json()

    def offer_details(self, offer_id):
        r = self._get('/offer_details/', {"id": offer_id})
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 404:
            return None
        raise ValueError('offer(hash == {}; id={}): {}'.format(
            self.hash, offer_id, r.text
        ))

    def put_fcm_token(self, device, token):
        msisdn = device.client_id if device.client_id.startswith('7') else '7' + device.client_id
        device_id = hashlib.sha1(device.device_id + msisdn).hexdigest()
        headers = {
            "App": "SBDT/{}/{}".format(device.app_version, device.os),
        }
        r = self._put(
            '/token/{}'.format(device_id),
            data=json.dumps({'token': token}),
            headers=headers
        )
        return r

    def put_msisdn(self, device):
        msisdn = device.client_id if device.client_id.startswith('7') else '7' + device.client_id
        device_id = hashlib.sha1(device.device_id + msisdn).hexdigest()
        headers = {
            "App": "SBDT/{}/{}".format(device.app_version, device.os),
        }
        r = self._put(
            '/msisdn/{}'.format(device_id),
            data=json.dumps({'msisdn': msisdn}),
            headers=headers,
        )
        return r

    def _put(self, path, data, headers=None):
        HEADERS = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        }
        if headers:
            HEADERS.update(headers)
        return self.session.put(self._url(path, need_hash=False), data=data, headers=HEADERS)

    def _get(self, path, params=None, headers=None, need_hash=True):
        return self.session.get(self._url(path, need_hash=need_hash), params=params, headers=headers)

    def _post(self, path, data=None):
        return self.session.post(self._url(path), data=data)


if __name__ == '__main__':

    (device_uid, msisdn, hash) = ("295A9E28-9BB1-4E47-A989-55D9FE16D0D5", "9585931009", "cb5c084371efdaf493cf17333d067fcb0ef534b9")
    # (device_uid, msisdn, hash) = ("", "79957772475", "")

    api = SbtCashbackApi(device_uid, msisdn, hash)
    for offer in api.success_offers():
        print(offer)

    for offer in api.success_user_offers():
        print(offer)