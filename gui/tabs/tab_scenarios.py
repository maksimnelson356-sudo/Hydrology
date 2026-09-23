"""
gui/tabs/tab_scenarios.py
Scenario tab for HydroSphere P0 architecture.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.domain.models import ScenarioStatus
from core.services.calculation_service import CalculationError
from core.services.reservoir_scenario_service import (
    ReservoirScenarioError,
    ReservoirScenarioService,
)
from core.services.scenario_service import ScenarioNotFoundError, ScenarioService

if TYPE_CHECKING:
    from core.services.bootstrap import ServiceContainer


class ScenarioTab(QWidget):
    """Tab for managing scenarios."""
    status_message = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(
        self,
        scenario_service: ScenarioService | None = None,
        service_container: ServiceContainer | None = None,
    ):
        super().__init__()
        self.scenario_service = scenario_service
        self.service_container = service_container
        self.reservoir_service = (
            ReservoirScenarioService(scenario_service) if scenario_service else None
        )
        self._last_used_methodology: dict[UUID, str] = {}
        self._setup_ui()
        self._refresh_scenarios()
        if self.service_container:
            self._populate_methodology_combo()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.btn_create = QPushButton("Создать сценарий")
        self.btn_create.clicked.connect(self._create_scenario)
        self.btn_clone = QPushButton("Клонировать")
        self.btn_clone.clicked.connect(self._clone_scenario)
        self.btn_update = QPushButton("Обновить")
        self.btn_update.clicked.connect(self._update_scenario)
        self.btn_archive = QPushButton("Архивировать")
        self.btn_archive.clicked.connect(self._archive_scenario)
        self.btn_remove = QPushButton("Удалить")
        self.btn_remove.clicked.connect(self._remove_scenario)
        self.btn_run = QPushButton("Запустить")
        self.btn_run.clicked.connect(self._run_scenario)
        self.btn_compare = QPushButton("Сравнить")
        self.btn_compare.clicked.connect(self._compare_scenarios)

        toolbar.addWidget(self.btn_create)
        toolbar.addWidget(self.btn_clone)
        toolbar.addWidget(self.btn_update)
        toolbar.addWidget(self.btn_archive)
        toolbar.addWidget(self.btn_remove)
        toolbar.addWidget(self.btn_run)
        toolbar.addWidget(self.btn_compare)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter: list and details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left: scenario list
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.addWidget(QLabel("Сценарии:"))
        self.scenario_list = QListWidget()
        self.scenario_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.scenario_list.itemSelectionChanged.connect(self._on_scenario_selected)
        left_layout.addWidget(self.scenario_list)
        splitter.addWidget(left_frame)

        # Right: details and controls
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        splitter.addWidget(right_frame)

        # Scenario details
        details_group = QGroupBox("Детали сценария")
        details_layout = QFormLayout(details_group)
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Название сценария")
        self.edit_description = QLineEdit()
        self.edit_description.setPlaceholderText("Описание")
        self.combo_status = QComboBox()
        self.combo_status.addItems([s.value for s in ScenarioStatus])
        self.edit_parameters = QTextEdit()
        self.edit_parameters.setPlaceholderText("Параметры (JSON)")
        self.edit_parameters.setMaximumHeight(100)
        details_layout.addRow("Название:", self.edit_name)
        details_layout.addRow("Описание:", self.edit_description)
        details_layout.addRow("Статус:", self.combo_status)
        details_layout.addRow("Параметры:", self.edit_parameters)
        right_layout.addWidget(details_group)

        # Run scenario controls
        run_group = QGroupBox("Запуск сценария")
        run_layout = QFormLayout(run_group)
        self.combo_methodology = QComboBox()
        self.combo_methodology.setPlaceholderText("Выберите методику")
        self.btn_run_with_method = QPushButton("Запустить с методикой")
        self.btn_run_with_method.clicked.connect(self._run_with_methodology)
        run_layout.addRow("Методика:", self.combo_methodology)
        run_layout.addRow("", self.btn_run_with_method)
        right_layout.addWidget(run_group)

        # P1.7 Reservoir Scenario Simulator
        reservoir_group = QGroupBox("Водохранилище (сценарный расчёт)")
        reservoir_layout = QFormLayout(reservoir_group)
        self.edit_res_name = QLineEdit()
        self.edit_res_name.setPlaceholderText("Название (напр. Base)")
        self.spin_res_demand = QDoubleSpinBox()
        self.spin_res_demand.setRange(0.01, 100000.0)
        self.spin_res_demand.setValue(50.0)
        self.spin_res_demand.setDecimals(2)
        self.spin_res_vmax = QDoubleSpinBox()
        self.spin_res_vmax.setRange(0.0, 100000.0)
        self.spin_res_vmax.setValue(2.0)
        self.spin_res_vmax.setDecimals(3)
        self.spin_res_s0 = QDoubleSpinBox()
        self.spin_res_s0.setRange(0.0, 100000.0)
        self.spin_res_s0.setValue(0.0)
        self.spin_res_s0.setDecimals(3)
        self.spin_res_guarantee = QDoubleSpinBox()
        self.spin_res_guarantee.setRange(1.0, 100.0)
        self.spin_res_guarantee.setValue(95.0)
        self.spin_res_guarantee.setDecimals(1)
        self.spin_res_guarantee.setSuffix(" %")
        self.combo_res_mode = QComboBox()
        self.combo_res_mode.addItems(
            ["guarantee_for_volume", "volume_for_guarantee", "natural_supply"]
        )
        self.btn_res_create = QPushButton("Создать сценарий")
        self.btn_res_create.clicked.connect(self._create_reservoir_scenario)
        self.btn_res_run = QPushButton("Запустить водохранилище")
        self.btn_res_run.clicked.connect(self._run_reservoir_scenario)
        self.btn_res_delta = QPushButton("Сравнить Δ")
        self.btn_res_delta.clicked.connect(self._compare_reservoir_delta)
        reservoir_layout.addRow("Название:", self.edit_res_name)
        reservoir_layout.addRow("Забор D, м³/с:", self.spin_res_demand)
        reservoir_layout.addRow("V полезное, км³:", self.spin_res_vmax)
        reservoir_layout.addRow("S₀, км³:", self.spin_res_s0)
        reservoir_layout.addRow("Гарантия:", self.spin_res_guarantee)
        reservoir_layout.addRow("Режим:", self.combo_res_mode)
        reservoir_layout.addRow("", self.btn_res_create)
        reservoir_layout.addRow("", self.btn_res_run)
        reservoir_layout.addRow("", self.btn_res_delta)
        right_layout.addWidget(reservoir_group)

        # Balance series plot (P1.7)
        plot_group = QGroupBox("Баланс водохранилища (км³)")
        plot_layout = QVBoxLayout(plot_group)
        self.figure_balance = Figure(figsize=(5, 2.5))
        self.canvas_balance = FigureCanvas(self.figure_balance)
        plot_layout.addWidget(self.canvas_balance)
        right_layout.addWidget(plot_group)

        # Comparison results
        compare_group = QGroupBox("Сравнение сценариев")
        compare_layout = QVBoxLayout(compare_group)
        # Parameter comparison
        compare_layout.addWidget(QLabel("Параметры:"))
        self.compare_param_table = QTableWidget()
        self.compare_param_table.setColumnCount(0)
        self.compare_param_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.compare_param_table.verticalHeader().setVisible(False)
        self.compare_param_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        compare_layout.addWidget(self.compare_param_table)
        # Result comparison
        compare_layout.addWidget(QLabel("Результаты и Δ:"))
        self.compare_result_table = QTableWidget()
        self.compare_result_table.setColumnCount(0)
        self.compare_result_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.compare_result_table.verticalHeader().setVisible(False)
        self.compare_result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        compare_layout.addWidget(self.compare_result_table)
        right_layout.addWidget(compare_group)

        # Initially disable controls
        self.set_controls_enabled(False)

    def set_controls_enabled(self, enabled: bool):
        """Enable or disable scenario editing controls."""
        self.btn_clone.setEnabled(enabled)
        self.btn_update.setEnabled(enabled)
        self.btn_archive.setEnabled(enabled)
        self.btn_remove.setEnabled(enabled)
        self.btn_run.setEnabled(enabled)
        self.btn_compare.setEnabled(enabled)
        self.edit_name.setEnabled(enabled)
        self.edit_description.setEnabled(enabled)
        self.combo_status.setEnabled(enabled)
        self.edit_parameters.setEnabled(enabled)

    def _refresh_scenarios(self):
        """Refresh the scenario list from the service."""
        if not self.scenario_service:
            return
        self.scenario_list.clear()
        scenarios = self.scenario_service.list()
        for scenario in scenarios:
            item = QListWidgetItem(scenario.name)
            item.setData(Qt.ItemDataRole.UserRole, scenario.id)
            # Set color based on status
            if scenario.status == ScenarioStatus.ACTIVE:
                item.setForeground(Qt.GlobalColor.darkGreen)
            elif scenario.status == ScenarioStatus.ARCHIVED:
                item.setForeground(Qt.GlobalColor.darkGray)
            else:
                item.setForeground(Qt.GlobalColor.black)
            self.scenario_list.addItem(item)
        self._on_scenario_selected()  # update details

    def _on_scenario_selected(self):
        """Update details when scenario selection changes."""
        item = self.scenario_list.currentItem()
        if not item:
            self.set_controls_enabled(False)
            self._clear_details()
            return
        self.set_controls_enabled(True)
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            scenario = self.scenario_service.get(scenario_id)
        except ScenarioNotFoundError:
            self._clear_details()
            return
        self.edit_name.setText(scenario.name)
        self.edit_description.setText(scenario.description)
        index = self.combo_status.findText(scenario.status.value)
        if index >= 0:
            self.combo_status.setCurrentIndex(index)
        # Show parameters as JSON
        import json
        self.edit_parameters.setText(json.dumps(scenario.parameters, indent=2, ensure_ascii=False))

    def _clear_details(self):
        """Clear scenario details fields."""
        self.edit_name.clear()
        self.edit_description.clear()
        self.combo_status.setCurrentIndex(0)
        self.edit_parameters.clear()
        self.compare_table.setRowCount(0)
        self.compare_table.setColumnCount(0)

    def _create_scenario(self):
        """Create a new scenario."""
        if not self.scenario_service:
            return
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название сценария")
            return
        description = self.edit_description.text()
        # Parse parameters JSON
        import json
        try:
            parameters = json.loads(self.edit_parameters.toPlainText())
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Ошибка", f"Неверный формат JSON в параметрах: {e}")
            return
        scenario = self.scenario_service.create(
            name=name,
            description=description,
            parameters=parameters
        )
        self.status_message.emit(f"Создан сценарий: {scenario.name}")
        self._refresh_scenarios()
        # Select the newly created scenario
        for i in range(self.scenario_list.count()):
            item = self.scenario_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == scenario.id:
                self.scenario_list.setCurrentItem(item)
                break

    def _clone_scenario(self):
        """Clone the selected scenario."""
        item = self.scenario_list.currentItem()
        if not item:
            return
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        name = self.edit_name.text().strip()
        if not name:
            name = "Копия сценария"
        # Parse parameters JSON
        import json
        try:
            parameters = json.loads(self.edit_parameters.toPlainText())
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Ошибка", f"Неверный формат JSON в параметрах: {e}")
            return
        try:
            clone = self.scenario_service.clone(scenario_id, name=name, parameters=parameters)
            self.status_message.emit(f"Сценарий клонирован: {clone.name}")
            self._refresh_scenarios()
            # Select the cloned scenario
            for i in range(self.scenario_list.count()):
                item = self.scenario_list.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == clone.id:
                    self.scenario_list.setCurrentItem(item)
                    break
        except ScenarioNotFoundError:
            QMessageBox.warning(self, "Ошибка", "Сценарий не найден")

    def _update_scenario(self):
        """Update the selected scenario."""
        item = self.scenario_list.currentItem()
        if not item:
            return
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название сценария")
            return
        description = self.edit_description.text()
        # Parse parameters JSON
        import json
        try:
            parameters = json.loads(self.edit_parameters.toPlainText())
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Ошибка", f"Неверный формат JSON в параметрах: {e}")
            return
        try:
            scenario = self.scenario_service.update(
                scenario_id,
                name=name,
                description=description,
                parameters=parameters
            )
            self.status_message.emit(f"Сценарий обновлен: {scenario.name}")
            self._refresh_scenarios()
        except ScenarioNotFoundError:
            QMessageBox.warning(self, "Ошибка", "Сценарий не найден")

    def _archive_scenario(self):
        """Archive the selected scenario."""
        item = self.scenario_list.currentItem()
        if not item:
            return
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            scenario = self.scenario_service.archive(scenario_id)
            self.status_message.emit(f"Сценарий archived: {scenario.name}")
            self._refresh_scenarios()
        except ScenarioNotFoundError:
            QMessageBox.warning(self, "Ошибка", "Сценарий не найден")

    def _remove_scenario(self):
        """Remove the selected scenario."""
        item = self.scenario_list.currentItem()
        if not item:
            return
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить сценарий \"{self.scenario_list.currentItem().text()}\"?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.scenario_service.remove(scenario_id)
                self.status_message.emit("Сценарий удален")
                self._refresh_scenarios()
            except ScenarioNotFoundError:
                QMessageBox.warning(self, "Ошибка", "Сценарий не найден")

    def _run_scenario(self):
        """Run the selected scenario with the last used methodology (or default) and dataset."""
        item = self.scenario_list.currentItem()
        if not item:
            return
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            scenario = self.scenario_service.get(scenario_id)
            # Determine methodology to use
            method_name = self._last_used_methodology.get(scenario_id)
            if not method_name and self.service_container:
                # Get the first available methodology id (qualified name) from the registry
                registered = self.service_container.registered_methodology_ids()
                if registered:
                    method_name = registered[0]
            if not method_name:
                raise ValueError("Нет доступной методологии для запуска сценария")
            # Run the scenario (result is stored in the scenario service)
            self.scenario_service.run(scenario_id, method_name)
            # Store the methodology as last used for this scenario
            self._last_used_methodology[scenario_id] = method_name
            self.status_message.emit(f"Сценарий '{scenario.name}' запущен с методикой '{method_name}'")
        except (ScenarioNotFoundError, CalculationError, ValueError) as e:
            self.error.emit(str(e))

    def _run_with_methodology(self):
        """Run the selected scenario with the selected methodology."""
        item = self.scenario_list.currentItem()
        if not item:
            return
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        methodology_name = self.combo_methodology.currentText()
        if not methodology_name:
            self.error.emit("Выберите методику")
            return
        try:
            scenario = self.scenario_service.get(scenario_id)
            self.scenario_service.run(scenario_id, methodology_name)
            # Store the methodology as last used for this scenario
            self._last_used_methodology[scenario_id] = methodology_name
            self.status_message.emit(f"Сценарий '{scenario.name}' запущен с методикой '{methodology_name}'")
        except (ScenarioNotFoundError, CalculationError) as e:
            self.error.emit(str(e))

    def _compare_scenarios(self):
        """Compare selected scenarios (or all if none selected)."""
        if not self.scenario_service:
            return
        selected_items = self.scenario_list.selectedItems()
        scenario_ids = []
        if selected_items:
            for item in selected_items:
                scenario_ids.append(item.data(Qt.ItemDataRole.UserRole))
        else:
            # Compare all scenarios
            scenario_ids = None
        try:
            # Compare parameters
            param_rows = self.scenario_service.compare(scenario_ids)
            # Compare results
            result_rows = self.scenario_service.compare_results(scenario_ids)
            # Get scenario names for headers
            scenarios = self.scenario_service.list() if scenario_ids is None else [self.scenario_service.get(sid) for sid in scenario_ids]
            scenario_names = [s.name for s in scenarios]
            # Show parameters and results in separate tables
            self._show_parameter_comparison(param_rows, scenario_names)
            self._show_result_comparison(result_rows, scenario_names)
        except Exception as e:
            self.error.emit(f"Не удалось сравнить сценарии: {e}")

    def _show_parameter_comparison(self, rows: list[dict], scenario_names: list[str]):
        """Show parameter comparison in a table."""
        if not rows:
            self.compare_param_table.setRowCount(0)
            self.compare_param_table.setColumnCount(0)
            return
        # Columns: parameter, then each scenario
        self.compare_param_table.setColumnCount(len(scenario_names) + 1)
        headers = ["Параметр"] + scenario_names
        self.compare_param_table.setHorizontalHeaderLabels(headers)
        self.compare_param_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            # Parameter name
            param_item = QTableWidgetItem(row.get("parameter", ""))
            param_item.setFlags(param_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.compare_param_table.setItem(row_idx, 0, param_item)
            # Scenario values
            for col_idx, name in enumerate(scenario_names, start=1):
                value = row.get(name)
                # Format value for display
                if value is None:
                    display = ""
                elif isinstance(value, float):
                    display = f"{value:.4g}"
                else:
                    display = str(value)
                item = QTableWidgetItem(display)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.compare_param_table.setItem(row_idx, col_idx, item)
        self.compare_param_table.resizeColumnsToContents()

    def _show_result_comparison(self, rows: list[dict], scenario_names: list[str]):
        """Show result comparison in a table."""
        if not rows:
            self.compare_result_table.setRowCount(0)
            self.compare_result_table.setColumnCount(0)
            return
        # Columns: Scenario, Status, Output (as JSON string)
        self.compare_result_table.setColumnCount(3)
        headers = ["Сценарий", "Статус", "Выходные данные"]
        self.compare_result_table.setHorizontalHeaderLabels(headers)
        self.compare_result_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            scenario_item = QTableWidgetItem(row.get("scenario", ""))
            scenario_item.setFlags(scenario_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.compare_result_table.setItem(row_idx, 0, scenario_item)
            status_item = QTableWidgetItem(str(row.get("status", "")))
            status_item.setFlags(status_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.compare_result_table.setItem(row_idx, 1, status_item)
            output = row.get("output", {})
            # Format output as JSON string for display
            import json
            output_str = json.dumps(output, ensure_ascii=False, indent=2)
            output_item = QTableWidgetItem(output_str)
            output_item.setFlags(output_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.compare_result_table.setItem(row_idx, 2, output_item)
        self.compare_result_table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # P1.7 Reservoir Scenario Simulator
    # ------------------------------------------------------------------
    def _require_reservoir_service(self) -> ReservoirScenarioService | None:
        if self.reservoir_service is None and self.scenario_service is not None:
            self.reservoir_service = ReservoirScenarioService(self.scenario_service)
        if self.reservoir_service is None:
            self.error.emit("Сервис сценариев недоступен")
        return self.reservoir_service

    def _create_reservoir_scenario(self):
        """Create a scenario typed as reservoir with regulation parameters."""
        service = self._require_reservoir_service()
        if service is None:
            return
        name = self.edit_res_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Ошибка", "Введите название сценария")
            return
        try:
            scenario = service.create(
                name=name,
                demand_m3_s=self.spin_res_demand.value(),
                v_max_km3=self.spin_res_vmax.value() or None,
                s0_km3=self.spin_res_s0.value() or None,
                target_guarantee=self.spin_res_guarantee.value(),
                mode=self.combo_res_mode.currentText(),
            )
        except ReservoirScenarioError as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return
        self.status_message.emit(f"Создан reservoir-сценарий: {scenario.name}")
        self._refresh_scenarios()
        for i in range(self.scenario_list.count()):
            item = self.scenario_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == scenario.id:
                self.scenario_list.setCurrentItem(item)
                break

    def _run_reservoir_scenario(self):
        """Run the selected reservoir scenario through multi_year_regulation."""
        service = self._require_reservoir_service()
        if service is None:
            return
        item = self.scenario_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Ошибка", "Выберите сценарий в списке")
            return
        scenario_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            result = service.run(scenario_id)
            self.status_message.emit(
                f"Reservoir-сценарий выполнен: гарантия "
                f"{result.output_data.get('guarantee_percent', '—')} %"
            )
            self._plot_balance_series(scenario_id)
        except (
            ScenarioNotFoundError,
            ReservoirScenarioError,
            CalculationError,
            ValueError,
        ) as e:
            self.error.emit(str(e))

    def _compare_reservoir_delta(self):
        """Build a numeric Δ table across stored reservoir results."""
        service = self._require_reservoir_service()
        if service is None:
            return
        selected_items = self.scenario_list.selectedItems()
        scenario_ids = (
            [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
            if selected_items
            else None
        )
        try:
            rows = service.compare_delta(scenario_ids)
        except (ScenarioNotFoundError, ReservoirScenarioError) as e:
            self.error.emit(str(e))
            return
        if not rows:
            self.compare_result_table.setRowCount(0)
            self.compare_result_table.setColumnCount(0)
            self.status_message.emit("Нет результатов для сравнения — запустите сценарии")
            return
        self._show_delta_table(rows)
        self.status_message.emit(f"Δ-таблица: {len(rows)} метрик")

    def _show_delta_table(self, rows: list[dict]):
        """Render compare_numeric_results rows (metric / baseline / values / Δ)."""
        # Collect ordered non-delta columns first, then Δ columns.
        base_cols = ["metric", "baseline"]
        value_cols: list[str] = []
        delta_cols: list[str] = []
        for row in rows:
            for key in row:
                if key in base_cols or key in value_cols or key in delta_cols:
                    continue
                if key.startswith("Δ "):
                    delta_cols.append(key)
                else:
                    value_cols.append(key)
        headers = base_cols + value_cols + delta_cols
        self.compare_result_table.setColumnCount(len(headers))
        self.compare_result_table.setHorizontalHeaderLabels(headers)
        self.compare_result_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, key in enumerate(headers):
                value = row.get(key)
                if value is None:
                    display = ""
                elif isinstance(value, float):
                    display = f"{value:.4g}"
                else:
                    display = str(value)
                cell = QTableWidgetItem(display)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.compare_result_table.setItem(row_idx, col_idx, cell)
        self.compare_result_table.resizeColumnsToContents()

    def _plot_balance_series(self, scenario_id: UUID):
        """Plot balance_series_km3 of a run reservoir scenario."""
        service = self._require_reservoir_service()
        if service is None:
            return
        try:
            series = service.series_for(scenario_id)
        except (ScenarioNotFoundError, ReservoirScenarioError) as e:
            self.error.emit(str(e))
            return
        self.figure_balance.clear()
        axes = self.figure_balance.add_subplot(111)
        axes.plot(range(len(series)), series, marker="o", markersize=3, linewidth=1.2)
        axes.set_xlabel("Шаг (год + S₀)")
        axes.set_ylabel("км³")
        axes.grid(True, alpha=0.3)
        self.figure_balance.tight_layout()
        self.canvas_balance.draw_idle()

    def _populate_methodology_combo(self):
        """Fill the methodology combo from the service container registry."""
        if not self.service_container:
            return
        self.combo_methodology.clear()
        for methodology_id in self.service_container.registered_methodology_ids():
            descriptor = self.service_container.registry.get(methodology_id)
            self.combo_methodology.addItem(descriptor.name, descriptor.qualified_name)
