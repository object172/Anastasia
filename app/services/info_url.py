# -*- encoding: utf-8 -*-
from app_regions.services import is_full_region_dt_id
from settings import SBT_BASE_TARIFF_PDF

__all__ = (
    'get_info_url',
)

def get_info_url(region, tariff_obj=None):
    if (region, tariff_obj and tariff_obj.segment) in SBT_BASE_TARIFF_PDF:
        return SBT_BASE_TARIFF_PDF[(region, tariff_obj.segment)]

    if (region, tariff_obj and tariff_obj.name) in SBT_BASE_TARIFF_PDF:
        return SBT_BASE_TARIFF_PDF[(region, tariff_obj.name)]

    if (region, tariff_obj and tariff_obj.id) in SBT_BASE_TARIFF_PDF:
        return SBT_BASE_TARIFF_PDF[(region, tariff_obj.id)]

    reg_type = 'full' if is_full_region_dt_id(region) else 'medium'

    if (reg_type, tariff_obj and tariff_obj.name) in SBT_BASE_TARIFF_PDF:
        return SBT_BASE_TARIFF_PDF[(reg_type, tariff_obj.name)]

    if reg_type in SBT_BASE_TARIFF_PDF:
        return SBT_BASE_TARIFF_PDF[reg_type]

    return SBT_BASE_TARIFF_PDF.get(region)