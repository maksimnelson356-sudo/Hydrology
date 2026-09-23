"""
gui/dialogs/api_import_dialog.py
Диалог импорта ряда из HTTP API (P1.2, DOCS/ROADMAP.md).

URL источника + id поста → `HttpApiSource.fetch_series` в фоновом воркере →
`dataset_ready` (тот же path, что у файлового импорта: проект + QualityPipeline).
Диалог не лечит данные и не считает качество — это делает MainWindow.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.domain.models import Dataset
from core.services.api_source import ApiSourceError, HttpApiSource

try:
    from i18n import t
except Exception:  # pragma: no cover - i18n optional at early bootstrap

    def t(key: str, fallback: str = "") -> str:
        return fallback


TITLE_STYLE = "font-size: 15px; font-weight: bold; color: #0D47A1;"
HINT_STYLE = (
    "color: #666; font-style: italic; padding: 6px; "
    "background: #f0f0f0; border-radius: 4px;"
)


class ApiImportWorker(QThread):
    """Fetch a series off the UI thread."""

    ready = pyqtSignal(object)  # Dataset
    failed = pyqtSignal(str)

    def __init__(
        self,
        base_url: str,
        post_id: str,
        *,
        name: str = "",
        unit: str = "m³/s",
        location: str = "",
        timeout: float = 10.0,
        retries: int = 2,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_url = base_url
        self._post_id = post_id
        self._name = name
        self._unit = unit
        self._location = location
        self._timeout = timeout
        self._retries = retries

    def run(self) -> None:  # noqa: D102 - QThread entry
        try:
            source = HttpApiSource(
                self._base_url,
                timeout=self._timeout,
                retries=self._retries,
            )
            dataset = source.fetch_series(
                self._post_id,
                name=self._name,
                unit=self._unit,
                location=self._location,
            )
        except ApiSourceError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # surface to dialog, never crash the app
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.ready.emit(dataset)


class ApiImportDialog(QDialog):
    """Мастер: URL + id поста → Dataset (provenance в metadata)."""

    dataset_ready = pyqtSignal(object)  # Dataset

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("api_import_title", "Импорт из источника (API)"))
        self.setMinimumSize(640, 480)
        self._worker: ApiImportWorker | None = None
        self._progress: QProgressDialog | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(t("api_import_title", "Импорт из источника (API)"))
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            t(
                "api_import_hint",
                "Ряд загружается по HTTP без файла: пропуски остаются "
                "пропусками, provenance пишется в метаданные набора.",
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        layout.addWidget(hint)

        form_group = QGroupBox(t("api_import_settings", "Параметры источника"))
        form = QFormLayout(form_group)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText(
            t("api_url_placeholder", "https://api.example.test/series")
        )
        self._post_edit = QLineEdit()
        self._post_edit.setPlaceholderText(
            t("api_post_placeholder", "Идентификатор поста…")
        )
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(
            t("import_name_placeholder", "Название ряда…")
        )
        self._unit_edit = QLineEdit("m³/s")
        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText(
            t("import_location_placeholder", "Река / бассейн (необязательно)")
        )
        self._timeout_edit = QLineEdit("10")
        self._timeout_edit.setPlaceholderText("10")
        self._retries_edit = QLineEdit("2")
        self._retries_edit.setPlaceholderText("2")

        form.addRow(t("api_base_url", "URL:") + ":", self._url_edit)
        form.addRow(t("api_post_id", "Пост:") + ":", self._post_edit)
        form.addRow(t("import_name", "Название:") + ":", self._name_edit)
        form.addRow(t("import_unit", "Единицы:") + ":", self._unit_edit)
        form.addRow(t("import_location", "Объект:") + ":", self._location_edit)
        form.addRow(t("api_timeout", "Таймаут, с:") + ":", self._timeout_edit)
        form.addRow(t("api_retries", "Повторы:") + ":", self._retries_edit)
        layout.addWidget(form_group)

        preview_group = QGroupBox(t("preview_group", "Предпросмотр"))
        preview_layout = QVBoxLayout(preview_group)
        self._preview_text = QPlainTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumBlockCount(80)
        self._preview_text.setPlaceholderText(
            t(
                "api_preview_placeholder",
                "Нажмите «Получить», чтобы увидеть первые строки ряда…",
            )
        )
        preview_layout.addWidget(self._preview_text)
        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet("color: #666; font-size: 11px;")
        preview_layout.addWidget(self._meta_label)
        layout.addWidget(preview_group, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._btn_cancel = QPushButton(t("btn_cancel", "Отмена"))
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_fetch = QPushButton(t("api_fetch", "Получить"))
        self._btn_fetch.clicked.connect(self._on_fetch)
        self._btn_import = QPushButton(t("api_import_run", "Импортировать"))
        self._btn_import.setEnabled(False)
        self._btn_import.clicked.connect(self._on_import)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_fetch)
        buttons.addWidget(self._btn_import)
        layout.addLayout(buttons)

        self._dataset: Dataset | None = None

    def _validated_params(self) -> dict[str, Any] | None:
        base_url = self._url_edit.text().strip()
        post_id = self._post_edit.text().strip()
        if not base_url or not post_id:
            QMessageBox.warning(
                self,
                t("api_import_title", "Импорт из источника (API)"),
                t("api_pick_url_post", "Укажите URL источника и id поста."),
            )
            return None
        try:
            timeout = float(self._timeout_edit.text().strip() or "10")
            retries = int(self._retries_edit.text().strip() or "2")
        except ValueError:
            QMessageBox.warning(
                self,
                t("api_import_title", "Импорт из источника (API)"),
                t("api_bad_timeout", "Таймаут и повторы должны быть числами."),
            )
            return None
        if timeout <= 0 or timeout > 120:
            QMessageBox.warning(
                self,
                t("api_import_title", "Импорт из источника (API)"),
                t("api_timeout_range", "Таймаут должен быть в 0…120 секунд."),
            )
            return None
        if retries < 0 or retries > 5:
            QMessageBox.warning(
                self,
                t("api_import_title", "Импорт из источника (API)"),
                t("api_retries_range", "Повторы должны быть 0…5."),
            )
            return None
        name = self._name_edit.text().strip() or post_id
        return {
            "base_url": base_url,
            "post_id": post_id,
            "name": name,
            "unit": self._unit_edit.text().strip() or "m³/s",
            "location": self._location_edit.text().strip(),
            "timeout": timeout,
            "retries": retries,
        }

    def _on_fetch(self) -> None:
        params = self._validated_params()
        if params is None:
            return
        self._dataset = None
        self._btn_import.setEnabled(False)
        self._preview_text.clear()

        self._progress = QProgressDialog(
            t("api_fetching", "Загрузка из источника…"), None, 0, 0, self
        )
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setValue(0)

        self._worker = ApiImportWorker(
            params["base_url"],
            params["post_id"],
            name=params["name"],
            unit=params["unit"],
            location=params["location"],
            timeout=params["timeout"],
            retries=params["retries"],
        )
        self._worker.ready.connect(self._on_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_ready(self, dataset: object) -> None:
        self._close_progress()
        self._btn_import.setEnabled(True)
        if not isinstance(dataset, Dataset):
            QMessageBox.critical(
                self,
                t("api_import_title", "Импорт из источника (API)"),
                t("import_failed", "Импорт завершился некорректным результатом."),
            )
            return
        self._dataset = dataset
        years = dataset.years
        lines = [f"{y}: {dataset.data[y]}" for y in years[:20]]
        if len(years) > 20:
            lines.append(f"… ещё {len(years) - 20}")
        self._preview_text.setPlainText("\n".join(lines))
        source_url = str(dataset.metadata.get("source_url", ""))
        self._meta_label.setText(
            f"точек: {dataset.length} · {dataset.start_year}–{dataset.end_year} · {source_url}"
        )

    def _on_failed(self, message: str) -> None:
        self._close_progress()
        self._btn_import.setEnabled(False)
        self._dataset = None
        QMessageBox.critical(
            self,
            t("api_import_title", "Импорт из источника (API)"),
            message or t("import_failed", "Не удалось получить данные."),
        )

    def _on_import(self) -> None:
        if self._dataset is None:
            return
        self.dataset_ready.emit(self._dataset)
        self.accept()

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None

    def done(self, result: int) -> None:  # noqa: D102 - QDialog override
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(3000)
        super().done(result)
