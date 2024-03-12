# -*- encoding: utf-8 -*-

from app.api.bercut_mvno_api import MVNOApi as BercutMVNOApi


def MVNOApi():
    api = BercutMVNOApi()
    return api
