"""
gui/dialogs/calibration_dialog.py
Диалог калибровки параметров (P1.5, DOCS/ROADMAP.md).

Выбор модели (лигейшн / показательная), метрики (MSE/NSE), стартовых
параметров и limits → фоновый CalibrationWorker → метрика «до/после»,
применение к сценарию через ScenarioService. Математика только в ядре
(scipy.optimize + core.stats.metrics).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import numpy as np
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.domain.models import Dataset
from core.services.calibration_service import (
    AVAILABLE_METRICS,
    CalibrationError,
    CalibrationRequest,
    CalibrationService,
)
from core.services.scenario_service import ScenarioService

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

#: model_id -> (label, param names with default start/limits)
_MODELS: dict[str, tuple[str, list[tuple[str, float, float, float]]]] = {
    "linear": (
        "Линейная: y = a + b·x",
        [
            ("a", 0.0, -1e6, 1e6),
            ("b", 1.0, -1e3, 1e3),
        ],
    ),
    "exp": (
        "Показательная: y = a·exp(b·x)",
        [
            ("a", 1.0, 0.0, 1e6),
            ("b", 0.0, -50.0, 50.0),
        ],
    ),
}


def _make_predict(model_id: str, x: np.ndarray):
    """Build predict(params) -> y for the selected model (closed over x)."""

    if model_id == "exp":

        def predict_exp(params: dict[str, float]) -> np.ndarray:
            a = float(params["a"])
            b = float(params["b"])
            # Clip exponent to avoid overflow during optimization.
            expo = np.clip(b * x, -700.0, 700.0)
            return a * np.exp(expo)

        return predict_exp

    def predict_linear(params: dict[str, float]) -> np.ndarray:
        a = float(params["a"])
        b = float(params["b"])
        return a + b * x

    return predict_linear


class CalibrationWorker(QThread):
    """Run CalibrationService.calibrate off the UI thread."""

    ready = pyqtSignal(object)  # CalculationResult
    failed = pyqtSignal(str)

    def __init__(
        self,
        observed: list[float],
        x: np.ndarray,
        model_id: str,
        initial: dict[str, float],
        bounds: dict[str, tuple[float | None, float | None]],
        metric: str,
        method: str = "L-BFGS-B",
        max_iterations: int = 500,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._observed = observed
        self._x = x
        self._model_id = model_id
        self._initial = dict(initial)
        self._bounds = dict(bounds)
        self._metric = metric
        self._method = method
        self._max_iterations = max_iterations

    def run(self) -> None:  # noqa: D102 - QThread entry
        try:
            service = CalibrationService()
            request = CalibrationRequest(
                initial=self._initial,
                bounds=self._bounds,
                metric=self._metric,
                method=self._method,
                max_iterations=self._max_iterations,
            )
            result = service.calibrate(
                self._observed,
                _make_predict(self._model_id, self._x),
                request,
            )
        except CalibrationError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # surface to dialog, never crash the app
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.ready.emit(result)


class CalibrationDialog(QDialog):
    """Подбор параметров модели к наблюдаемому ряду с limits и метрикой."""

    #: Emitted after a successful run so MainWindow can store provenance.
    calibration_finished = pyqtSignal(object)  # CalculationResult

    def __init__(
        self,
        dataset: Dataset,
        post_name: str,
        *,
        scenario_service: ScenarioService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("calibration_title", "Калибровка параметров"))
        self.setMinimumSize(780, 560)
        self._dataset = dataset
        self._post_name = post_name
        self._scenario_service = scenario_service
        self._worker: CalibrationWorker | None = None
        self._progress: QProgressDialog | None = None
        self._result = None  # last CalculationResult
        self._fitted: dict[str, float] = {}
        self._build_ui()
        self._init_params_table()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel(t("calibration_title", "Калибровка параметров"))
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            t(
                "calibration_hint",
                "Метрика и limits задаются явно; оптимизация идёт в фоне "
                "(scipy.optimize). Результат — параметры «до/после» и запись "
                "в историю расчётов; применение к сценарию — только по кнопке.",
            )
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(HINT_STYLE)
        layout.addWidget(hint)

        settings = QGroupBox(t("calibration_settings", "Настройки"))
        form = QFormLayout(settings)
        self._model_combo = QComboBox()
        for model_id, (label, _) in _MODELS.items():
            self._model_combo.addItem(label, model_id)
        self._model_combo.currentIndexChanged.connect(self._init_params_table)
        self._metric_combo = QComboBox()
        for metric_id in AVAILABLE_METRICS:
            label = "MSE" if metric_id == "mse" else "NSE"
            self._metric_combo.addItem(label, metric_id)
        self._metric_combo.setCurrentIndex(1)  # default NSE (decision 9.5)
        self._method_combo = QComboBox()
        for method in ("L-BFGS-B", "Nelder-Mead", "Powell"):
            self._method_combo.addItem(method, method)
        form.addRow(t("calibration_model", "Модель:") + ":", self._model_combo)
        form.addRow(t("calibration_metric", "Метрика:") + ":", self._metric_combo)
        form.addRow(t("calibration_method", "Метод:") + ":", self._method_combo)
        layout.addWidget(settings)

        params_group = QGroupBox(t("calibration_params", "Параметры и limits"))
        params_layout = QVBoxLayout(params_group)
        self._params_table = QTableWidget(0, 4)
        self._params_table.setHorizontalHeaderLabels(
            [
                t("calibration_col_param", "Параметр"),
                t("calibration_col_start", "Старт"),
                t("calibration_col_lower", "Нижн."),
                t("calibration_col_upper", "Верхн."),
            ]
        )
        self._params_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._params_table.setEditTriggers(
            QTableWidget.EditTrigger.DoubleClicked
            | QTableWidget.EditTrigger.SelectedClicked
            | QTableWidget.EditTrigger.EditKeyPressed
        )
        self._params_table.setMaximumHeight(160)
        params_layout.addWidget(self._params_table)
        layout.addWidget(params_group)

        result_group = QGroupBox(t("calibration_result", "Результат"))
        result_layout = QVBoxLayout(result_group)
        self._result_label = QLabel("—")
        self._result_label.setWordWrap(True)
        result_layout.addWidget(self._result_label)
        self._result_text = QPlainTextEdit()
        self._result_text.setReadOnly(True)
        self._result_text.setMaximumHeight(140)
        result_layout.addWidget(self._result_text)
        layout.addWidget(result_group, stretch=1)

        scenario_row = QHBoxLayout()
        self._scenario_combo = QComboBox()
        self._scenario_combo.addItem(t("calibration_no_scenario", "— без сценария —"), None)
        self._fill_scenarios()
        scenario_row.addWidget(
            QLabel(t("calibration_apply_to", "Применить к сценарию:") + ":")
        )
        scenario_row.addWidget(self._scenario_combo, stretch=1)
        layout.addLayout(scenario_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._btn_close = QPushButton(t("btn_cancel", "Закрыть"))
        self._btn_close.clicked.connect(self.reject)
        self._btn_apply = QPushButton(t("calibration_apply", "Применить"))
        self._btn_apply.setEnabled(False)
        self._btn_apply.clicked.connect(self._on_apply)
        self._btn_run = QPushButton(t("calibration_run", "Калибровать"))
        self._btn_run.clicked.connect(self._on_run)
        buttons.addWidget(self._btn_close)
        buttons.addWidget(self._btn_apply)
        buttons.addWidget(self._btn_run)
        layout.addLayout(buttons)

    def _init_params_table(self) -> None:
        model_id = self._model_combo.currentData() or "linear"
        rows = _MODELS[model_id][1]
        self._params_table.setRowCount(len(rows))
        for row, (name, start, lo, hi) in enumerate(rows):
            for col, text in enumerate((name, str(start), str(lo), str(hi))):
                item = QTableWidgetItem(text)
                if col == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._params_table.setItem(row, col, item)
        self._result_label.setText("—")
        self._result_text.clear()
        self._btn_apply.setEnabled(False)
        self._result = None
        self._fitted = {}

    def _fill_scenarios(self) -> None:
        if self._scenario_service is None:
            return
        try:
            for scenario in self._scenario_service.list():
                self._scenario_combo.addItem(scenario.name, str(scenario.id))
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[WARN] calibration scenarios: {exc}")

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    def _collect_request(self) -> dict[str, Any] | None:
        initial: dict[str, float] = {}
        bounds: dict[str, tuple[float | None, float | None]] = {}
        for row in range(self._params_table.rowCount()):
            name_item = self._params_table.item(row, 0)
            start_item = self._params_table.item(row, 1)
            lo_item = self._params_table.item(row, 2)
            hi_item = self._params_table.item(row, 3)
            if name_item is None or start_item is None:
                continue
            name = name_item.text().strip()
            try:
                start = float(start_item.text().strip())
                lo = float(lo_item.text().strip()) if lo_item else float("-inf")
                hi = float(hi_item.text().strip()) if hi_item else float("inf")
            except (ValueError, AttributeError):
                QMessageBox.warning(
                    self,
                    t("calibration_title", "Калибровка параметров"),
                    t("calibration_bad_limits", "Limits и старт — числа (пусто = ±inf)."),
                )
                return None
            initial[name] = start
            bounds[name] = (lo, hi)

        if not initial:
            QMessageBox.warning(
                self,
                t("calibration_title", "Калибровка параметров"),
                t("calibration_no_params", "Нет параметров для калибровки."),
            )
            return None

        years = sorted(int(y) for y in self._dataset.data)
        values = [float(self._dataset.data[y]) for y in years]
        x = np.asarray(years, dtype=float)
        if x.size > 1:
            # Normalize x to 0..1 for numerical stability of large year numbers.
            span = float(x[-1] - x[0]) or 1.0
            x = (x - float(x[0])) / span

        model_id = str(self._model_combo.currentData() or "linear")
        metric = str(self._metric_combo.currentData() or "nse")
        method = str(self._method_combo.currentData() or "L-BFGS-B")
        return {
            "observed": values,
            "x": x,
            "model_id": model_id,
            "initial": initial,
            "bounds": bounds,
            "metric": metric,
            "method": method,
        }

    def _on_run(self) -> None:
        payload = self._collect_request()
        if payload is None:
            return
        self._btn_run.setEnabled(False)
        self._btn_apply.setEnabled(False)

        self._progress = QProgressDialog(
            t("calibration_running", "Калибровка…"), None, 0, 0, self
        )
        self._progress.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress.setMinimumDuration(0)
        self._progress.setValue(0)

        self._worker = CalibrationWorker(
            payload["observed"],
            payload["x"],
            payload["model_id"],
            payload["initial"],
            payload["bounds"],
            payload["metric"],
            method=payload["method"],
        )
        self._worker.ready.connect(self._on_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_ready(self, result: object) -> None:
        self._close_progress()
        self._btn_run.setEnabled(True)
        self._result = result
        output = getattr(result, "output_data", {}) or {}
        before = output.get("metric_before")
        after = output.get("metric_after")
        metric = output.get("metric", "")
        fitted = output.get("parameters_after", {}) or {}
        self._fitted = {str(k): float(v) for k, v in fitted.items()}
        iterations = output.get("iterations", 0)
        success = output.get("success", False)
        label = "MSE" if metric == "mse" else "NSE"
        self._result_label.setText(
            f"{label}: {before:.6g} → {after:.6g} · "
            f"итераций: {iterations} · "
            f"{'OK' if success else output.get('message', 'частично')}"
        )
        lines = [f"{k} = {v:.6g}" for k, v in self._fitted.items()]
        before_params = output.get("parameters_before", {}) or {}
        lines += [f"{k}_0 = {v:.6g}" for k, v in before_params.items()]
        self._result_text.setPlainText("\n".join(lines))
        self._btn_apply.setEnabled(bool(self._fitted))
        self.calibration_finished.emit(result)
        self._status = t("calibration_done", "Калибровка выполнена")
        if self.parent() is not None and hasattr(self.parent(), "_status_bar"):
            self.parent()._status_bar.showMessage(self._status)

    def _on_failed(self, message: str) -> None:
        self._close_progress()
        self._btn_run.setEnabled(True)
        self._result = None
        self._fitted = {}
        self._btn_apply.setEnabled(False)
        self._result_label.setText("—")
        QMessageBox.critical(
            self,
            t("calibration_title", "Калибровка параметров"),
            message or t("calibration_failed", "Калибровка не выполнена."),
        )

    def _on_apply(self) -> None:
        if not self._fitted:
            return
        scenario_id = self._scenario_combo.currentData()
        if scenario_id is None or self._scenario_service is None:
            QMessageBox.information(
                self,
                t("calibration_title", "Калибровка параметров"),
                t("calibration_pick_scenario", "Выберите сценарий для применения."),
            )
            return
        try:
            sid = UUID(str(scenario_id))
            CalibrationService.apply_to_scenario(
                self._scenario_service, sid, self._fitted
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                t("calibration_title", "Калибровка параметров"),
                str(exc),
            )
            return
        QMessageBox.information(
            self,
            t("calibration_title", "Калибровка параметров"),
            t("calibration_applied", "Параметры применены к сценарию."),
        )
        self.accept()

    def _close_progress(self) -> None:
        if self._progress is not None:
            self._progress.close()
            self._progress = None

    def done(self, result: int) -> None:  # noqa: D102 - QDialog override
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(2000)
        self._close_progress()
        super().done(result)
