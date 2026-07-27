"""
gui/widget_work5.py
Работа 5 — Ледовые явления (PyQt6)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QLineEdit, QTableWidget, QTableWidgetItem, QComboBox
)
from PyQt6.QtGui import QFont

from gui.plot_style import auto_resize_table

from core.hydrorash.ice_phenomena import (
    compute_ice_cover_stats, estimate_max_ice_thickness,
    ice_jam_rise, ice_jam_flood_level, ice_cover_duration,
    freeze_up_date_analysis, ice_breakup_date_analysis,
    get_ice_parameters_by_zone, estimate_ice_thickness_by_formula,
    ClimateZone
)

_ZONE_PARAM_LABELS = {
    "zone": "Зона",
    "max_thickness_range_m": "Макс. толщина, м",
    "freeze_period_days": "Период ледостава, сут",
    "ice_duration_days": "Длительность льда, сут",
    "typical_rise_m": "Типичный подъём, м",
    "freeze_up_doy_range": "Ледостав (день года)",
    "breakup_doy_range": "Распад льда (день года)",
    "zone_coefficient": "Зональный коэффициент",
    "snow_correction": "Снеговая поправка",
    "description": "Описание",
    "normative": "Норматив",
}


class Work5Widget(QWidget):
    """Вкладка «Работа 5: Ледовые явления»."""

    def __init__(self):
        super().__init__()
        self.freeze_dates = None
        self.breakup_dates = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("ЛЕДОВЫЕ ЯВЛЕНИЯ")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1565C0;")
        layout.addWidget(title)

        zone_group = QGroupBox("Климатическая зона и параметры")
        zone_form = QFormLayout(zone_group)

        self.combo_zone = QComboBox()
        self.combo_zone.addItems([
            "умеренная", "субарктическая", "арктическая",
            "холодная влажная", "сухая", "полузасушливая"
        ])
        zone_form.addRow("Климатическая зона:", self.combo_zone)

        self.edit_width = QLineEdit("50")
        zone_form.addRow("Ширина русла, м:", self.edit_width)

        self.edit_depth = QLineEdit("3")
        zone_form.addRow("Средняя глубина, м:", self.edit_depth)

        self.edit_velocity = QLineEdit("1.0")
        zone_form.addRow("Скорость течения, м/с:", self.edit_velocity)

        self.edit_winter_temp = QLineEdit("-15")
        zone_form.addRow("Средняя температура января, °C:", self.edit_winter_temp)

        layout.addWidget(zone_group)

        btn_row = QHBoxLayout()
        self.btn_zone_params = QPushButton("Параметры по зоне")
        self.btn_zone_params.clicked.connect(self.show_zone_params)
        btn_row.addWidget(self.btn_zone_params)

        self.btn_thickness = QPushButton("Рассчитать толщину льда")
        self.btn_thickness.clicked.connect(self.calc_ice_thickness)
        btn_row.addWidget(self.btn_thickness)

        self.btn_jam = QPushButton("Заторный паводок")
        self.btn_jam.clicked.connect(self.calc_ice_jam)
        btn_row.addWidget(self.btn_jam)

        self.btn_load_dates = QPushButton("Загрузить даты ледостава")
        self.btn_load_dates.clicked.connect(self.load_dates)
        btn_row.addWidget(self.btn_load_dates)

        layout.addLayout(btn_row)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setFont(QFont("Consolas", 10))
        layout.addWidget(self.result_box)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        auto_resize_table(self.table)
        layout.addWidget(self.table)

    def show_zone_params(self):
        try:
            zone_map = {
                "умеренная": ClimateZone.MODERATE,
                "субарктическая": ClimateZone.SUBARCTIC,
                "арктическая": ClimateZone.ARCTIC,
                "холодная влажная": ClimateZone.COLD_HUMID,
                "сухая": ClimateZone.DRY,
                "полузасушливая": ClimateZone.SEMI_ARID
            }
            zone = zone_map[self.combo_zone.currentText()]
            params = get_ice_parameters_by_zone(zone)

            self.result_box.clear()
            self.result_box.append(f"Параметры для зоны: {zone.value}")
            for k, v in params.items():
                label = _ZONE_PARAM_LABELS.get(k, k)
                self.result_box.append(f"  {label}: {v}")

            self.table.setRowCount(len(params))
            for i, (k, v) in enumerate(params.items()):
                label = _ZONE_PARAM_LABELS.get(k, k)
                self.table.setItem(i, 0, QTableWidgetItem(str(label)))
                self.table.setItem(i, 1, QTableWidgetItem(str(v)))

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def calc_ice_thickness(self):
        try:
            T_jan = float(self.edit_winter_temp.text())
            width = float(self.edit_width.text())
            depth = float(self.edit_depth.text())
            velocity = float(self.edit_velocity.text())

            zone_map = {
                "умеренная": ClimateZone.MODERATE,
                "субарктическая": ClimateZone.SUBARCTIC,
                "арктическая": ClimateZone.ARCTIC,
                "холодная влажная": ClimateZone.COLD_HUMID,
                "сухая": ClimateZone.DRY,
                "полузасушливая": ClimateZone.SEMI_ARID
            }
            zone = zone_map[self.combo_zone.currentText()]

            thickness = estimate_max_ice_thickness(
                latitude=60.0,
                mean_jan_temp=T_jan,
                zone=zone
            )

            formula_thick = estimate_ice_thickness_by_formula(
                mean_winter_temp=abs(T_jan),
                water_depth=depth,
                flow_velocity=velocity
            )

            self.result_box.clear()
            self.result_box.append("=== ТОЛЩИНА ЛЬДА ===")
            self.result_box.append(f"Методический диапазон: {thickness.get('thickness_range_m', 'Н/Д')}")
            self.result_box.append(f"Взвешенная оценка: {thickness.get('thickness_m', 'Н/Д')} м")
            self.result_box.append(f"По формуле Кондратьева: {formula_thick:.3f} м")
            self.result_box.append(f"Формула: {thickness.get('formula_used', 'Н/Д')}")
            self.result_box.append(f"Ширина русла: {width} м")
            self.result_box.append(f"Скорость: {velocity} м/с")

            self.table.setRowCount(5)
            items = [
                ("Взвешенная оценка", f"{thickness.get('thickness_m', 'Н/Д')} м"),
                ("Формула Кондратьева", f"{formula_thick:.3f} м"),
                ("Формула РД 52-26-2008", thickness.get("formula_used", "Н/Д")),
                ("Ширина русла", f"{width} м"),
                ("Скорость течения", f"{velocity} м/с")
            ]
            for i, (k, v) in enumerate(items):
                self.table.setItem(i, 0, QTableWidgetItem(k))
                self.table.setItem(i, 1, QTableWidgetItem(v))

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def calc_ice_jam(self):
        try:
            width = float(self.edit_width.text())
            velocity = float(self.edit_velocity.text())
            T_jan = float(self.edit_winter_temp.text())

            zone_map = {
                "умеренная": ClimateZone.MODERATE,
                "субарктическая": ClimateZone.SUBARCTIC,
                "арктическая": ClimateZone.ARCTIC,
                "холодная влажная": ClimateZone.COLD_HUMID,
                "сухая": ClimateZone.DRY,
                "полузасушливая": ClimateZone.SEMI_ARID
            }
            zone = zone_map[self.combo_zone.currentText()]

            thick_result = estimate_max_ice_thickness(
                latitude=60.0,
                mean_jan_temp=T_jan,
                zone=zone
            )
            ice_thickness = thick_result.get('thickness_m', 0.5)

            rise = ice_jam_rise(width, ice_thickness, velocity)

            self.result_box.clear()
            self.result_box.append("=== ЗАТОРНЫЙ ПАВОДК ===")
            self.result_box.append(f"Толщина льда: {ice_thickness:.3f} м")
            self.result_box.append(f"Повышение уровня: {rise.get('rise_m', 'Н/Д')} м")
            self.result_box.append(f"Вероятность затора: {rise.get('jam_probability', 'Н/Д')}")
            self.result_box.append(f"Опасность: {rise.get('severity', 'Н/Д')}")
            self.result_box.append(f"Формула: {rise.get('formula_used', 'Н/Д')}")

            flood = ice_jam_flood_level(
                H_normal=0.0,
                channel_width=width,
                ice_thickness=ice_thickness,
                flow_velocity=velocity
            )
            self.result_box.append(f"\nРасчётный уровень при заторе: {flood.get('H_ice_m', 'Н/Д')} м")
            self.result_box.append(f"Коэффициент k_P: {flood.get('k_P', 'Н/Д')}")

            self.table.setRowCount(5)
            items = [
                ("Толщина льда", f"{ice_thickness:.3f} м"),
                ("Повышение уровня", f"{rise.get('rise_m', 'Н/Д')} м"),
                ("Вероятность затора", str(rise.get('jam_probability', 'Н/Д'))),
                ("Опасность", str(rise.get('severity', 'Н/Д'))),
                ("Расчётный уровень H_ice", f"{flood.get('H_ice_m', 'Н/Д')} м")
            ]
            for i, (k, v) in enumerate(items):
                self.table.setItem(i, 0, QTableWidgetItem(k))
                self.table.setItem(i, 1, QTableWidgetItem(v))

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def load_dates(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить даты ледостава", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            df = pd.read_excel(path)
            freeze_col = [c for c in df.columns if 'ледостав' in str(c).lower() or 'freeze' in str(c).lower()]
            breakup_col = [c for c in df.columns if 'распад' in str(c).lower() or 'breakup' in str(c).lower()]
            if freeze_col:
                self.freeze_dates = pd.to_datetime(df[freeze_col[0]], errors='coerce').dropna()
                self.result_box.append(f"Загружены даты ледостава: {len(self.freeze_dates)}")
            if breakup_col:
                self.breakup_dates = pd.to_datetime(df[breakup_col[0]], errors='coerce').dropna()
                self.result_box.append(f"Загружены даты вскрытия: {len(self.breakup_dates)}")
            if not freeze_col and not breakup_col:
                self.result_box.append(f"Столбцы: {list(df.columns)}")
                self.result_box.append("Не найдены столбцы с датами ледостава/вскрытия")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def set_data(self, freeze_dates=None, breakup_dates=None):
        if freeze_dates is not None:
            self.freeze_dates = freeze_dates
        if breakup_dates is not None:
            self.breakup_dates = breakup_dates
