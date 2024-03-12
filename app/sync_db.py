# -*- coding: utf-8 -*-

import traceback

import __import_utils__
with __import_utils__.up_import(1):
    from app_utils.db_utils import get_dbengine, create_dbsession
    import app.services
    from app.models import AppDeclBase


class SyncDB(object):

    def __init__(self, db_engine=None, db_session=None):
        self.db_engine = db_engine or get_dbengine()
        self.db_session = db_session or create_dbsession()

    def handler(self):
        self.create_all_models()

    def create_all_models(self):
        AppDeclBase.metadata.create_all(self.db_engine)
        # ...

        self.db_session.commit()


if __name__ == '__main__':
    SyncDB().handler()
