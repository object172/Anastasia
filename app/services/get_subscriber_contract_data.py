# -*- encoding: utf-8 -*-

from app_sbtelecom.api.sbt_bercut_billing_api import SbtBercutBillingApi
from app_regions.services import get_region_name_by_dt_id

__all__ = (
    'get_subscriber_contract_data',
)


def get_subscriber_contract_data(client=None, number=None):
    u"""
        return {
            fio: "Суй Во Чай",
            sex: "Муж"/"Жен",
            birthdate: "12.12.2000",
            birthplace: "Москва, бла, бла, бла",
            citizenship: "РФ",
            doctype: "Паспорт РФ",
            serial: null | "1234",
            docid: "12345678",
            ufmscode: "123456",
            issuer: "Загс ...",
            issued: "21.12.2112",
            address: "ул. Строителей,...",
        }
    """

    region = client and get_region_name_by_dt_id(client.region)
    return _get_subscriber_contract_bercut_data((client and client.number) or number, region)


BERCUT_GENDER_MAPPING = {
    0: u'Муж',
    1: u'Жен',
}


BERCUT_DOCTYPE_MAPPING = {
    u'Паспорт': u'Паспорт РФ',
    u'Иностранный паспорт': u'Паспорт иностранного гражданина',
    u'Вид на жительство': u'Вид на жительство лица без гражданства',
    u'Удостоверение беж.': u'Удостоверение беженца',
    u'Свидетельство о предоставлении временного убежища': u'Свидетельство о предоставлении временного убежища',
}

u"""
BERCUT DOCTYPE CODES:
    "1": "Паспорт",
    "2": "Иностранный паспорт",
    "3": "Удостоверение",
    "4": "Разрешение",
    "5": "Вид на жительство",
    "7": "Свидетельство",
    "8": "Иной документ",
    "9": "Удостоверение беж.",
    "24": "Свид-во о рег-ции",

ПОДКЛЮЧИ DOCTYPE MAPPING:
    'Паспорт РФ': 1,
    'Временное удостоверение личности гражданина РФ': 8,
    'Паспорт иностранного гражданина': 2,
    'Удостоверение личности моряка': 8,
    'Дипломатический паспорт': 8,
    'Вид на жительство лица без гражданства': 5,
    'Удостоверение беженца': 9,
    'Свидетельство о предоставлении временного убежища': 8,
    'Военное удостоверение': 8,
"""


BERCUT_CITIZENSHIP_MAPPING = {
    u"Россия": u"РФ"
}


def _get_subscriber_contract_bercut_data(number, region):
    u"""
    api.getContract() == {
        "personalProfileData": {
            "genderId": "0",
            "dateOfBirth": "1991-08-13T00:00:00.000+03:00",
            "fullName": "Блесков Георгий",
            "identityDocument": {
                "identityDocumentName": "Паспорт",
                "series": "7777",
                "country": "Инмарсат",
                "dateOfIssue": "2011-10-11T00:00:00.000+04:00",
                "number": "123456",
                "authority": "ОУФМС"
            },
            "registrationAddress": {
                "building": "12",
                "city": "Москва",
                "postIndex": "123456",
                "street": "вавилова",
                "house": "12",
                "country": "Россия"
            }
        },
    }
    """
    response = {}
    api = SbtBercutBillingApi(number=number, region=region)
    try:
        data = api.getContract()
        personal_data = data.get("personalProfileData") or {}

        response["fio"] = personal_data.get("fullName") or ''

        gender_id = personal_data.get("genderId")
        gender_id = gender_id and int(gender_id)
        response["sex"] = BERCUT_GENDER_MAPPING.get(gender_id) or ''

        response["birthdate"] = api.strptime(personal_data.get("dateOfBirth")) or ''
        response["birthplace"] = ''

        document_data = personal_data.get("identityDocument") or {}

        citizenship = document_data.get("country") or ''
        response["citizenship"] = citizenship and BERCUT_CITIZENSHIP_MAPPING.get(
            citizenship, citizenship
        )

        doctype = document_data.get("identityDocumentName") or ''
        response["doctype"] = doctype and BERCUT_DOCTYPE_MAPPING.get(doctype) or ''

        response["serial"] = document_data.get('series')
        response["docid"] = document_data.get('number') or ''
        response["ufmscode"] = ''
        response["issuer"] = document_data.get('authority') or ''
        response["issued"] = api.strptime(document_data.get('dateOfIssue')) or ''

        address_data = personal_data.get("registrationAddress") or {}

        post_index = address_data.get('postIndex')
        country = address_data.get('country')
        city = address_data.get('city')
        street = address_data.get('street')
        house = address_data.get('house')

        address = u', '.join(filter(bool, [country, post_index, city, street, house]))
        response["address"] = address
    except Exception as err:
        try:
            print(err)
        except Exception as e:
            print(e)

    return response
