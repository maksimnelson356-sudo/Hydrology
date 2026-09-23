"""
gui/tabs/tab_results.py
Results tab showing calculation history and provenance.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
)
from PyQt6.QtWidgets import (
    QGroupBox as GroupBox,
)
from PyQt6.QtWidgets import (
    QHBoxLayout as HBox,
)
from PyQt6.QtWidgets import (
    QHeaderView as HeaderView,
)
from PyQt6.QtWidgets import (
    QLabel as Label,
)
from PyQt6.QtWidgets import (
    QPushButton as PushButton,
)
from PyQt6.QtWidgets import (
    QTableWidget as TableWidget,
)
from PyQt6.QtWidgets import (
    QTableWidgetItem as TableWidgetItem,
)
from PyQt6.QtWidgets import (
    QVBoxLayout as VBox,
)
from PyQt6.QtWidgets import (
    QWidget as Widget,
)

from core.domain.models import CalculationResult
from core.services.result_store import provenance_chain

# Version of the application (should be defined elsewhere, but we'll set a default)
__version__ = "0.1.0"


class TabResults(Widget):
    """Tab showing list of calculation results and provenance."""

    def __init__(
        self,
        result_store=None,
        service_container=None,
        parent: Widget | None = None,
    ) -> None:
        super().__init__(parent)
        if result_store is None and service_container is not None:
            result_store = getattr(service_container, "results", None)
        self._result_store = result_store
        # Optional lookups for provenance labels; None-safe in _show_provenance.
        self._dataset_store = getattr(service_container, "datasets", None)
        self._scenario_store = getattr(service_container, "scenario", None)
        self._selected_result: CalculationResult | None = None
        # Sorting and filtering state
        self._sort_column = 0  # default sort by number
        self._sort_order = Qt.SortOrder.AscendingOrder
        self._filter_text = ""
        self._build_ui()
        self.refresh()

    def _get_provenance_step_icon(self, step_kind: str) -> str:
        """Return an emoji icon for the given step kind in provenance."""
        icon_map = {
            "data": "📊",
            "methodology": "⚙️",
            "parameters": "🔧",
            "calculation": "🧮",
            "output": "📤",
            "quality": "✅",
            "validation": "🔍",
            "scenario": "🎯",
            "engine": "🔧",
        }
        return icon_map.get(step_kind.lower(), "📌")

    def _build_ui(self) -> None:
        layout = VBox()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Filter bar
        filter_layout = HBox()
        filter_layout.addWidget(Label("Фильтр:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Введите текст для фильтрации...")
        self.filter_edit.textChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_edit)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Results table
        results_group = GroupBox("История расчётов")
        results_layout = VBox()
        self.table = TableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["№", "Методика", "Дата", "Статус", "Значение"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, HeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, HeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, HeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, HeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, HeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        # Context menu
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        # Header click for sorting
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        results_layout.addWidget(self.table)
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        # Provenance button
        btn_layout = HBox()
        self.btn_provenance = PushButton("Откуда это число?")
        self.btn_provenance.clicked.connect(self._show_provenance)
        self.btn_provenance.setEnabled(False)
        btn_layout.addWidget(self.btn_provenance)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Provenance details
        prov_group = GroupBox("Цепочка получения (provenance)")
        prov_layout = VBox()
        self.provenance_tree = QTreeWidget()
        self.provenance_tree.setHeaderHidden(True)
        self.provenance_tree.setAlternatingRowColors(True)
        self.provenance_tree.setExpandsOnDoubleClick(False)
        self.provenance_tree.setIndentation(15)
        self.provenance_tree.setStyleSheet("""
            QTreeWidget {
                outline: 0;
            }
            QTreeWidget::item {
                height: 24px;
                border: 1px solid transparent;
                border-radius: 3px;
            }
            QTreeWidget::item:selected {
                background-color: #1565C0;
                color: white;
            }
            QTreeWidget::item:hover:!selected {
                background-color: #E3F2FD;
            }
        """)
        prov_layout.addWidget(self.provenance_tree)
        prov_group.setLayout(prov_layout)
        layout.addWidget(prov_group)

        layout.addStretch(1)
        self.setLayout(layout)

    def _on_filter_changed(self, text: str) -> None:
        self._filter_text = text.strip().lower()
        self.refresh()

    def _on_header_clicked(self, logical_index: int) -> None:
        if logical_index == self._sort_column:
            # Toggle order
            if self._sort_order == Qt.SortOrder.AscendingOrder:
                self._sort_order = Qt.SortOrder.DescendingOrder
            else:
                self._sort_order = Qt.SortOrder.AscendingOrder
        else:
            self._sort_column = logical_index
            self._sort_order = Qt.SortOrder.AscendingOrder
        self.refresh()

    def refresh(self) -> None:
        """Refresh the table from the result store with sorting and filtering."""
        if self._result_store is None:
            self.table.setRowCount(0)
            self._selected_result = None
            self.btn_provenance.setEnabled(False)
            return
        results = self._result_store.list_results()
        # Apply sorting
        sorted_results = self._sort_results(results)
        # Apply filtering
        if self._filter_text:
            filtered_results = [
                r for r in sorted_results if self._matches_filter(r, self._filter_text)
            ]
        else:
            filtered_results = sorted_results

        self.table.setRowCount(len(filtered_results))
        for row, result in enumerate(filtered_results):
            metadata = result.metadata
            # №
            label = getattr(metadata, "label", f"Расчёт #{row + 1}")
            item0 = TableWidgetItem(label)
            item0.setData(Qt.ItemDataRole.UserRole, result)
            item0.setToolTip(self._get_tooltip(result, 0))
            self.table.setItem(row, 0, item0)
            # Методика
            meth_name = metadata.methodology.qualified_name
            item1 = TableWidgetItem(meth_name)
            item1.setToolTip(self._get_tooltip(result, 1))
            self.table.setItem(row, 1, item1)
            # Дата
            dt = metadata.completed_at or metadata.started_at or metadata.created_at
            date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else ""
            item2 = TableWidgetItem(date_str)
            item2.setToolTip(self._get_tooltip(result, 2))
            self.table.setItem(row, 2, item2)
            # Статус
            status_str = metadata.status.value.capitalize()
            item3 = TableWidgetItem(status_str)
            item3.setToolTip(self._get_tooltip(result, 3))
            self.table.setItem(row, 3, item3)
            # Значение (first output or N/A)
            if result.output_data:
                first_key = next(iter(result.output_data))
                first_val = result.output_data[first_key]
                if isinstance(first_val, float):
                    val_str = f"{first_key}: {first_val:.4g}"
                else:
                    val_str = f"{first_key}: {first_val}"
            else:
                val_str = "нет данных"
            item4 = TableWidgetItem(val_str)
            item4.setToolTip(self._get_tooltip(result, 4))
            self.table.setItem(row, 4, item4)

        # Select first row if any
        if filtered_results:
            self.table.selectRow(0)
        else:
            self._selected_result = None
            self.btn_provenance.setEnabled(False)

    def _sort_results(self, results: list[CalculationResult]) -> list[CalculationResult]:
        """Return a new list of results sorted by the current sort column and order."""
        # Make a copy to avoid modifying the original list
        results_copy = list(results)
        if self._sort_column == 0:  # номер
            results_copy.sort(
                key=lambda r: getattr(r.metadata, "label", ""),
                reverse=(self._sort_order == Qt.SortOrder.DescendingOrder),
            )
        elif self._sort_column == 1:  # методика
            results_copy.sort(
                key=lambda r: r.metadata.methodology.qualified_name,
                reverse=(self._sort_order == Qt.SortOrder.DescendingOrder),
            )
        elif self._sort_column == 2:  # дата
            results_copy.sort(
                key=lambda r: r.metadata.completed_at
                or r.metadata.started_at
                or r.metadata.created_at,
                reverse=(self._sort_order == Qt.SortOrder.DescendingOrder),
            )
        elif self._sort_column == 3:  # статус
            results_copy.sort(
                key=lambda r: r.metadata.status.value,
                reverse=(self._sort_order == Qt.SortOrder.DescendingOrder),
            )
        elif self._sort_column == 4:  # значение
            # For value, we try to get a numeric value from the first output, else use 0
            def get_value(r):
                if r.output_data:
                    first_val = next(iter(r.output_data.values()))
                    if isinstance(first_val, (int, float)):
                        return first_val
                return 0
            results_copy.sort(
                key=get_value, reverse=(self._sort_order == Qt.SortOrder.DescendingOrder)
            )
        return results_copy

    def _matches_filter(self, result: CalculationResult, filter_text: str) -> bool:
        """Check if the result matches the filter text in any of the displayed columns."""
        metadata = result.metadata
        # Check label
        label = getattr(metadata, "label", "")
        if filter_text in label.lower():
            return True
        # Check methodology name
        meth_name = metadata.methodology.qualified_name
        if filter_text in meth_name.lower():
            return True
        # Check date
        dt = metadata.completed_at or metadata.started_at or metadata.created_at
        date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else ""
        if filter_text in date_str.lower():
            return True
        # Check status
        status_str = metadata.status.value.lower()
        if filter_text in status_str:
            return True
        # Check value (first output)
        if result.output_data:
            first_key = next(iter(result.output_data))
            first_val = result.output_data[first_key]
            val_str = f"{first_key}: {first_val}"
            if filter_text in val_str.lower():
                return True
        return False

    def _get_tooltip(self, result: CalculationResult, column: int) -> str:
        """Generate a tooltip for the given result and column."""
        metadata = result.metadata
        dt = metadata.completed_at or metadata.started_at or metadata.created_at
        date_str = dt.strftime("%Y-%m-%d %H:%M") if dt else ""
        base = (
            f"Методика: {metadata.methodology.qualified_name}\n"
            f"Дата: {date_str}\n"
            f"Статус: {metadata.status.value.capitalize()}\n"
            f"Метка: {getattr(metadata, 'label', 'N/A')}"
        )
        if column == 0:  # номер
            return f"{base}\nМетка: {getattr(metadata, 'label', 'N/A')}"
        elif column == 1:  # методика
            return (
                f"{base}\n"
                f"Полное имя: {metadata.methodology.qualified_name}\n"
                f"Описание: {metadata.methodology.description or '—'}"
            )
        elif column == 2:  # дата
            started = (
                metadata.started_at.strftime("%Y-%m-%d %H:%M")
                if metadata.started_at
                else "N/A"
            )
            completed = (
                metadata.completed_at.strftime("%Y-%m-%d %H:%M")
                if metadata.completed_at
                else "N/A"
            )
            created = (
                metadata.created_at.strftime("%Y-%m-%d %H:%M")
                if metadata.created_at
                else "N/A"
            )
            return f"{base}\nНачато: {started}\nЗавершено: {completed}\nСоздано: {created}"
        elif column == 3:  # статус
            return f"{base}\nПодробный статус: {metadata.status.value}"
        elif column == 4:  # значение
            if result.output_data:
                lines = [f"{k}: {v}" for k, v in result.output_data.items()]
                output_str = "\n".join(lines)
            else:
                output_str = "Нет выходных данных"
            # Add warnings if any (warnings live on CalculationResult, not metadata)
            warnings = getattr(result, "warnings", None) or []
            if warnings:
                warning_str = "\n".join(warnings)
                return f"{base}\nВыходные данные:\n{output_str}\n\nПредупреждения:\n{warning_str}"
            else:
                return f"{base}\nВыходные данные:\n{output_str}"
        return base

    def _on_selection_changed(self) -> None:
        selected = self.table.selectedItems()
        if selected:
            # Take the first selected item (any column) and get the result from its UserRole
            item = selected[0]
            result = item.data(Qt.ItemDataRole.UserRole)
            if result is not None:
                self._selected_result = result
                self.btn_provenance.setEnabled(True)
                return
        self._selected_result = None
        self.btn_provenance.setEnabled(False)

    def _show_context_menu(self, position) -> None:
        """Show context menu for the table."""
        item = self.table.itemAt(position)
        if not item:
            return
        # Get the result from the item's UserRole (we store it in each item)
        result = item.data(Qt.ItemDataRole.UserRole)
        if result is None:
            return

        menu = QMenu()
        copy_action = menu.addAction("Копировать значение")
        export_action = menu.addAction("Экспортировать результат")
        # Compare action is disabled for now (requires two selections)
        compare_action = menu.addAction("Сравнить с другим результатом")
        compare_action.setEnabled(False)

        action = menu.exec(self.table.viewport().mapToPosition(position))
        if action == copy_action:
            self._copy_value(item)
        elif action == export_action:
            self._export_result(result)
        elif action == compare_action:
            # Placeholder for future implementation
            QMessageBox.information(
                self,
                "Сравнение",
                "Функция сравнения результатов будет реализована в будущих версиях.",
            )

    def _copy_value(self, item: TableWidgetItem) -> None:
        """Copy the text of the given item to clipboard."""
        from PyQt6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(item.text())

    def _export_result(self, result: CalculationResult) -> None:
        """Export the result to a JSON file."""
        import json
        from datetime import datetime
        from uuid import UUID

        from PyQt6.QtWidgets import QFileDialog

        # Prepare a JSON-serializable dictionary
        data = {
            "metadata": {
                "label": getattr(result.metadata, "label", None),
                "methodology": {
                    "name": result.metadata.methodology.name,
                    "qualified_name": result.metadata.methodology.qualified_name,
                    "standard": result.metadata.methodology.standard,
                },
                "status": result.metadata.status.value,
                "started_at": (
                    result.metadata.started_at.isoformat()
                    if result.metadata.started_at
                    else None
                ),
                "completed_at": (
                    result.metadata.completed_at.isoformat()
                    if result.metadata.completed_at
                    else None
                ),
                "created_at": (
                    result.metadata.created_at.isoformat()
                    if result.metadata.created_at
                    else None
                ),
                "input_dataset_ids": [
                    str(uid) for uid in result.metadata.input_dataset_ids
                ],
                "input_parameters": result.metadata.input_parameters,
            },
            "output_data": result.output_data,
            "warnings": list(getattr(result, "warnings", []) or []),
        }

        # Handle UUID and datetime in input_parameters
        def make_serializable(obj):
            if isinstance(obj, UUID):
                return str(obj)
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        # We'll do a simple pass; for now assume input_parameters are already serializable
        # (they should be, as they come from the domain model's serialization)
        try:
            json_str = json.dumps(data, indent=2, ensure_ascii=False, default=make_serializable)
        except TypeError as e:
            QMessageBox.warning(
                self,
                "Ошибка экспорта",
                f"Не удалось экспортировать результат из-за неподдерживаемого типа данных: {e}",
            )
            return

        # Ask for file name
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Экспортировать результат",
            f"result_{getattr(result.metadata, 'label', 'unknown').replace(' ', '_')}.json",
            "JSON файлы (*.json);;Все файлы (*)",
        )
        if file_name:
            try:
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(json_str)
                QMessageBox.information(
                    self,
                    "Экспорт успешен",
                    f"Результат успешно экспортирован в файл:\n{file_name}",
                )
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Ошибка экспорта",
                    f"Не удалось записать файл:\n{e}",
                )

    def _show_provenance(self) -> None:
        if not self._selected_result:
            return
        metadata = self._selected_result.metadata

        # Get dataset names from input_dataset_ids (store may be absent).
        dataset_names = []
        if self._dataset_store is not None:
            for dataset_id in metadata.input_dataset_ids:
                dataset = getattr(self._dataset_store, "get_by_id", lambda _id: None)(dataset_id)
                if dataset is None and hasattr(self._dataset_store, "get_dataset"):
                    dataset = self._dataset_store.get_dataset(dataset_id)
                if dataset:
                    dataset_names.append(dataset.name)
                else:
                    dataset_names.append(f"Unknown dataset ({dataset_id})")
        dataset_name = ", ".join(dataset_names) if dataset_names else None

        # Try to get scenario from input_parameters or metadata
        scenario_name = metadata.input_parameters.get("scenario_name")
        if not scenario_name and self._scenario_store is not None:
            scenario_id_str = metadata.input_parameters.get("scenario_id")
            if scenario_id_str:
                try:
                    from uuid import UUID
                    scenario_id = UUID(scenario_id_str)
                    scenario = None
                    if hasattr(self._scenario_store, "get_optional"):
                        scenario = self._scenario_store.get_optional(scenario_id)
                    elif hasattr(self._scenario_store, "get_by_id"):
                        scenario = self._scenario_store.get_by_id(scenario_id)
                    if scenario:
                        scenario_name = scenario.name
                except (ValueError, TypeError):
                    pass

        # Quality information might be in input_parameters or could be fetched from quality service
        # For now, we'll try to get from input_parameters
        quality_grade = metadata.input_parameters.get("quality_grade")
        quality_score = metadata.input_parameters.get("quality_score")
        n_years = metadata.input_parameters.get("n_years")
        parameters = metadata.input_parameters

        steps = provenance_chain(
            self._selected_result,
            quality_grade=quality_grade,
            quality_score=quality_score,
            scenario_name=scenario_name,
            dataset_name=dataset_name,
            n_years=n_years,
            parameters=parameters,
        )

        # Clear existing items
        self.provenance_tree.clear()

        # Add root item with icon
        root_item = QTreeWidgetItem(self.provenance_tree, ["Результат расчёта"])
        root_item.setExpanded(True)
        # Set icon for root (could use a database or calculation icon)
        # For now, we'll rely on the styling

        # Add each step as a child item with appropriate icons based on step kind
        for step in steps:
            # Determine icon based on step kind
            icon_text = self._get_provenance_step_icon(step.kind)
            step_item = QTreeWidgetItem(root_item, [f"{icon_text} {step.kind.upper()}: {step.title}"])
            if step.detail:
                detail_item = QTreeWidgetItem(step_item, [f"ℹ️ {step.detail}"])
                step_item.addChild(detail_item)
            step_item.setExpanded(True)

        # Add engine version info at the bottom
        engine_item = QTreeWidgetItem(root_item, [f"🔧 Версия движка: {__version__}"])
        engine_item.setExpanded(True)
