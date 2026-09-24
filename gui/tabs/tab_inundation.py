"""Native PyQt tab for HydroSphere P3.3 inundation estimates."""

from __future__ import annotations

from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.hydrorash.inundation import InundationCalculationError, StageAreaPoint
from core.services.inundation_service import (
    GeoJsonSource,
    InundationError,
    InundationRequest,
    InundationResult,
    InundationService,
    StageAreaSource,
    TrapezoidSource,
)


class InundationTab(QWidget):
    """Level-to-area/volume calculator backed by ``InundationService``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._update_source_visibility()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Затопление: уровень → площадь и объём")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #0D47A1;")
        layout.addWidget(title)

        hint = QLabel("Источник 11.2=(a): таблица/кривая S(H); дополнительно поддерживается аналитический профиль и GeoJSON-контуры с отметками. DEM не используется.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #546E7A; font-size: 11px;")
        layout.addWidget(hint)

        parameters = QGroupBox("Параметры расчёта")
        form = QFormLayout(parameters)
        self.inundation_source = QComboBox()
        self.inundation_source.addItem("Кривая S(H)", "stage_area")
        self.inundation_source.addItem("Трапецеидальный профиль", "trapezoid")
        self.inundation_source.addItem("GeoJSON-контуры", "geojson")
        self.inundation_source.currentIndexChanged.connect(self._update_source_visibility)
        form.addRow("Источник S(H):", self.inundation_source)

        self.inundation_stage = QDoubleSpinBox()
        self.inundation_stage.setRange(0.0, 1000.0)
        self.inundation_stage.setDecimals(2)
        self.inundation_stage.setSingleStep(0.1)
        self.inundation_stage.setValue(1.5)
        self.inundation_stage.setSuffix(" м")
        form.addRow("Уровень H:", self.inundation_stage)
        layout.addWidget(parameters)

        self.stage_area_group = QGroupBox("Кривая площади затопления")
        stage_area_layout = QVBoxLayout(self.stage_area_group)
        self.stage_area_table = QTableWidget(0, 2)
        self.stage_area_table.setHorizontalHeaderLabels(["Уровень H, м", "Площадь S, м²"])
        self.stage_area_table.horizontalHeader().setStretchLastSection(True)
        self.stage_area_table.setMaximumHeight(170)
        self._fill_default_curve()
        stage_area_layout.addWidget(self.stage_area_table)

        curve_buttons = QHBoxLayout()
        add_button = QPushButton("Добавить точку")
        add_button.clicked.connect(self._add_curve_point)
        remove_button = QPushButton("Удалить последнюю")
        remove_button.clicked.connect(self._remove_curve_point)
        curve_buttons.addWidget(add_button)
        curve_buttons.addWidget(remove_button)
        curve_buttons.addStretch()
        stage_area_layout.addLayout(curve_buttons)
        layout.addWidget(self.stage_area_group)

        self.trapezoid_group = QGroupBox("Трапецеидальный профиль")
        trapezoid_form = QFormLayout(self.trapezoid_group)
        self.inundation_bottom_width = QDoubleSpinBox()
        self.inundation_bottom_width.setRange(0.01, 10000.0)
        self.inundation_bottom_width.setDecimals(2)
        self.inundation_bottom_width.setValue(20.0)
        self.inundation_bottom_width.setSuffix(" м")
        trapezoid_form.addRow("Ширина дна B:", self.inundation_bottom_width)
        self.inundation_side_slope = QDoubleSpinBox()
        self.inundation_side_slope.setRange(0.0, 100.0)
        self.inundation_side_slope.setDecimals(2)
        self.inundation_side_slope.setValue(2.0)
        self.inundation_side_slope.setSuffix(" —")
        trapezoid_form.addRow("Откос бортов m:", self.inundation_side_slope)
        layout.addWidget(self.trapezoid_group)

        self.geojson_group = QGroupBox("GeoJSON-контуры")
        geojson_layout = QVBoxLayout(self.geojson_group)
        geojson_row = QHBoxLayout()
        self.geojson_path = QLineEdit()
        self.geojson_path.setReadOnly(True)
        self.geojson_path.setPlaceholderText("GeoJSON FeatureCollection с properties.elevation")
        load_button = QPushButton("Загрузить GeoJSON")
        load_button.clicked.connect(self._load_geojson)
        geojson_row.addWidget(self.geojson_path)
        geojson_row.addWidget(load_button)
        geojson_layout.addLayout(geojson_row)
        layout.addWidget(self.geojson_group)

        calculate_button = QPushButton("Рассчитать затопление")
        calculate_button.setStyleSheet(
            "QPushButton { background: #00695C; color: white; font-weight: bold; }"
        )
        calculate_button.clicked.connect(self.calculate_inundation)
        layout.addWidget(calculate_button)

        self.inundation_figure = Figure(figsize=(10, 4), tight_layout=True)
        self.inundation_canvas = FigureCanvas(self.inundation_figure)
        self.inundation_result = QTextEdit()
        self.inundation_result.setReadOnly(True)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.inundation_canvas)
        splitter.addWidget(self.inundation_result)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 150])
        layout.addWidget(splitter, stretch=1)

    def calculate_inundation(self) -> None:
        """Evaluate the selected source and refresh result text plus S(H) plot."""
        try:
            request = InundationRequest(
                stage_m=self.inundation_stage.value(),
                source=self._source_from_controls(),
            )
            result = InundationService.run(request)
        except (InundationError, InundationCalculationError, OSError, UnicodeError) as error:
            self._show_error(str(error))
            return
        self._show_result(result)

    def _source_from_controls(self) -> StageAreaSource | TrapezoidSource | GeoJsonSource:
        source_key = str(self.inundation_source.currentData())
        match source_key:  # noqa: MATCH_OK
            case "stage_area":
                return StageAreaSource(points=self._stage_area_points())
            case "trapezoid":
                return TrapezoidSource(
                    bottom_width_m=self.inundation_bottom_width.value(),
                    side_slope=self.inundation_side_slope.value(),
                )
            case "geojson":
                path = self.geojson_path.text().strip()
                if not path:
                    raise InundationError("Выберите GeoJSON-файл с контурами")
                return GeoJsonSource(
                    geojson_text=Path(path).read_text(encoding="utf-8-sig")
                )
            case unreachable:
                raise InundationError(f"Неизвестный источник: {unreachable}")

    def _stage_area_points(self) -> tuple[StageAreaPoint, ...]:
        if self.stage_area_table.rowCount() == 0:
            raise InundationError("Кривая S(H) не содержит точек")
        points: list[StageAreaPoint] = []
        for row in range(self.stage_area_table.rowCount()):
            try:
                stage = float(self._cell_text(row, 0))
                area = float(self._cell_text(row, 1))
            except ValueError as error:
                raise InundationError(f"Некорректное значение в строке {row + 1}") from error
            points.append(StageAreaPoint(stage_m=stage, area_m2=area))
        return tuple(points)

    def _show_result(self, result: InundationResult) -> None:
        self.inundation_result.clear()
        self.inundation_result.append(
            f"Уровень: запрошен {result.requested_stage_m:.3f} м, "
            f"расчётный {result.effective_stage_m:.3f} м"
        )
        self.inundation_result.append(
            f"Площадь: {result.area_m2:,.0f} м² ({result.area_km2:.6f} км²)"
        )
        self.inundation_result.append(
            f"Объём: {result.volume_m3:,.0f} м³ "
            f"({result.volume_mln_m3:.3f} млн м³; {result.volume_km3:.6f} км³)"
        )
        for warning in result.warnings:
            self.inundation_result.append(f"Предупреждение: {warning}")
        self.inundation_result.append(f"Источник: {result.provenance}")

        stages, areas_m2 = ([point.stage_m for point in result.curve], [point.area_m2 for point in result.curve])
        plotted_areas = [area / 1_000_000.0 for area in areas_m2] if (use_km2 := max(areas_m2) >= 1_000_000.0) else areas_m2
        self.inundation_figure.clear()
        axes = self.inundation_figure.add_subplot(111)
        axes.plot(stages, plotted_areas, color="#00695C", linewidth=2, label="S(H)")
        axes.fill_between(stages, plotted_areas, color="#26A69A", alpha=0.2)
        axes.axvline(
            result.effective_stage_m,
            color="#F44336",
            linestyle=":",
            label=f"H = {result.effective_stage_m:.2f} м",
        )
        axes.set_xlabel("Уровень H, м")
        axes.set_ylabel("Площадь затопления, " + ("км²" if use_km2 else "м²"))
        axes.set_title("Кривая затопления S(H)")
        axes.grid(True, alpha=0.5)
        axes.legend()
        self.inundation_canvas.draw()

    def _show_error(self, message: str) -> None:
        self.inundation_figure.clear()
        self.inundation_canvas.draw()
        self.inundation_result.clear()
        self.inundation_result.append(f"Ошибка: {message}")

    def _update_source_visibility(self, _index: int = -1) -> None:
        source_key = str(self.inundation_source.currentData())
        self.stage_area_group.setVisible(source_key == "stage_area")
        self.trapezoid_group.setVisible(source_key == "trapezoid")
        self.geojson_group.setVisible(source_key == "geojson")
        if hasattr(self, "inundation_figure"):
            self.inundation_figure.clear()
            self.inundation_canvas.draw()
            self.inundation_result.clear()

    def _load_geojson(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Загрузить GeoJSON-контуры",
            "",
            "GeoJSON (*.geojson *.json)",
        )
        if path:
            self.geojson_path.setText(path)

    def _fill_default_curve(self) -> None:
        defaults = ((0.0, 0.0), (1.0, 5_000.0), (2.0, 15_000.0), (3.0, 30_000.0))
        self.stage_area_table.setSortingEnabled(False)
        self.stage_area_table.setRowCount(len(defaults))
        for row, values in enumerate(defaults):
            self._set_row(row, *values)
        self.stage_area_table.setSortingEnabled(True)

    def _add_curve_point(self) -> None:
        self.stage_area_table.setSortingEnabled(False)
        row = self.stage_area_table.rowCount()
        self.stage_area_table.insertRow(row)
        self._set_row(row, float(row), 0.0)
        self.stage_area_table.setSortingEnabled(True)

    def _remove_curve_point(self) -> None:
        row = self.stage_area_table.rowCount() - 1
        if row >= 0:
            self.stage_area_table.removeRow(row)

    def _set_row(self, row: int, stage: float, area: float) -> None:
        self.stage_area_table.setItem(row, 0, QTableWidgetItem(f"{stage:.3f}"))
        self.stage_area_table.setItem(row, 1, QTableWidgetItem(f"{area:.3f}"))

    def _cell_text(self, row: int, column: int) -> str:
        item = self.stage_area_table.item(row, column)
        return item.text().strip() if item is not None else ""
