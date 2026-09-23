"""
gui/dialogs/import_dialog.py
Диалог импорта ряда (P1.1, DOCS/ROADMAP.md).

Выбор файла CSV/TSV/Excel → предпросмотр колонок → маппинг год/значение →
`ImportService` в фоновом воркере. Диалог не считает качество: после импорта
MainWindow запускает `DataQualityService` отдельно (только отчёт).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
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
from core.services.import_service import (
    ColumnMapping,
    ImportPreview,
    ImportService,
    ImportServiceError,
)

try:
    from i18n import t
except Exception:  # pragma: no cover - i18n optional at early bootstrap

    def t(key: str, fallback: str = "") -> str:
        return fallback


FILE_FILTER = (
    "Данные (*.csv *.tsv *.txt *.xlsx *.xls);;"
    "CSV (*.csv);;TSV (*.tsv);;Excel (*.xlsx *.xls);;Все (*)"
)

TITLE_STYLE = "font-size: 15px; font-weight: bold; color: #0D47A1;"
HINT_STYLE = (
    "color: #666; font-style: italic; padding: 6px; "
    "background: #f0f0f0; border-radius: 4px;"
)


class ImportWorker(QThread):
    """Build a Dataset off the UI thread."""

    ready = pyqtSignal(object)  # Dataset
    failed = pyqtSignal(str)

    def __init__(
        self,
        path: str,
        mapping: ColumnMapping,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._mapping = mapping

    def run(self) -> None:  # noqa: D102 - QThread entry
        try:
            dataset = ImportService().import_file(self._path, self._mapping)
        except ImportServiceError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # surface to dialog, never crash the app
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.ready.emit(dataset)


class ImportDialog(QDialog):
    """Мастер: файл → предпросмотр → маппинг → Dataset."""

    dataset_ready = pyqtSignal(object)  # Dataset

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("import_title", "Импорт ряда (CSV / Excel)"))
        self.setMinimumSize(720, 520)
        self._service = ImportService()
        self._preview: ImportPreview | None = None
        self._worker: ImportWorker | None = None
        self._progress: QProgressDialog | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(t("import_title", "Импорт ряда (CSV / Excel)"))
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            t(
                "import_hint",
                "Файл разбирается без «лечения» данных: пропуски остаются "
                "пропусками, качество проверяется отдельным отчётом.",
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        layout.addWidget(hint)

        # --- file ---
        file_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        self._path_edit.setPlaceholderText(t("import_path_placeholder", "Файл не выбран…"))
        browse = QPushButton(t("import_browse", "Обзор…"))
        browse.clicked.connect(self._on_browse)
        file_row.addWidget(QLabel(t("import_file", "Файл:")))
        file_row.addWidget(self._path_edit, 1)
        file_row.addWidget(browse)
        layout.addLayout(file_row)

        # --- mapping ---
        map_group = QGroupBox(t("import_mapping", "Сопоставление колонок"))
        form = QFormLayout(map_group)
        self._year_combo = QComboBox()
        self._value_combo = QComboBox()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(t("import_name_placeholder", "Название ряда…"))
        self._unit_edit = QLineEdit("m³/s")
        self._location_edit = QLineEdit()
        self._location_edit.setPlaceholderText(t("import_location_placeholder", "Река / бассейн (необязательно)"))
        form.addRow(t("label_year", "Год") + ":", self._year_combo)
        form.addRow(t("label_value", "Значение") + ":", self._value_combo)
        form.addRow(t("import_name", "Название:") + ":", self._name_edit)
        form.addRow(t("import_unit", "Единицы:") + ":", self._unit_edit)
        form.addRow(t("import_location", "Объект:") + ":", self._location_edit)
        layout.addWidget(map_group)

        # --- preview ---
        preview_group = QGroupBox(t("preview_group", "Предпросмотр"))
        preview_layout = QVBoxLayout(preview_group)
        self._preview_text = QPlainTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumBlockCount(80)
        self._preview_text.setPlaceholderText(
            t("import_preview_placeholder", "Выберите файл, чтобы увидеть первые строки…")
        )
        preview_layout.addWidget(self._preview_text)
        self._meta_label = QLabel("")
        self._meta_label.setStyleSheet("color: #666; font-size: 11px;")
        preview_layout.addWidget(self._meta_label)
        layout.addWidget(preview_group, 1)

        # --- buttons ---
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._btn_cancel = QPushButton(t("btn_cancel", "Отмена"))
        self._btn_cancel.clicked.connect(self.reject)
        self._btn_import = QPushButton(t("import_run", "Импортировать"))
        self._btn_import.setEnabled(False)
        self._btn_import.clicked.connect(self._on_import)
        buttons.addWidget(self._btn_cancel)
        buttons.addWidget(self._btn_import)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------
    # File / preview
    # ------------------------------------------------------------------
    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("import_browse", "Обзор…"), "", FILE_FILTER
        )
        if not path:
            return
        self._load_preview(path)

    def _load_preview(self, path: str) -> None:
        try:
            preview = self._service.preview(path)
        except ImportServiceError as exc:
            QMessageBox.critical(self, t("import_title", "Импорт ряда"), str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            QMessageBox.critical(
                self,
                t("import_title", "Импорт ряда"),
                f"{type(exc).__name__}: {exc}",
            )
            return

        self._preview = preview
        self._path_edit.setText(preview.path)
        name = Path(preview.path).stem
        if not self._name_edit.text().strip():
            self._name_edit.setText(name)

        self._year_combo.clear()
        self._value_combo.clear()
        self._year_combo.addItems(preview.columns)
        self._value_combo.addItems(preview.columns)
        if preview.year_column in preview.columns:
            self._year_combo.setCurrentText(preview.year_column)
        if preview.value_column in preview.columns:
            self._value_combo.setCurrentText(preview.value_column)

        lines: list[str] = []
        if preview.columns:
            lines.append(" | ".join(str(c) for c in preview.columns))
            lines.append("-" * min(72, max(12, sum(len(str(c)) + 3 for c in preview.columns))))
        for row in preview.rows[:15]:
            lines.append(" | ".join(str(cell) for cell in row))
        self._preview_text.setPlainText("\n".join(lines))

        meta_bits = [f"строк ≈ {preview.n_rows_estimate}"]
        if preview.sheet_names:
            meta_bits.append(f"листов: {len(preview.sheet_names)}")
        if preview.delimiter:
            meta_bits.append(f"разделитель: {preview.delimiter!r}")
        meta_bits.append(f"кодировка: {preview.encoding}")
        self._meta_label.setText(" · ".join(meta_bits))
        self._btn_import.setEnabled(True)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------
    def _on_import(self) -> None:
        if self._preview is None:
            return
        year_col = self._year_combo.currentText().strip()
        value_col = self._value_combo.currentText().strip()
        name = self._name_edit.text().strip() or Path(self._preview.path).stem
        if not year_col or not value_col:
            QMessageBox.warning(
                self,
                t("import_title", "Импорт ряда"),
                t("import_pick_columns", "Выберите колонки года и значения."),
            )
            return
        if year_col == value_col:
            QMessageBox.warning(
                self,
                t("import_title", "Импорт ряда"),
                t("import_same_columns", "Колонки года и значения должны отличаться."),
            )
            return

        mapping = ColumnMapping(
            year_column=year_col,
            value_column=value_col,
            name=name,
            unit=self._unit_edit.text().strip() or "m³/s",
            location=self._location_edit.text().strip(),
            sheet_name=self._preview.sheet_name,
            delimiter=self._preview.delimiter,
            encoding=self._preview.encoding,
        )

        self._progress = QProgressDialog(
            t("import_running", "Импорт ряда…"), None, 0, 0, self
        )
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setValue(0)

        # Worker without parent: closing the dialog must not kill a running QThread.
        self._worker = ImportWorker(self._preview.path, mapping)
        self._worker.ready.connect(self._on_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()
        self._btn_import.setEnabled(False)

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None

    def _on_ready(self, dataset: object) -> None:
        self._close_progress()
        self._btn_import.setEnabled(True)
        if isinstance(dataset, Dataset):
            self.dataset_ready.emit(dataset)
            self.accept()
            return
        QMessageBox.critical(
            self,
            t("import_title", "Импорт ряда"),
            t("import_failed", "Импорт завершился некорректным результатом."),
        )

    def _on_failed(self, message: str) -> None:
        self._close_progress()
        self._btn_import.setEnabled(True)
        QMessageBox.critical(
            self,
            t("import_title", "Импорт ряда"),
            message or t("import_failed", "Не удалось импортировать файл."),
        )

    def done(self, result: int) -> None:  # noqa: D102 - QDialog override
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.isRunning():
            worker.wait(3000)
        super().done(result)

    # Convenience for tests / callers that only need mapping defaults.
    def current_mapping(self) -> dict[str, Any] | None:
        if self._preview is None:
            return None
        return {
            "path": self._preview.path,
            "year_column": self._year_combo.currentText(),
            "value_column": self._value_combo.currentText(),
            "name": self._name_edit.text().strip(),
            "unit": self._unit_edit.text().strip(),
            "location": self._location_edit.text().strip(),
        }
