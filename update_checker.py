"""
update_checker.py
Система автообновлений HydroSphere.

Поддерживает:
- Проверку версий через REST API
- Скачивание обновлений
- Автоустановку с перезапуском
- Откат при ошибке

Использование:
    checker = UpdateChecker()
    result = checker.check_for_updates()
    if result:
        checker.download_and_install(result)
"""

import hashlib
import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

try:
    from version import (
        APP_NAME_EN,
        UPDATE_CHECK_INTERVAL_HOURS,
        UPDATE_SERVER_URL,
        VERSION_MAJOR,
        VERSION_MINOR,
        VERSION_PATCH,
        VERSION_STRING,
    )
except ImportError:
    VERSION_STRING = "1.0.0"
    VERSION_MAJOR = 1
    VERSION_MINOR = 0
    VERSION_PATCH = 0
    UPDATE_SERVER_URL = "https://api.example.com/hydrosphere"
    UPDATE_CHECK_INTERVAL_HOURS = 24
    APP_NAME_EN = "HydroSphere"


class UpdateInfo:
    """Информация о доступном обновлении."""

    def __init__(self, version: str, download_url: str, changelog: str = "",
                 size_bytes: int = 0, sha256: str = "",
                 min_version: str = "", release_date: str = ""):
        self.version = version
        self.download_url = download_url
        self.changelog = changelog
        self.size_bytes = size_bytes
        self.sha256 = sha256
        self.min_version = min_version
        self.release_date = release_date

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    @property
    def version_tuple(self) -> tuple[int, ...]:
        try:
            return tuple(int(x) for x in self.version.split("."))
        except (ValueError, AttributeError):
            return (0, 0, 0)

    def is_newer_than(self, current_version: str) -> bool:
        """Проверить, является ли эта версия новее текущей."""
        current_tuple = tuple(int(x) for x in current_version.split("."))
        return self.version_tuple > current_tuple


class UpdateState:
    """Состояние последней проверки обновлений."""

    STATE_FILE = "update_state.json"

    def __init__(self):
        self.last_check: datetime | None = None
        self.last_version: str = VERSION_STRING
        self.skipped_versions: list[str] = []
        self.auto_check_enabled: bool = True
        self._load()

    def _get_path(self) -> Path:
        app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(app_data) / APP_NAME_EN / self.STATE_FILE

    def _load(self):
        path = self._get_path()
        try:
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                self.last_check = datetime.fromisoformat(data.get("last_check", "")) if data.get("last_check") else None
                self.last_version = data.get("last_version", VERSION_STRING)
                self.skipped_versions = data.get("skipped_versions", [])
                self.auto_check_enabled = data.get("auto_check_enabled", True)
        except (json.JSONDecodeError, ValueError, OSError):
            pass

    def save(self):
        path = self._get_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "last_check": self.last_check.isoformat() if self.last_check else None,
                "last_version": self.last_version,
                "skipped_versions": self.skipped_versions,
                "auto_check_enabled": self.auto_check_enabled,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def should_check(self) -> bool:
        """Нужно ли проверять обновления (раз в N часов)."""
        if not self.auto_check_enabled:
            return False
        if self.last_check is None:
            return True
        elapsed = datetime.now() - self.last_check
        return elapsed > timedelta(hours=UPDATE_CHECK_INTERVAL_HOURS)


class UpdateChecker:
    """Основной класс проверки обновлений."""

    def __init__(self, server_url: str | None = None):
        self.server_url = server_url or UPDATE_SERVER_URL
        self.state = UpdateState()
        self._progress_callback = None
        self._cancel_flag = False

    def set_progress_callback(self, callback):
        """Установить callback для прогресса: callback(percent, message)."""
        self._progress_callback = callback

    def _report_progress(self, percent: float, message: str):
        if self._progress_callback:
            self._progress_callback(percent, message)

    def cancel(self):
        """Отменить текущую операцию."""
        self._cancel_flag = True

    def check_for_updates(self, force: bool = False) -> UpdateInfo | None:
        """
        Проверить наличие обновлений.

        Args:
            force: Проверять даже если недавно проверяли

        Returns:
            UpdateInfo если доступно обновление, None если нет
        """
        self._cancel_flag = False
        self._report_progress(0, "Проверка обновлений...")

        if not force and not self.state.should_check():
            return None

        try:
            self._report_progress(20, "Подключение к серверу...")
            info = self._fetch_update_info()

            if info is None:
                self.state.last_check = datetime.now()
                self.state.save()
                self._report_progress(100, "Обновлений нет")
                return None

            if not info.is_newer_than(VERSION_STRING):
                self.state.last_check = datetime.now()
                self.state.save()
                self._report_progress(100, "Уже последняя версия")
                return None

            if info.version in self.state.skipped_versions:
                self._report_progress(100, "Версия пропущена пользователем")
                return None

            self._report_progress(100, f"Доступно обновление: {info.version}")
            return info

        except Exception as e:
            self._report_progress(100, f"Ошибка проверки: {e}")
            return None

    def _fetch_update_info(self) -> UpdateInfo | None:
        """Получить информацию о доступных обновлениях с сервера."""
        try:
            if self._is_placeholder_url(self.server_url):
                return None

            url = f"{self.server_url}/version.json"
            req = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME_EN}/{VERSION_STRING}"})
            # Небольшой таймаут + ограничение DNS-резолва, чтобы не вешать приложение
            response = urllib.request.urlopen(req, timeout=5)
            data = json.loads(response.read().decode("utf-8"))

            return UpdateInfo(
                version=data.get("version", ""),
                download_url=data.get("download_url", ""),
                changelog=data.get("changelog", ""),
                size_bytes=data.get("size_bytes", 0),
                sha256=data.get("sha256", ""),
                min_version=data.get("min_version", ""),
                release_date=data.get("release_date", ""),
            )
        except (TimeoutError, urllib.error.URLError, json.JSONDecodeError, OSError, KeyError):
            return None

    @staticmethod
    def _is_placeholder_url(url: str) -> bool:
        """Пропустить заведомо нерабочие адреса (примеры, localhost)."""
        if not url:
            return True
        lowered = url.lower()
        for marker in ("example.com", "example.org", "example.net",
                       "localhost", "127.0.0.1", "0.0.0.0", "<your-server>"):
            if marker in lowered:
                return True
        return False

    def download_update(self, info: UpdateInfo, dest_dir: str | None = None) -> Path | None:
        """
        Скачать обновление.

        Returns:
            Путь к скачанному файлу или None при ошибке
        """
        self._cancel_flag = False

        if dest_dir is None:
            dest_dir = tempfile.mkdtemp(prefix="hydro_update_")

        dest_path = Path(dest_dir)
        filename = f"HydroSphere_{info.version}_Setup.exe"
        filepath = dest_path / filename

        try:
            self._report_progress(0, f"Скачивание {info.version}...")

            import urllib.error
            import urllib.request

            def _progress_hook(block_num, block_size, total_size):
                if self._cancel_flag:
                    raise InterruptedError("Отменено пользователем")
                if total_size > 0:
                    percent = min(100, block_num * block_size / total_size * 100)
                    self._report_progress(percent * 0.8,
                                          f"Скачивание: {percent:.0f}%")

            urllib.request.urlretrieve(info.download_url, str(filepath), _progress_hook)

            self._report_progress(80, "Проверка целостности...")

            if info.sha256:
                actual_hash = self._compute_sha256(filepath)
                if actual_hash.lower() != info.sha256.lower():
                    filepath.unlink()
                    self._report_progress(100, "Ошибка: файл повреждён")
                    return None

            self._report_progress(100, "Скачивание завершено")
            return filepath

        except InterruptedError:
            if filepath.exists():
                filepath.unlink()
            self._report_progress(100, "Скачивание отменено")
            return None
        except (urllib.error.URLError, OSError) as e:
            if filepath.exists():
                filepath.unlink()
            self._report_progress(100, f"Ошибка скачивания: {e}")
            return None

    def install_update(self, installer_path: Path) -> bool:
        """Запустить установщик обновления и закрыть приложение."""
        try:
            self._report_progress(0, "Запуск установщика...")

            # Запускаем установщик молча (тихая установка)
            cmd = [str(installer_path), "/SILENT", "/NORESTART"]
            subprocess.Popen(cmd, shell=False)

            self._report_progress(100, "Установщик запущен. Приложение будет закрыто.")

            # Даём время на запуск установщика
            import time
            time.sleep(2)

            # Закрываем текущее приложение
            self._report_progress(100, "Перезапуск...")
            return True

        except OSError as e:
            self._report_progress(100, f"Ошибка запуска: {e}")
            return False

    def skip_version(self, version: str):
        """Пропустить эту версию (не напоминать)."""
        if version not in self.state.skipped_versions:
            self.state.skipped_versions.append(version)
            self.state.save()

    def dismiss_update(self, info: UpdateInfo):
        """Отклонить обновление (показать в следующий раз)."""
        self.state.last_check = datetime.now()
        self.state.save()

    @staticmethod
    def _compute_sha256(filepath: Path) -> str:
        """Вычислить SHA-256 хеш файла."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


class ManualUpdateChecker:
    """Обёртка для использования из GUI без прямых импортов."""

    def __init__(self):
        self._checker = None

    def get_checker(self) -> UpdateChecker:
        if self._checker is None:
            self._checker = UpdateChecker()
        return self._checker

    def check_once(self) -> UpdateInfo | None:
        """Однократная проверка (для при запуске)."""
        checker = self.get_checker()
        return checker.check_for_updates(force=False)

    def check_now(self) -> UpdateInfo | None:
        """Принудительная проверка (из меню)."""
        checker = self.get_checker()
        return checker.check_for_updates(force=True)


# Глобальный экземпляр для использования в GUI
_updater = None


def get_updater() -> ManualUpdateChecker:
    global _updater
    if _updater is None:
        _updater = ManualUpdateChecker()
    return _updater


def check_for_updates() -> bool:
    """Совместимый интерфейс: проверить обновления при запуске."""
    updater = get_updater()
    result = updater.check_once()
    return result is not None
