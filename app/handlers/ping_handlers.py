# -*- encoding: utf-8 -*-

import datetime

from app.handlers import BaseHandler

from app_utils.db_utils import create_dbsession
from app_utils.json_utils import json
from app_utils.os_utils import get_system_stats
from app_utils.redis_utils import create_redis_session


__all__ = ('PingHandler', )


class PingHandler(BaseHandler):

    CHANGE_TARIFF_MAX_QUEUE_LENGTH = 20
    PAYMENTS_MAX_QUEUE_LENGTH = 20
    FAVOURITES_NUMBERS_MAX_QUEUE_LENGTH = 20
    THREADS_MAX_COUNT = 8000

    def _get(self, *args, **kwargs):
        utcnow = datetime.datetime.utcnow()
        errors = []

        try:
            db_session = create_dbsession()
        except Exception as err:
            error = "Failed to connect to database: {}".format(err)
            self.alarm.alarm(error)
            errors.append(error)
        finally:
            try:
                db_session.close()
            except:
                pass

        try:
            redis = create_redis_session()
        except Exception as err:
            error = "Failed to connect to redis: {}".format(err)
            self.alarm.alarm(error)
            errors.append(error)
        finally:
            try:
                redis.connection_pool.disconnect()
            except:
                pass

        last_worker_check = redis.get('worker_check_datetime')
        last_worker_check = last_worker_check and datetime.datetime.strptime(
            last_worker_check,
            u'%Y-%m-%dT%H:%M:%S'
        )
        if last_worker_check and last_worker_check < utcnow - datetime.timedelta(hours=1):
            error = 'worker checking service is not working for {}'.format(str(utcnow-last_worker_check))
            self.alarm.alarm(error)
            errors.append(error)
        #
        # queue_orders_length = redis.get('worker:change_tariff')
        # if queue_orders_length is None:
        #     error = 'worker:change_tariff is not working'
        #     self.alarm.alarm(error)
        #     errors.append(error)
        # elif int(queue_orders_length) > self.CHANGE_TARIFF_MAX_QUEUE_LENGTH:
        #     error = 'worker:change_tariff: queue is too long: {} > {}'.format(
        #         queue_orders_length, self.CHANGE_TARIFF_MAX_QUEUE_LENGTH
        #     )
        #     self.alarm.error(error)
        #     # errors.append(error)
        #
        # total_threads = get_system_stats()['threads'].get('total')
        # if total_threads is None:
        #     self.alarm.error("can't get threads counts")
        # elif total_threads > self.THREADS_MAX_COUNT:
        #     error = 'too many threads: {} > {}'.format(
        #         total_threads, self.THREADS_MAX_COUNT
        #     )
        #     self.alarm.alarm(error)
        #     errors.append(error)
        #
        # queue_orders_length = redis.get('worker:payments')
        # if queue_orders_length is None:
        #     error = 'worker:payments is not working'
        #     self.alarm.alarm(error)
        #     errors.append(error)
        # elif int(queue_orders_length) > self.PAYMENTS_MAX_QUEUE_LENGTH:
        #     error = 'worker:payments: queue is too long: {} > {}'.format(
        #         queue_orders_length, self.PAYMENTS_MAX_QUEUE_LENGTH
        #     )
        #     self.alarm.alarm(error)
        #     # errors.append(error)
        #
        # queue_orders_length = redis.get('worker:favourites_numbers')
        # if queue_orders_length is None:
        #     error = 'worker:favourites_numbers is not working'
        #     self.alarm.alarm(error)
        #     errors.append(error)
        # elif int(queue_orders_length) > self.FAVOURITES_NUMBERS_MAX_QUEUE_LENGTH:
        #     error = 'worker:favourites_numbers: queue is too long: {} > {}'.format(
        #         queue_orders_length, self.FAVOURITES_NUMBERS_MAX_QUEUE_LENGTH
        #     )
        #     self.alarm.error(error)
        #     # errors.append(error)
        #
        # bdpn_started = redis.get('alarm:bdpn_all')
        # if bdpn_started is None:
        #     error = 'alarm:bdpn_parser not started > 1h'
        #     if utcnow.hour >= 5 and utcnow.hour < 21:
        #         self.alarm.alarm(error)
        #         errors.append(error)
        #     else:
        #         self.alarm.error(error)
        #         # errors.append(error)

        if errors:
            return dict(result=1, errors=errors)
        return dict(result=1)
