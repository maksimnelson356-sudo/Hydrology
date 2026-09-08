"""
i18n/__init__.py
Система переводов HydroSphere.
Поддерживает ru/en. Язык по умолчанию — русский.
"""

import json
import os
from typing import Dict

_current_lang = "ru"
_translations: dict[str, dict] = {}
_interface_translations: dict[str, dict] = {}


def _load_lang(lang_code: str) -> dict:
    lang_file = os.path.join(os.path.dirname(__file__), f'{lang_code}.json')
    try:
        with open(lang_file, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def set_language(lang_code: str):
    global _current_lang, _translations, _interface_translations
    _current_lang = lang_code
    _translations = _load_lang(lang_code)
    _interface_translations = _load_lang(lang_code)


def t(key: str, fallback: str = "") -> str:
    """Получить перевод по ключу.
    
    Использование в виджетах:
        from i18n import t
        self.btn.setText(t("btn_fill", "Заполнить пропуски"))
    """
    return _translations.get(key, fallback)


def tr(key: str, fallback: str = "") -> str:
    """Алиас для t() — краткая форма."""
    return t(key, fallback)


def get_translator(lang_code: str = None) -> dict[str, str]:
    if lang_code is None:
        lang_code = _current_lang
    return _load_lang(lang_code)


def get_available_languages() -> list:
    """Вернуть список доступных языков."""
    return [f[:-5] for f in os.listdir(os.path.dirname(__file__)) if f.endswith('.json')]


# Автоматическая загрузка русского при импорте
set_language("ru")
