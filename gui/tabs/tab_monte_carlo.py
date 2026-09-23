"""
gui/tabs/tab_monte_carlo.py
Вкладка «Monte Carlo» (P2.1): настройка распределений входных параметров,
прогон N итераций в фоновом воркере, сводка (mean/std/p5/p50/p95) и
гистограмма с квантилями matplotlib.

Блоки:
- P2.2 «Чувствительность»: OAT ±Δ и tornado-ранжирование (SensitivityService).
- P2.3 «Климат»: delta-change ×(1+δ) на демо-ряд (ClimateService), до/после.
- P2.5 «Решения»: P(exceed) и класс риска по пользовательскому Q_крит
  (DecisionSupportService, решение 10.3 (а)).

Графики — хелперы `gui/plot_style` (P2.4). Математика — только в сервисах.
Без новых runtime-зависимостей (решения 10.1, 10.2, 10.3 (а)).
"""

from __future__ import annotations

from typing import Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
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

from core.services.climate_service import (
    CLIMATE_MODES,
    ClimateError,
    ClimateScenario,
    ClimateService,
)
from core.services.decision_support_service import (
    DecisionSupportError,
    DecisionSupportRequest,
    DecisionSupportService,
)
from core.services.monte_carlo_service import (
    DEFAULT_N_RUNS,
    MonteCarloError,
    MonteCarloRequest,
    MonteCarloService,
    ParameterSpec,
)
from core.services.sensitivity_service import (
    DEFAULT_RELATIVE_DELTA,
    SensitivityError,
    SensitivityRequest,
    SensitivityService,
)
from gui.plot_style import (
    draw_fan_chart,
    draw_histogram_quantiles,
    draw_tornado_hbars,
)

HINT_STYLE = (
    "color: #666; font-style: italic; padding: 8px; background: #f0f0f0; border-radius: 4px;"
)
TITLE_STYLE = "font-size: 15px; font-weight: bold; color: #0D47A1;"
RUN_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; font-weight: bold; "
    "padding: 10px; font-size: 13px; border-radius: 6px; }"
    "QPushButton:hover { background-color: #0D47A1; }"
)

#: Demo model parameter rows: (name, distribution, low/high | mean/std | left/mode/right)
_DEFAULT_ROWS: list[tuple[str, str, dict[str, float]]] = [
    ("a", "normal", {"mean": 2.0, "std": 0.3}),
    ("b", "uniform", {"low": -1.0, "high": 1.0}),
    ("c", "triangular", {"left": 0.0, "mode": 1.0, "right": 5.0}),
]

_PARAM_HEADERS = (
    "Имя",
    "Распределение",
    "Параметр 1",
    "Параметр 2",
    "Параметр 3",
)

#: Demo hydrological series for climate before/after (year → Q m³/s).
_CLIMATE_DEMO: dict[int, float] = {
    2000: 12.0,
    2001: 15.5,
    2002: 11.0,
    2003: 18.0,
    2004: 14.2,
    2005: 16.8,
    2006: 13.1,
    2007: 17.4,
}


class MonteCarloWorker(QThread):
    """Фоновый прогон Monte Carlo (не блокирует UI)."""

    finished = pyqtSignal(object)  # CalculationResult
    error = pyqtSignal(str)

    def __init__(
        self,
        model: Any,
        request: MonteCarloRequest,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._request = request

    def run(self) -> None:  # noqa: D102 — QThread entry point
        try:
            result = MonteCarloService.run(self._model, self._request)
        except MonteCarloError as exc:
            self.error.emit(str(exc))
            return
        except Exception as exc:  # noqa: BLE001 — surface any model failure
            self.error.emit(f"{type(exc).__name__}: {exc}")
            return
        self.finished.emit(result)


class TabMonteCarlo(QWidget):
    """Раздел «Monte Carlo»: семплирование, прогон, сводка и гистограмма."""

    status_message = pyqtSignal(str)
    error = pyqtSignal(str)
    run_finished = pyqtSignal(object)  # CalculationResult

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = MonteCarloService()
        self._worker: MonteCarloWorker | None = None
        self._result: Any = None
        self._sensitivity_result: Any = None
        self._climate_result: dict[int, float] | None = None
        self._ds_result: Any = None
        self._build_ui()

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------
    @property
    def result(self) -> Any:
        """Last successful CalculationResult (or None)."""
        return self._result

    def build_request(self) -> MonteCarloRequest:
        """Assemble MonteCarloRequest from the parameter table + N/seed."""
        rows = self.table.rowCount()
        if rows == 0:
            raise MonteCarloError("Добавьте хотя бы один параметр")
        specs: list[ParameterSpec] = []
        for row in range(rows):
            name_item = self.table.item(row, 0)
            dist_item = self.table.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            dist = (dist_item.text() if dist_item else "").strip()
            params: dict[str, float] = {}
            for col, key in ((2, "p1"), (3, "p2"), (4, "p3")):
                item = self.table.item(row, col)
                if item is None or not item.text().strip():
                    continue
                try:
                    params[key] = float(item.text().replace(",", "."))
                except ValueError as exc:
                    raise MonteCarloError(
                        f"Строка {row + 1}, колонка {col}: «{item.text()}» не число"
                    ) from exc
            specs.append(self._make_spec(name, dist, params))
        seed_text = self.spin_seed.cleanText()
        seed: int | None
        if seed_text == "0" and not self.chk_seed.isChecked():
            seed = None
        else:
            seed = int(self.spin_seed.value())
        return MonteCarloRequest(
            parameters=tuple(specs),
            n_runs=int(self.spin_n.value()),
            seed=seed,
        )

    @staticmethod
    def _make_spec(name: str, dist: str, raw: dict[str, float]) -> ParameterSpec:
        """Map UI column keys to distribution-specific parameter names."""
        dist_l = dist.strip().lower()
        if dist_l == "uniform":
            if "p1" not in raw or "p2" not in raw:
                raise MonteCarloError(f"uniform «{name}»: нужны low и high")
            return ParameterSpec(
                name=name, distribution=dist_l, params={"low": raw["p1"], "high": raw["p2"]}
            )
        if dist_l == "normal":
            if "p1" not in raw or "p2" not in raw:
                raise MonteCarloError(f"normal «{name}»: нужны mean и std")
            return ParameterSpec(
                name=name, distribution=dist_l, params={"mean": raw["p1"], "std": raw["p2"]}
            )
        if "p1" not in raw or "p2" not in raw or "p3" not in raw:
            raise MonteCarloError(f"triangular «{name}»: нужны left, mode, right")
        return ParameterSpec(
            name=name,
            distribution=dist_l,
            params={"left": raw["p1"], "mode": raw["p2"], "right": raw["p3"]},
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Monte Carlo — пропагация неопределённостей (P2.1)")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            "Задайте распределения входных параметров (uniform / normal / triangular, "
            f"решение 10.1), число прогонов N (по умолчанию {DEFAULT_N_RUNS}, "
            "решение 10.2) и seed для воспроизводимости. Демо-модель: y = a·x + b, x = 1."
        )
        hint.setStyleSheet(HINT_STYLE)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Controls: N / seed / run
        controls = QHBoxLayout()
        form_n = QFormLayout()
        self.spin_n = QSpinBox()
        self.spin_n.setRange(1, 100_000)
        self.spin_n.setValue(DEFAULT_N_RUNS)
        self.spin_n.setSingleStep(100)
        form_n.addRow("Прогонов N:", self.spin_n)
        controls.addLayout(form_n)

        form_seed = QFormLayout()
        self.chk_seed = QCheckBox("Seed")
        self.chk_seed.setChecked(True)
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(0, 2_147_483_647)
        self.spin_seed.setValue(42)
        self.spin_seed.setEnabled(True)
        self.chk_seed.toggled.connect(self.spin_seed.setEnabled)
        seed_row = QHBoxLayout()
        seed_row.addWidget(self.chk_seed)
        seed_row.addWidget(self.spin_seed)
        form_seed.addRow("Seed:", seed_row)
        controls.addLayout(form_seed)

        self.btn_run = QPushButton("▶ Запустить Monte Carlo")
        self.btn_run.setStyleSheet(RUN_STYLE)
        self.btn_run.clicked.connect(self._on_run_clicked)
        controls.addWidget(self.btn_run)
        controls.addStretch()
        layout.addLayout(controls)

        # Parameter table
        params_box = QGroupBox("Входные параметры и распределения")
        params_layout = QVBoxLayout(params_box)
        self.table = QTableWidget(len(_DEFAULT_ROWS), len(_PARAM_HEADERS))
        self.table.setHorizontalHeaderLabels(list(_PARAM_HEADERS))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(120)
        for row, (name, dist, params) in enumerate(_DEFAULT_ROWS):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(dist))
            values = list(params.values())
            for col, value in enumerate(values, start=2):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        params_layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Параметр")
        add_btn.clicked.connect(self._on_add_param)
        del_btn = QPushButton("− Удалить")
        del_btn.clicked.connect(self._on_del_param)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        params_layout.addLayout(btn_row)
        layout.addWidget(params_box)

        # Summary labels
        summary_box = QGroupBox("Сводка выхода y")
        summary_form = QFormLayout(summary_box)
        self.lbl_mean = QLabel("—")
        self.lbl_std = QLabel("—")
        self.lbl_p5 = QLabel("—")
        self.lbl_p50 = QLabel("—")
        self.lbl_p95 = QLabel("—")
        self.lbl_min = QLabel("—")
        self.lbl_max = QLabel("—")
        self.lbl_n = QLabel("—")
        summary_form.addRow("mean:", self.lbl_mean)
        summary_form.addRow("std:", self.lbl_std)
        summary_form.addRow("p5:", self.lbl_p5)
        summary_form.addRow("p50:", self.lbl_p50)
        summary_form.addRow("p95:", self.lbl_p95)
        summary_form.addRow("min:", self.lbl_min)
        summary_form.addRow("max:", self.lbl_max)
        summary_form.addRow("N:", self.lbl_n)
        layout.addWidget(summary_box)

        # Histogram preview
        preview_box = QGroupBox("Гистограмма выхода с квантилями")
        preview_layout = QVBoxLayout(preview_box)
        self._figure = Figure(figsize=(5, 3), tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        preview_layout.addWidget(self._canvas)
        layout.addWidget(preview_box, stretch=1)

        # --- P2.2 sensitivity / tornado block -------------------------
        sens_box = QGroupBox("Чувствительность — Tornado (P2.2)")
        sens_layout = QVBoxLayout(sens_box)

        sens_controls = QHBoxLayout()
        form_rel = QFormLayout()
        self.spin_rel_delta = QDoubleSpinBox()
        self.spin_rel_delta.setRange(0.001, 10.0)
        self.spin_rel_delta.setSingleStep(0.01)
        self.spin_rel_delta.setDecimals(3)
        self.spin_rel_delta.setValue(DEFAULT_RELATIVE_DELTA)
        self.spin_rel_delta.setSuffix(" × |baseline|")
        form_rel.addRow("±Δ (отн.):", self.spin_rel_delta)
        sens_controls.addLayout(form_rel)

        self.btn_tornado = QPushButton("🌪 Построить Tornado")
        self.btn_tornado.setStyleSheet(RUN_STYLE)
        self.btn_tornado.clicked.connect(self._on_tornado_clicked)
        sens_controls.addWidget(self.btn_tornado)
        sens_controls.addStretch()
        sens_layout.addLayout(sens_controls)

        self.lbl_tornado_order = QLabel("Порядок: —")
        self.lbl_tornado_order.setWordWrap(True)
        sens_layout.addWidget(self.lbl_tornado_order)

        self._tornado_figure = Figure(figsize=(5, 2.2), tight_layout=True)
        self._tornado_canvas = FigureCanvas(self._tornado_figure)
        sens_layout.addWidget(self._tornado_canvas)
        layout.addWidget(sens_box, stretch=1)

        # --- P2.3 climate delta-change block --------------------------
        climate_box = QGroupBox("Климат — delta-change (P2.3)")
        climate_layout = QVBoxLayout(climate_box)

        climate_controls = QHBoxLayout()
        form_delta = QFormLayout()
        self.spin_climate_delta = QDoubleSpinBox()
        self.spin_climate_delta.setRange(-0.9, 5.0)
        self.spin_climate_delta.setSingleStep(0.01)
        self.spin_climate_delta.setDecimals(3)
        self.spin_climate_delta.setValue(0.1)
        form_delta.addRow("δ:", self.spin_climate_delta)

        self.combo_climate_mode = QComboBox()
        self.combo_climate_mode.addItems(list(CLIMATE_MODES))
        form_delta.addRow("Режим:", self.combo_climate_mode)
        climate_controls.addLayout(form_delta)

        self.btn_climate = QPushButton("🌡 Применить климат-фактор")
        self.btn_climate.setStyleSheet(RUN_STYLE)
        self.btn_climate.clicked.connect(self._on_climate_clicked)
        climate_controls.addWidget(self.btn_climate)
        climate_controls.addStretch()
        climate_layout.addLayout(climate_controls)

        self.lbl_climate = QLabel("До/после: —")
        self.lbl_climate.setWordWrap(True)
        climate_layout.addWidget(self.lbl_climate)

        self._climate_figure = Figure(figsize=(5, 2.0), tight_layout=True)
        self._climate_canvas = FigureCanvas(self._climate_figure)
        climate_layout.addWidget(self._climate_canvas)
        layout.addWidget(climate_box, stretch=1)

        # --- P2.5 decision support block ------------------------------
        ds_box = QGroupBox("Решения — P(exceed) и риск (P2.5, решение 10.3 (а))")
        ds_layout = QVBoxLayout(ds_box)

        ds_controls = QHBoxLayout()
        form_q = QFormLayout()
        self.edit_q_crit = QDoubleSpinBox()
        self.edit_q_crit.setRange(-1e9, 1e9)
        self.edit_q_crit.setDecimals(3)
        self.edit_q_crit.setValue(14.0)
        form_q.addRow("Q_крит:", self.edit_q_crit)
        ds_controls.addLayout(form_q)

        self.btn_ds = QPushButton("📊 Оценить риск")
        self.btn_ds.setStyleSheet(RUN_STYLE)
        self.btn_ds.clicked.connect(self._on_ds_clicked)
        ds_controls.addWidget(self.btn_ds)
        ds_controls.addStretch()
        ds_layout.addLayout(ds_controls)

        self.lbl_ds = QLabel("P(exceed): —")
        self.lbl_ds.setWordWrap(True)
        ds_layout.addWidget(self.lbl_ds)
        layout.addWidget(ds_box, stretch=1)

    # ------------------------------------------------------------------
    # P2.3 climate
    # ------------------------------------------------------------------
    def build_climate_scenario(self) -> ClimateScenario:
        """Scenario from δ spinbox + mode combo (demo series applied on click)."""
        mode = self.combo_climate_mode.currentText().strip().lower()
        if mode not in CLIMATE_MODES:
            raise ClimateError(f"Неизвестный режим «{mode}»")
        return ClimateScenario(
            name=f"climate δ={self.spin_climate_delta.value():g}",
            delta=float(self.spin_climate_delta.value()),
            mode=mode,
        )

    def _on_climate_clicked(self) -> None:
        try:
            scenario = self.build_climate_scenario()
            before = ClimateService.identity(_CLIMATE_DEMO)
            after = ClimateService.apply_series(_CLIMATE_DEMO, scenario)
        except ClimateError as exc:
            self.error.emit(str(exc))
            QMessageBox.critical(self, "Климат", str(exc))
            return
        self._climate_result = after
        mean_b = sum(before.values()) / len(before)
        mean_a = sum(after.values()) / len(after)
        ratio = mean_a / mean_b if mean_b else float("nan")
        self.lbl_climate.setText(
            f"До/после: mean {mean_b:.4g} → {mean_a:.4g} (ratio {ratio:.4g}); "
            f"режим {scenario.mode}, δ={scenario.delta:g}"
        )
        self._draw_climate(before, after, scenario)
        self.status_message.emit(
            f"Климат: δ={scenario.delta:g} {scenario.mode}, mean {mean_b:.4g}→{mean_a:.4g}"
        )

    def _draw_climate(
        self,
        before: dict[int, float],
        after: dict[int, float],
        scenario: ClimateScenario,
    ) -> None:
        self._climate_figure.clear()
        axes = self._climate_figure.add_subplot(111)
        years = sorted(after)
        med = [after[y] for y in years]
        low = [min(before[y], after[y]) for y in years]
        high = [max(before[y], after[y]) for y in years]
        draw_fan_chart(
            axes,
            years,
            med,
            low,
            high,
            title=f"Климат delta-change: {scenario.mode}, δ={scenario.delta:g}",
            label="диапазон до/после",
        )
        axes.plot(
            years,
            [before[y] for y in years],
            marker="o",
            color="#78909C",
            linewidth=1.4,
            linestyle="--",
            label="до",
        )
        axes.plot(
            years,
            med,
            marker="s",
            color="#0D47A1",
            linewidth=1.5,
            label="после",
        )
        axes.set_xlabel("Год", fontsize=9)
        axes.set_ylabel("Q, м³/с", fontsize=9)
        axes.legend(fontsize=8)
        self._climate_canvas.draw_idle()

    # ------------------------------------------------------------------
    # P2.5 decision support
    # ------------------------------------------------------------------
    def build_ds_request(self) -> DecisionSupportRequest:
        """Samples from last MC run (or demo ramp) + user Q_крит (10.3 (а))."""
        samples: list[float] = []
        if self._result is not None:
            raw = self._result.output_data.get("samples") or []
            samples = [float(v) for v in raw]
        if not samples:
            # analytic demo: 0..99 so P(exceed) is known for smoke
            samples = [float(i) for i in range(100)]
        q = float(self.edit_q_crit.value())
        return DecisionSupportRequest(samples=samples, thresholds={"Q_крит": q})

    def _on_ds_clicked(self) -> None:
        try:
            request = self.build_ds_request()
            result = DecisionSupportService.assess(request)
        except DecisionSupportError as exc:
            self.error.emit(str(exc))
            QMessageBox.critical(self, "Решения", str(exc))
            return
        self._ds_result = result
        item = result.assessments[0]
        self.lbl_ds.setText(
            f"P(exceed) = {item.p_exceed:.4f} ({item.n_exceed}/{item.n_samples}), "
            f"класс риска: {item.risk_class}; {result.recommendation}"
        )
        self.status_message.emit(
            f"Риск: P={item.p_exceed:.4f}, класс={item.risk_class}"
        )

    def build_sensitivity_request(self) -> SensitivityRequest:
        """Baseline = центр каждой колонки распределения; Δ — отн. из спинбокса."""
        rows = self.table.rowCount()
        if rows == 0:
            raise SensitivityError("Добавьте хотя бы один параметр")
        baseline: dict[str, float] = {}
        for row in range(rows):
            name_item = self.table.item(row, 0)
            dist_item = self.table.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            dist = (dist_item.text() if dist_item else "").strip().lower()
            if not name:
                raise SensitivityError(f"Строка {row + 1}: пустое имя параметра")
            values: list[float] = []
            for col in (2, 3, 4):
                item = self.table.item(row, col)
                if item is None or not item.text().strip():
                    continue
                try:
                    values.append(float(item.text().replace(",", ".")))
                except ValueError as exc:
                    raise SensitivityError(
                        f"Строка {row + 1}, колонка {col}: «{item.text()}» не число"
                    ) from exc
            if not values:
                raise SensitivityError(f"«{name}»: нет числовых значений")
            if dist == "uniform" and len(values) >= 2:
                baseline[name] = 0.5 * (values[0] + values[1])
            elif dist == "normal" and len(values) >= 1:
                baseline[name] = values[0]  # mean
            elif dist == "triangular" and len(values) >= 2:
                baseline[name] = values[1]  # mode
            else:
                baseline[name] = values[0]
        return SensitivityRequest(
            baseline=baseline,
            deltas={},
            relative_delta=float(self.spin_rel_delta.value()),
        )

    def _on_tornado_clicked(self) -> None:
        try:
            request = self.build_sensitivity_request()
            result = SensitivityService.analyze(self._demo_model, request)
        except SensitivityError as exc:
            self.error.emit(str(exc))
            QMessageBox.critical(self, "Чувствительность", str(exc))
            return
        self._sensitivity_result = result
        order = ", ".join(result.order)
        self.lbl_tornado_order.setText(f"Порядок: {order}")
        self._draw_tornado(result)
        self.status_message.emit(f"Tornado: {order}")

    def _draw_tornado(self, result: Any) -> None:
        self._tornado_figure.clear()
        axes = self._tornado_figure.add_subplot(111)
        names = list(result.order)
        swings = [item.swing for item in result.influences]
        draw_tornado_hbars(axes, names, swings, title="Tornado — чувствительность параметров")
        self._tornado_canvas.draw_idle()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_add_param(self) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(f"p{row + 1}"))
        self.table.setItem(row, 1, QTableWidgetItem("normal"))
        self.table.setItem(row, 2, QTableWidgetItem("0"))
        self.table.setItem(row, 3, QTableWidgetItem("1"))
        self.table.setItem(row, 4, QTableWidgetItem(""))

    def _on_del_param(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    @staticmethod
    def _demo_model(params: dict[str, float]) -> float:
        """y = a·x + b with x = 1, c unused if present (demo only)."""
        return float(params.get("a", 1.0) * 1.0 + params.get("b", 0.0))

    def _on_run_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        try:
            request = self.build_request()
        except MonteCarloError as exc:
            self.error.emit(str(exc))
            QMessageBox.critical(self, "Monte Carlo", str(exc))
            return
        self.btn_run.setEnabled(False)
        self.status_message.emit(f"Monte Carlo: {request.n_runs} прогонов…")
        self._worker = MonteCarloWorker(self._demo_model, request, parent=self)
        self._worker.finished.connect(self._on_run_finished)
        self._worker.error.connect(self._on_run_error)
        self._worker.start()

    def _on_run_finished(self, result: Any) -> None:
        self.btn_run.setEnabled(True)
        self._result = result
        summary = result.output_data["summary"]
        self.lbl_mean.setText(f"{summary['mean']:.6g}")
        self.lbl_std.setText(f"{summary['std']:.6g}")
        self.lbl_p5.setText(f"{summary['p5']:.6g}")
        self.lbl_p50.setText(f"{summary['p50']:.6g}")
        self.lbl_p95.setText(f"{summary['p95']:.6g}")
        self.lbl_min.setText(f"{summary['min']:.6g}")
        self.lbl_max.setText(f"{summary['max']:.6g}")
        self.lbl_n.setText(str(summary["count"]))
        self._draw_histogram(result.output_data["samples"], summary)
        self.status_message.emit(
            f"Monte Carlo: N={summary['count']}, p50={summary['p50']:.4g}"
        )
        self.run_finished.emit(result)

    def _on_run_error(self, message: str) -> None:
        self.btn_run.setEnabled(True)
        self.error.emit(message)
        QMessageBox.critical(self, "Monte Carlo", message)

    def _draw_histogram(self, samples: list[float], summary: dict) -> None:
        self._figure.clear()
        axes = self._figure.add_subplot(111)
        draw_histogram_quantiles(axes, samples, summary, title="Выход y — Monte Carlo")
        self._canvas.draw_idle()
