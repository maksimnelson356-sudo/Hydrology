"""
version.py
Централизованное управление версией приложения HydroSphere.

Версионирование: MAJOR.MINOR.PATCH
- MAJOR — крупные изменения (новые модули, несовместимые API)
- MINOR — новые функции, совместимые с предыдущими
- PATCH — исправления багов

Для сборки установщика: version.py не должен импортировать сторонние библиотеки.
"""

APP_NAME = "HydroSphere"
APP_NAME_EN = "HydroSphere"
APP_NAME_RU = "HydroSphere"
APP_DESCRIPTION = "Hydrological Statistics Platform"
APP_DESCRIPTION_RU = "Платформа гидрологической статистики"

VERSION_MAJOR = 1
VERSION_MINOR = 0
VERSION_PATCH = 0

VERSION_STRING = f"{VERSION_MAJOR}.{VERSION_MINOR}.{VERSION_PATCH}"
VERSION_FULL = f"{APP_NAME_EN} {VERSION_STRING}"

COPYRIGHT = "© 2026 HydroSphere Team"
COPYRIGHT_YEAR = 2026

UPDATE_SERVER_URL = "https://api.hydrosphere.app/v1/updates"
UPDATE_CHECK_INTERVAL_HOURS = 24

INSTALLER_PUBLISHER = "HydroSphere"
INSTALLER_URL = "https://hydrosphere.app"
