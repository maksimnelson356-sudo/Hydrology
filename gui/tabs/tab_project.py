"""
gui/tabs/tab_project.py
Раздел «Проект» (P0): создание, открытие и сохранение инженерного проекта (.hsp).

Проект — контейнер работы инженера: наборы данных, параметры, выбранный пост,
путь к файлу исходных данных, результаты расчётов и сценарии. Раздел ничего не
считает: он работает с core.services.project_service и показывает состояние проекта.
"""

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.services.project_service import ProjectService, ProjectServiceError

HINT_STYLE = (
    "color: #666; font-style: italic; padding: 8px; background: #f0f0f0; border-radius: 4px;"
)
TITLE_STYLE = "font-size: 15px; font-weight: bold; color: #0D47A1;"
PROJECT_FILTER = "Проект HydroSphere (*.hsp);;Все файлы (*)"


class ProjectTab(QWidget):
    """Панель проекта: файл .hsp, состав проекта, параметры и предупреждения."""

    status_message = pyqtSignal(str)
    error = pyqtSignal(str)
    project_changed = pyqtSignal(str)

    def __init__(self, service: ProjectService | None = None, parent=None):
        super().__init__(parent)
        self._service = service or ProjectService()
        self._capture_hook: Callable[[ProjectService], object] | None = None
        self._restore_hook: Callable[[ProjectService], list[str]] | None = None
        self._messages: list[str] = []
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Внешний API
    # ------------------------------------------------------------------
    @property
    def service(self) -> ProjectService:
        """Сервис проекта, общий с главным окном."""
        return self._service

    def set_capture_hook(self, hook: Callable[[ProjectService], object]) -> None:
        """Записать состояние главного окна в проект перед сохранением."""
        self._capture_hook = hook

    def set_restore_hook(self, hook: Callable[[ProjectService], list[str]]) -> None:
        """Восстановить состояние главного окна после открытия проекта."""
        self._restore_hook = hook
    # ------------------------------------------------------------------
    # Разметка
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Проект — контейнер инженерной работы")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            "Проект хранит исходные данные, параметры, выбранный пост, расчёты и сценарии. "
            "Файл проекта (.hsp) можно открыть позже и продолжить работу: данные → проверка → "
            "методика → расчёт → контроль → сценарии → результат → отчёт."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        self.btn_create = QPushButton("Создать проект")
        self.btn_create.clicked.connect(self.create_project)
        self.btn_open = QPushButton("Открыть проект...")
        self.btn_open.clicked.connect(self.open_project)
        self.btn_save = QPushButton("Сохранить проект")
        self.btn_save.clicked.connect(self.save_project)
        self.btn_save_as = QPushButton("Сохранить как...")
        self.btn_save_as.clicked.connect(self.save_project_as)
        for button in (self.btn_create, self.btn_open, self.btn_save, self.btn_save_as):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        main_group = QGroupBox("Состояние проекта")
        form = QFormLayout(main_group)
        self.edit_name = QLineEdit()
        self.edit_description = QLineEdit()
        self.label_path = QLabel("—")
        self.label_data = QLabel("—")
        self.label_post = QLabel("—")
        self.label_counts = QLabel("—")
        self.label_dates = QLabel("—")
        form.addRow("Название:", self.edit_name)
        form.addRow("Описание:", self.edit_description)
        form.addRow("Файл проекта:", self.label_path)
        form.addRow("Файл данных:", self.label_data)
        form.addRow("Выбранный пост:", self.label_post)
        form.addRow("Состав проекта:", self.label_counts)
        form.addRow("Создан / изменён:", self.label_dates)
        layout.addWidget(main_group)

        layout.addWidget(QLabel("Наборы данных проекта:"))
        self.table_datasets = QTableWidget(0, 5)
        self.table_datasets.setHorizontalHeaderLabels(
            ["Имя", "Тип", "Единица", "Точек", "Годы"]
        )
        self.table_datasets.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table_datasets.setMaximumHeight(170)
        layout.addWidget(self.table_datasets)

        layout.addWidget(QLabel("Параметры проекта:"))
        self.table_parameters = QTableWidget(0, 2)
        self.table_parameters.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.table_parameters.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table_parameters.setMaximumHeight(140)
        layout.addWidget(self.table_parameters)

        layout.addWidget(QLabel("Предупреждения и сообщения:"))
        self.messages = QPlainTextEdit()
        self.messages.setReadOnly(True)
        self.messages.setMaximumHeight(120)
        layout.addWidget(self.messages)
    # ------------------------------------------------------------------
    # Отображение состояния
    # ------------------------------------------------------------------
    def refresh(self):
        """Обновить элементы панели по текущему состоянию проекта."""
        summary = self._service.summary()
        self.edit_name.setText(summary["title"])
        self.edit_description.setText(summary["description"])
        self.label_path.setText(summary["path"] or "не сохранён (используйте «Сохранить как...»)")
        data_source = summary["data_source"] or "не задан"
        if summary["data_path"]:
            data_source = f"{data_source} — {summary['data_path']}"
        self.label_data.setText(data_source)
        self.label_post.setText(summary["selected_post"] or "не выбран")
        self.label_counts.setText(
            f"наборов данных: {summary['dataset_count']}, расчётов: {summary['calculation_count']}, "
            f"сценариев: {summary['scenario_count']}, отчётов: {summary['report_count']} "
            f"(схема {summary['schema_version']})"
        )
        years = "—"
        if summary["year_from"] and summary["year_to"]:
            years = f"{summary['year_from']}–{summary['year_to']}"
        self.label_dates.setText(
            f"{summary['created_at'][:19]} / {summary['updated_at'][:19]} | годы: {years}"
        )
        self._fill_datasets()
        self._fill_parameters()
        self.messages.setPlainText(
            "\n".join(self._messages) if self._messages else "Сообщений нет"
        )

    def _fill_datasets(self):
        datasets = self._service.datasets
        self.table_datasets.setRowCount(len(datasets))
        for row, dataset in enumerate(datasets):
            years = dataset.years
            cells = [
                dataset.name,
                dataset.dataset_type.value,
                dataset.unit,
                str(dataset.length),
                f"{years[0]}–{years[-1]}" if years else "—",
            ]
            for column, text in enumerate(cells):
                self.table_datasets.setItem(row, column, QTableWidgetItem(str(text)))

    def _fill_parameters(self):
        parameters = self._service.parameters
        self.table_parameters.setRowCount(len(parameters))
        for row, (key, value) in enumerate(sorted(parameters.items())):
            self.table_parameters.setItem(row, 0, QTableWidgetItem(str(key)))
            self.table_parameters.setItem(row, 1, QTableWidgetItem(self._format_value(value)))

    @staticmethod
    def _format_value(value) -> str:
        if isinstance(value, float):
            return f"{value:.4g}"
        return str(value)

    # ------------------------------------------------------------------
    # Действия
    # ------------------------------------------------------------------
    def create_project(self):
        """Создать новый проект (название спрашивается, если поле пустое)."""
        name = self.edit_name.text().strip()
        if not name:
            name, accepted = QInputDialog.getText(self, "Новый проект", "Название проекта:")
            if not accepted or not name.strip():
                return
        try:
            self._service.create_project(
                name.strip(), description=self.edit_description.text().strip()
            )
        except ValueError as error:
            self.error.emit(f"Не удалось создать проект: {error}")
            return
        self._messages = ["Создан новый проект. Сохраните его в файл .hsp."]
        self.refresh()
        self.project_changed.emit("")
        self.status_message.emit(f"Создан проект «{name.strip()}»")
    def open_project(self):
        """Открыть проект из файла .hsp и восстановить состояние данных."""
        path, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", PROJECT_FILTER)
        if not path:
            return
        try:
            self._service.open_project(path)
        except ProjectServiceError as error:
            self.error.emit(str(error))
            return

        messages = list(self._service.warnings)
        if self._restore_hook is not None:
            try:
                messages.extend(self._restore_hook(self._service) or [])
            except (ValueError, TypeError, OSError) as error:
                messages.append(f"Данные не восстановлены: {error}")
        self._messages = messages
        self.refresh()
        self.project_changed.emit(str(path))
        self.status_message.emit(f"Проект открыт: {path}")

    def save_project(self):
        """Сохранить проект; при отсутствии пути вызывается «Сохранить как...»."""
        self._apply_edits()
        if self._service.path is None:
            self.save_project_as()
            return
        self._write(self._service.path)

    def save_project_as(self):
        """Сохранить проект в новый файл .hsp."""
        self._apply_edits()
        name = self._service.project.name or "project"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить проект", f"{name}.hsp", PROJECT_FILTER
        )
        if not path:
            return
        self._write(path)

    # ------------------------------------------------------------------
    # Внутреннее
    # ------------------------------------------------------------------
    def _apply_edits(self):
        """Перенести правки названия и описания из полей в проект."""
        name = self.edit_name.text().strip()
        if name and name != self._service.project.name:
            self._service.project.name = name
        self._service.project.description = self.edit_description.text().strip()

    def _write(self, path):
        """Записать состояние интерфейса в проект и сохранить файл."""
        messages: list[str] = []
        if self._capture_hook is not None:
            try:
                captured = self._capture_hook(self._service)
                if isinstance(captured, list):
                    messages.extend(str(item) for item in captured)
            except (ValueError, TypeError, OSError) as error:
                messages.append(f"Состояние интерфейса записано не полностью: {error}")
        try:
            saved = self._service.save_project(path)
        except ProjectServiceError as error:
            self.error.emit(str(error))
            return
        messages.append(f"Проект сохранён: {saved}")
        self._messages = messages
        self.refresh()
        self.project_changed.emit(str(saved))
        self.status_message.emit(f"Проект сохранён: {saved}")
