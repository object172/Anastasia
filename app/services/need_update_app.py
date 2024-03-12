# -*- encoding: utf-8 -*-

from distutils.version import LooseVersion


__all__ = ('get_need_update_app', )


def get_need_update_app(app_ver):
    if not app_ver:
        return None

    try:
        app_ver = LooseVersion(app_ver)
    except:
        return None

    if app_ver < "1.11.5":
        return {
            "forceAppUpdate": {
                "version": "1.11.5",
                "caption": "Доступна новая версия",
                "info": "- Обновили приложение\n- Обновили тарифы",
                "warning": "Доступ в приложение закрыт, пока вы не обновитесь",
            }
        }
    return None
