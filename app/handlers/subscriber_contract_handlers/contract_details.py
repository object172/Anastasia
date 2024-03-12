# -*- encoding: utf-8 -*-

import datetime

from app.handlers import BaseHandler
from app.services import get_subscriber_contract_data
from app.wrappers import client_token_required


__all__ = ('SubscriberContractDetailsHandler', )


class SubscriberContractDetailsHandler(BaseHandler):

    @client_token_required()
    def _post(self, *args, **kwargs):
        if not self.client:
            return {}

        contract_data = get_subscriber_contract_data(self.client)

        if contract_data.get('birthdate'):
            contract_data['birthdate'] = contract_data['birthdate'].strftime('%d.%m.%Y')

        if contract_data.get('issued'):
            contract_data['issued'] = contract_data['issued'].strftime('%d.%m.%Y')

        print('contract_data')

        return contract_data
