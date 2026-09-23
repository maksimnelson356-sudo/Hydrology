"""
gui/tabs/tab_geo.py
Вкладка «Морфометрия» (P1.6, решение 9.3 = (б)): импорт контура бассейна
из GeoJSON, сводка (площадь / периметр / центроид) и превью matplotlib.

Сервис считает метрики; вкладка только читает файл и рисует результат.
Без QtGIS и без новых runtime-зависимостей.
"""

from __future__ import annotations

import json
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.services.geo_service import BasinMorphometry, GeoService, GeoServiceError

HINT_STYLE = (
    "color: #666; font-style: italic; padding: 8px; background: #f0f0f0; border-radius: 4px;"
)
TITLE_STYLE = "font-size: 15px; font-weight: bold; color: #0D47A1;"
LOAD_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; font-weight: bold; "
    "padding: 10px; font-size: 13px; border-radius: 6px; }"
    "QPushButton:hover { background-color: #0D47A1; }"
)
GEOJSON_FILTER = "GeoJSON (*.geojson *.json);;Все файлы (*)"


class TabGeo(QWidget):
    """Раздел «Морфометрия»: загрузка GeoJSON-контура и сводка бассейна."""

    status_message = pyqtSignal(str)
    error = pyqtSignal(str)
    contour_loaded = pyqtSignal(object)  # BasinMorphometry

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = GeoService()
        self._summary: BasinMorphometry | None = None
        self._rings: list[list[tuple[float, float]]] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------
    @property
    def summary(self) -> BasinMorphometry | None:
        """Last successfully loaded morphometry (or None)."""
        return self._summary

    @property
    def service(self) -> GeoService:
        """GeoService used by this tab."""
        return self._service

    @property
    def rings(self) -> list[list[tuple[float, float]]]:
        """Outer rings of the last loaded contour (for preview / tests)."""
        return [list(ring) for ring in self._rings]

    def load_contour_path(self, path: str | Path) -> BasinMorphometry:
        """Load a contour file programmatically (also used by tests/smoke)."""
        summary = self._service.load(path)
        self._apply_summary(summary, str(path))
        return summary

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Морфометрия бассейна — контур GeoJSON")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        hint = QLabel(
            "Загрузите контур бассейна (Feature / FeatureCollection / Polygon). "
            "Расчёт площади и периметра — без новых зависимостей (решение 9.3 = (б))."
        )
        hint.setStyleSheet(HINT_STYLE)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        toolbar = QHBoxLayout()
        self.btn_load = QPushButton("📂 Загрузить контур GeoJSON…")
        self.btn_load.setStyleSheet(LOAD_STYLE)
        self.btn_load.clicked.connect(self._on_load_clicked)
        toolbar.addWidget(self.btn_load)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Summary block
        summary_box = QGroupBox("Сводка")
        form = QFormLayout(summary_box)
        self.lbl_name = QLabel("—")
        self.lbl_area = QLabel("—")
        self.lbl_perimeter = QLabel("—")
        self.lbl_centroid = QLabel("—")
        self.lbl_vertices = QLabel("—")
        self.lbl_geometry = QLabel("—")
        self.lbl_path = QLabel("—")
        self.lbl_path.setWordWrap(True)
        form.addRow("Название:", self.lbl_name)
        form.addRow("Площадь:", self.lbl_area)
        form.addRow("Периметр:", self.lbl_perimeter)
        form.addRow("Центроид (x, y):", self.lbl_centroid)
        form.addRow("Вершин:", self.lbl_vertices)
        form.addRow("Геометрия:", self.lbl_geometry)
        form.addRow("Файл:", self.lbl_path)
        layout.addWidget(summary_box)

        # Detail table (key → value, mirrors to_metadata)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(140)
        layout.addWidget(self.table)

        # Contour preview
        preview_box = QGroupBox("Превью контура")
        preview_layout = QVBoxLayout(preview_box)
        self._figure = Figure(figsize=(5, 3), tight_layout=True)
        self._canvas = FigureCanvas(self._figure)
        preview_layout.addWidget(self._canvas)
        layout.addWidget(preview_box, stretch=1)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_load_clicked(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить контур бассейна", "", GEOJSON_FILTER
        )
        if not path:
            return
        try:
            self.load_contour_path(path)
        except GeoServiceError as error:
            self.error.emit(str(error))
            QMessageBox.critical(self, "Морфометрия", str(error))

    def _apply_summary(self, summary: BasinMorphometry, path: str) -> None:
        self._summary = summary
        self._rings = self._read_rings(path)
        self.lbl_name.setText(summary.name)
        self.lbl_area.setText(
            f"{summary.area_km2:.4f} км²  ({summary.area_m2:,.0f} м²)"
        )
        self.lbl_perimeter.setText(
            f"{summary.perimeter_km:.4f} км  ({summary.perimeter_m:,.0f} м)"
        )
        self.lbl_centroid.setText(
            f"({summary.centroid_lon:.6f}, {summary.centroid_lat:.6f})"
        )
        self.lbl_vertices.setText(str(summary.vertex_count))
        self.lbl_geometry.setText(summary.geometry_type)
        self.lbl_path.setText(path)

        meta = summary.to_metadata()
        self.table.setRowCount(0)
        for key, value in meta.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.table.setItem(row, 1, QTableWidgetItem(str(value)))

        self._draw_preview()
        self.status_message.emit(
            f"Контур «{summary.name}»: площадь {summary.area_km2:.3f} км²"
        )
        self.contour_loaded.emit(summary)

    @staticmethod
    def _read_rings(path: str) -> list[list[tuple[float, float]]]:
        """Read outer rings from the GeoJSON file for preview drawing."""
        try:
            raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return []
        return TabGeo._collect_rings(raw)

    def _draw_preview(self) -> None:
        """Plot the outer rings loaded with the last contour."""
        self._figure.clear()
        axes = self._figure.add_subplot(111)
        name = self._summary.name if self._summary else ""
        axes.set_title(name, fontsize=10)
        axes.set_aspect("equal", adjustable="datalim")

        for ring in self._rings:
            if not ring:
                continue
            xs = [p[0] for p in ring]
            ys = [p[1] for p in ring]
            axes.plot(xs, ys, color="#1565C0", linewidth=1.5)
            axes.fill(xs, ys, color="#1565C0", alpha=0.15)
        axes.grid(True, linestyle=":", alpha=0.5)
        axes.set_xlabel("X / lon", fontsize=9)
        axes.set_ylabel("Y / lat", fontsize=9)
        self._canvas.draw_idle()

    @staticmethod
    def _collect_rings(document: object) -> list[list[tuple[float, float]]]:
        rings: list[list[tuple[float, float]]] = []
        if not isinstance(document, dict):
            return rings
        gtype = document.get("type")
        if gtype == "Polygon":
            coords = document.get("coordinates") or []
            if coords:
                rings.append([(float(p[0]), float(p[1])) for p in coords[0] if len(p) >= 2])
        elif gtype == "MultiPolygon":
            for poly in document.get("coordinates") or []:
                if poly:
                    rings.append(
                        [(float(p[0]), float(p[1])) for p in poly[0] if len(p) >= 2]
                    )
        elif gtype == "Feature":
            rings.extend(TabGeo._collect_rings(document.get("geometry")))
        elif gtype == "FeatureCollection":
            for feature in document.get("features") or []:
                rings.extend(TabGeo._collect_rings(feature))
        return rings
