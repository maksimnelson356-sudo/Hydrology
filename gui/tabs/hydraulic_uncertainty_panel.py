"""Non-blocking P3.4 hydraulic uncertainty panel."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.services.hydraulic_uncertainty_service import (
    HydraulicUncertaintyError,
    HydraulicUncertaintyRequest,
    HydraulicUncertaintyResult,
)
from gui.tabs.hydraulic_uncertainty_result_view import HydraulicResultView
from gui.tabs.hydraulic_uncertainty_support import (
    HydraulicEngine,
    HydraulicParameterRow,
    build_hydraulic_request,
    default_parameter_rows,
    parse_engine,
)
from gui.workers.hydraulic_uncertainty_worker import HydraulicUncertaintyWorker

_PANEL_TITLE_STYLE = "font-size: 15px; font-weight: bold; color: #0D47A1;"
_PANEL_HINT_STYLE = (
    "color: #546E7A; font-size: 11px; padding: 8px; "
    "background: #F5F7FA; border-radius: 4px;"
)
_PANEL_RUN_STYLE = (
    "QPushButton { background-color: #00695C; color: white; font-weight: bold; "
    "padding: 9px; border-radius: 6px; }"
    "QPushButton:hover { background-color: #004D40; }"
    "QPushButton:disabled { background-color: #90A4AE; }"
)

_PARAMETER_HEADERS = ("Параметр", "Распределение", "low", "high")
_METRIC_HEADERS = ("Метрика", "p5", "p50", "p95", "mean", "std")


class HydraulicUncertaintyPanel(QWidget):
    """Configure and inspect seedable P3.1/P3.2/P3.3 uncertainty runs."""

    status_message = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Гидравлический Monte Carlo — P3.4")
        self.resize(1000, 760)
        self._worker: HydraulicUncertaintyWorker | None = None
        self._result: HydraulicUncertaintyResult | None = None
        self._build_ui()
        self._populate_parameters()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Гидравлический Monte Carlo — неопределённость P3.1/P3.2/P3.3")
        title.setStyleSheet(_PANEL_TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            "Задайте seed и число прогонов. Панель использует демонстрационные "
            "геометрические модели; p5/p50/p95 рассчитываются после полного "
            "прогона каждого набора параметров."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(_PANEL_HINT_STYLE)
        layout.addWidget(hint)

        controls_box = QGroupBox("Параметры прогона")
        controls = QHBoxLayout(controls_box)
        form = QFormLayout()
        self.hydraulic_engine = QComboBox()
        self.hydraulic_engine.addItem("Backwater: глубина / площадь / объём", "backwater")
        self.hydraulic_engine.addItem("Routing: пики / attenuation / lag", "routing")
        form.addRow("Гидравлический движок:", self.hydraulic_engine)

        self.hydraulic_n = QSpinBox()
        self.hydraulic_n.setRange(1, 100_000)
        self.hydraulic_n.setValue(200)
        self.hydraulic_n.setSingleStep(10)
        form.addRow("Прогонов N:", self.hydraulic_n)

        self.hydraulic_seed = QSpinBox()
        self.hydraulic_seed.setRange(0, 2_147_483_647)
        self.hydraulic_seed.setValue(42)
        form.addRow("Seed:", self.hydraulic_seed)
        controls.addLayout(form)

        self.hydraulic_run_button = QPushButton("Запустить P3.4")
        self.hydraulic_run_button.setStyleSheet(_PANEL_RUN_STYLE)
        self.hydraulic_run_button.clicked.connect(self._on_run_clicked)
        controls.addWidget(self.hydraulic_run_button)
        controls.addStretch()
        layout.addWidget(controls_box)

        parameters_box = QGroupBox("Неопределённые параметры (uniform)")
        parameters_layout = QVBoxLayout(parameters_box)
        self.hydraulic_parameters = QTableWidget(0, len(_PARAMETER_HEADERS))
        self.hydraulic_parameters.setHorizontalHeaderLabels(list(_PARAMETER_HEADERS))
        self.hydraulic_parameters.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.hydraulic_parameters.setMinimumHeight(150)
        parameters_layout.addWidget(self.hydraulic_parameters)
        layout.addWidget(parameters_box)

        result_box = QGroupBox("Квантили результата")
        result_layout = QVBoxLayout(result_box)
        self.hydraulic_table = QTableWidget(0, len(_METRIC_HEADERS))
        self.hydraulic_table.setHorizontalHeaderLabels(list(_METRIC_HEADERS))
        self.hydraulic_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.hydraulic_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.hydraulic_table.setMinimumHeight(150)
        result_layout.addWidget(self.hydraulic_table)

        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.figure import Figure

        self.hydraulic_figure = Figure(figsize=(8, 3), tight_layout=True)
        self.hydraulic_canvas = FigureCanvas(self.hydraulic_figure)
        self.hydraulic_canvas.setMinimumHeight(240)
        self._result_view = HydraulicResultView(
            self.hydraulic_table,
            self.hydraulic_figure,
            self.hydraulic_canvas,
        )
        result_layout.addWidget(self.hydraulic_canvas)
        layout.addWidget(result_box, stretch=1)

        self.hydraulic_status = QLabel("Готово к запуску")
        self.hydraulic_status.setWordWrap(True)
        layout.addWidget(self.hydraulic_status)

        self.hydraulic_engine.currentIndexChanged.connect(self._on_engine_changed)

    def _populate_parameters(self) -> None:
        rows = default_parameter_rows(self._current_engine())
        self.hydraulic_parameters.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            self.hydraulic_parameters.setItem(row_index, 0, QTableWidgetItem(row.name))
            self.hydraulic_parameters.setItem(row_index, 1, QTableWidgetItem(row.distribution))
            self.hydraulic_parameters.setItem(row_index, 2, QTableWidgetItem(row.low))
            self.hydraulic_parameters.setItem(row_index, 3, QTableWidgetItem(row.high))

    def _current_engine(self) -> HydraulicEngine:
        return parse_engine(str(self.hydraulic_engine.currentData()))

    def build_request(self) -> HydraulicUncertaintyRequest:
        """Build a validated request from the current panel controls."""
        rows: list[HydraulicParameterRow] = []
        for row_index in range(self.hydraulic_parameters.rowCount()):
            name_item = self.hydraulic_parameters.item(row_index, 0)
            dist_item = self.hydraulic_parameters.item(row_index, 1)
            low_item = self.hydraulic_parameters.item(row_index, 2)
            high_item = self.hydraulic_parameters.item(row_index, 3)
            rows.append(
                HydraulicParameterRow(
                    name=name_item.text() if name_item is not None else "",
                    distribution=dist_item.text() if dist_item is not None else "",
                    low=low_item.text() if low_item is not None else "",
                    high=high_item.text() if high_item is not None else "",
                )
            )
        return build_hydraulic_request(
            self._current_engine(),
            tuple(rows),
            self.hydraulic_n.value(),
            self.hydraulic_seed.value(),
        )

    def _on_engine_changed(self, _index: int) -> None:
        self._populate_parameters()
        self._clear_result()
        self.hydraulic_status.setText("Параметры обновлены для выбранного движка")

    def _clear_result(self) -> None:
        self._result = None
        self._result_view.clear()
        self.hydraulic_status.setText("Готово к запуску")

    def show_result(self, result: HydraulicUncertaintyResult) -> None:
        """Render metric quantiles and a compact p5/p50/p95 comparison plot."""
        self._result = result
        self._result_view.show(result)
        message = (
            f"Готово: {result.engine}, N={result.n_runs}, seed={result.seed}; "
            f"provenance={result.provenance}"
        )
        self.hydraulic_status.setText(message)
        self.status_message.emit(message)

    def _on_run_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        try:
            request = self.build_request()
        except HydraulicUncertaintyError as error:
            self.error.emit(str(error))
            QMessageBox.critical(self, "Гидравлический Monte Carlo", str(error))
            return

        self.hydraulic_run_button.setEnabled(False)
        status = f"Выполняется {request.n_runs} прогонов…"
        self.hydraulic_status.setText(status)
        self.status_message.emit(status)
        self._worker = HydraulicUncertaintyWorker(request, parent=self)
        self._worker.result_ready.connect(self.show_result)
        self._worker.error.connect(self._on_run_error)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_run_error(self, message: str) -> None:
        self.error.emit(message)
        status = f"Ошибка: {message}"
        self.hydraulic_status.setText(status)
        self.status_message.emit(status)
        QMessageBox.critical(self, "Гидравлический Monte Carlo", message)

    def _on_worker_finished(self) -> None:
        self.hydraulic_run_button.setEnabled(True)
        self._worker = None

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt naming
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait()
        super().closeEvent(event)
