"""
gui/tabs/tab_methodology.py
Раздел «Методики» (P0, Этап 3 дорожной карты): реестр методик с нормативной
базой и статусом применимости к текущему ряду.

Раздел ничего не считает сам: выбор методики -> проверка применимости ->
расчёт строго через core.services.calculation_service (build_container()).
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.services import ServiceContainer, build_container
from core.services.calculation_service import CalculationError

HINT_STYLE = (
    "color: #666; font-style: italic; padding: 8px; background: #f0f0f0; border-radius: 4px;"
)
TITLE_STYLE = "font-size: 15px; font-weight: bold; color: #0D47A1;"


class MethodologyTab(QWidget):
    """Список методик, требования к данным, применимость и запуск расчёта."""

    status_message = pyqtSignal(str)
    error = pyqtSignal(str)
    calculation_finished = pyqtSignal(str, object)  # (methodology_id, CalculationResult)

    def __init__(self, container: ServiceContainer | None = None, parent=None):
        super().__init__(parent)
        self._container = container or build_container()
        self._dataset = None  # текущий ряд (Dataset), задаётся извне
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Внешний API
    # ------------------------------------------------------------------
    @property
    def container(self) -> ServiceContainer:
        """Сервисный контейнер, общий с главным окном."""
        return self._container

    def set_dataset(self, dataset) -> None:
        """Задать текущий ряд (Dataset) и пересчитать применимость."""
        self._dataset = dataset
        self.refresh()

    # ------------------------------------------------------------------
    # Разметка
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("Методики — расчёт через сервисный слой")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            "Выберите методику: покажаны нормативная база, требования к данным и статус "
            "применимости к текущему ряду. Расчёт выполняет CalculationService; "
            "неприменимая методика не запустится — будет понятная ошибка со ссылкой на СП."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        layout.addWidget(hint)

        top = QHBoxLayout()
        left_group = QGroupBox("Реестр методик (P0)")
        left_layout = QVBoxLayout(left_group)
        self.list_methodologies = QListWidget()
        self.list_methodologies.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self.list_methodologies)
        top.addWidget(left_group, stretch=3)

        right_group = QGroupBox("Описание и применимость")
        form = QFormLayout(right_group)
        self.label_name = QLabel("—")
        self.label_standard = QLabel("—")
        self.label_scope = QLabel("—")
        self.label_scope.setWordWrap(True)
        self.label_limits = QLabel("—")
        self.label_limits.setWordWrap(True)
        self.label_normative = QLabel("—")
        self.label_applicability = QLabel("—")
        self.label_applicability.setWordWrap(True)
        form.addRow("Методика:", self.label_name)
        form.addRow("Норматив:", self.label_standard)
        form.addRow("Область применения:", self.label_scope)
        form.addRow("Ограничения:", self.label_limits)
        form.addRow("Статус:", self.label_normative)
        form.addRow("Применимость к ряду:", self.label_applicability)
        self.btn_run = QPushButton("Выполнить расчёт")
        self.btn_run.clicked.connect(self.run_calculation)
        form.addRow("", self.btn_run)
        top.addWidget(right_group, stretch=4)
        layout.addLayout(top)

        result_group = QGroupBox("Результат расчёта")
        result_layout = QVBoxLayout(result_group)
        self.result_table = QTableWidget()
        self.result_table.columnCount = 2
        self.result_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.result_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.result_text = QPlainTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(140)
        result_layout.addWidget(self.result_table)
        result_layout.addWidget(self.result_text)
        layout.addWidget(result_group, stretch=2)

    # ------------------------------------------------------------------
    # Логика
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Перечитать реестр и обновить статус применимости."""
        current = self.list_methodologies.currentRow()
        self.list_methodologies.blockSignals(True)
        self.list_methodologies.clear()
        for descriptor in self._container.registry.list():
            if self._container.calculation.has_handler(descriptor.qualified_name):
                item = QListWidgetItem(f"{descriptor.name} ({descriptor.id})")
                item.setData(Qt.ItemDataRole.UserRole, descriptor.id)
                self.list_methodologies.addItem(item)
        self.list_methodologies.blockSignals(False)
        row = min(current, self.list_methodologies.count() - 1)
        if row >= 0:
            self.list_methodologies.setCurrentRow(row)
        self._on_select(self.list_methodologies.currentRow())

    def _current_id(self) -> str | None:
        item = self.list_methodologies.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _on_select(self, _row: int) -> None:
        methodology_id = self._current_id()
        if not methodology_id:
            return
        descriptor = self._container.registry.get(methodology_id)
        self.label_name.setText(f"{descriptor.name} ({descriptor.qualified_name})")
        self.label_standard.setText(descriptor.normative_reference)
        self.label_scope.setText(descriptor.scope or "—")
        self.label_limits.setText(
            "; ".join(descriptor.limitations) if descriptor.limitations else "—"
        )
        kind = "нормативно предписана" if descriptor.is_normative else "инженерная реализация"
        self.label_normative.setText(kind)
        self._update_applicability(descriptor)

    def _update_applicability(self, descriptor) -> None:
        if self._dataset is None:
            self.label_applicability.setText("ряд не загружен")
            return
        check = self._container.registry.check_applicability(
            descriptor.id, self._dataset, {}
        )
        if check.is_valid:
            self.label_applicability.setStyleSheet("color: #2E7D32;")
            self.label_applicability.setText("применима ✓")
        else:
            messages = "; ".join(issue.message for issue in check.issues)
            self.label_applicability.setStyleSheet("color: #C62828;")
            self.label_applicability.setText(f"неприменима: {messages}")

    def run_calculation(self) -> None:
        """Запустить расчёт выбранной методики через CalculationService."""
        methodology_id = self._current_id()
        if not methodology_id:
            QMessageBox.information(self, "Методики", "Выберите методику из списка.")
            return
        if self._dataset is None:
            QMessageBox.warning(
                self, "Нет данных", "Сначала загрузите ряд в разделе «Данные и статистика»."
            )
            return
        descriptor = self._container.registry.get(methodology_id)
        try:
            result = self._container.calculation.execute(
                descriptor.to_methodology(),
                self._dataset,
                parameters=self._parameters_for(methodology_id),
            )
        except CalculationError as exc:
            self.error.emit(str(exc))
            QMessageBox.critical(self, "Расчёт не выполнен", str(exc))
            return
        self._show_result(descriptor, result)
        self.calculation_finished.emit(methodology_id, result)
        self.status_message.emit(f"Расчёт «{descriptor.name}» выполнен")

    def _parameters_for(self, methodology_id: str) -> dict[str, Any]:
        """Параметры запуска: спрос для водохранилища, остальное — по умолчанию."""
        if methodology_id == "reservoir_regulation":
            from PyQt6.QtWidgets import QInputDialog

            demand, ok = QInputDialog.getDouble(
                self,
                "reservoir_regulation",
                "Потребность в воде, м³/с (demand_m3_s):",
                value=50.0,
                min=0.0,
                decimals=2,
            )
            if not ok:
                raise CalculationError("Расчёт отменён пользователем", methodology_id)
            return {"demand_m3_s": demand}
        return {}

    def _show_result(self, descriptor, result) -> None:
        """Показать результат: плоские пары ключ/значение + сырой JSON."""
        from PyQt6.QtWidgets import QHeaderView as QHeaderViewForResize

        payload = result.output_data or {}
        rows: list[tuple[str, str]] = []

        def _walk(prefix: str, value) -> None:
            if isinstance(value, dict) and "columns" in value and "rows" in value:
                # DataFrame-представление (columns/rows)
                rows.append((prefix or "таблица", f"{len(value.get('rows', []))} строк"))
            elif isinstance(value, dict):
                for key, sub in value.items():
                    _walk(f"{prefix}{key}." if isinstance(sub, (dict, list)) else f"{prefix}{key}", sub)
            elif isinstance(value, list):
                rows.append((prefix or "список", f"{len(value)} значений"))
            else:
                rows.append((prefix.rstrip(".") or "—", str(value)))

        _walk("", payload)
        self.result_table.setRowCount(max(len(rows), 1))
        self.result_table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        if not rows:
            self.result_table.setItem(0, 0, QTableWidgetItem("—"))
            self.result_table.setItem(0, 1, QTableWidgetItem("пустой результат"))
        for index, (key, text) in enumerate(rows[:500]):
            self.result_table.setItem(index, 0, QTableWidgetItem(key))
            self.result_table.setItem(index, 1, QTableWidgetItem(text))
        self.result_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderViewForResize.ResizeMode.ResizeToContents
        )
        self.result_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderViewForResize.ResizeMode.Stretch
        )

        import json as _json

        self.result_text.setPlainText(
            _json.dumps(payload, ensure_ascii=False, indent=2, default=str)[:4000]
        )
