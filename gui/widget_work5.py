"""
gui/widget_work5.py
Работа 5 — Ледовые явления (PyQt6)
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.hydrorash.ice_phenomena import (
    ClimateZone,
    estimate_ice_thickness_by_formula,
    estimate_max_ice_thickness,
    get_ice_parameters_by_zone,
    ice_jam_flood_level,
    ice_jam_rise,
)
from gui.plot_style import auto_resize_table
from i18n import tr

_ZONE_PARAM_LABELS = {
    "zone": tr("zone", "Зона"),
    "max_thickness_range_m": tr("max_thickness_range_m", "Макс. толщина, м"),
    "freeze_period_days": tr("freeze_period_days", "Период ледостава, сут"),
    "ice_duration_days": tr("ice_duration_days", "Длительность льда, сут"),
    "typical_rise_m": tr("typical_rise_m", "Типичный подъём, м"),
    "freeze_up_doy_range": tr("freeze_up_doy_range", "Ледостав (день года)"),
    "breakup_doy_range": tr("breakup_doy_range", "Распад льда (день года)"),
    "zone_coefficient": tr("zone_coefficient", "Зональный коэффициент"),
    "snow_correction": tr("snow_correction", "Снеговая поправка"),
    "description": tr("description", "Описание"),
    "normative": tr("normative", "Норматив"),
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

        title = QLabel(tr("title_work5", "ЛЕДОВЫЕ ЯВЛЕНИЯ"))
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1565C0;")
        layout.addWidget(title)

        zone_group = QGroupBox(tr("group_zone", "Климатическая зона и параметры"))
        zone_form = QFormLayout(zone_group)

        self.combo_zone = QComboBox()
        self.combo_zone.addItems([
            tr("zone_moderate", "умеренная"),
            tr("zone_subarctic", "субарктическая"),
            tr("zone_arctic", "арктическая"),
            tr("zone_cold_humid", "холодная влажная"),
            tr("zone_dry", "сухая"),
            tr("zone_semi_arid", "полузасушливая")
        ])
        zone_form.addRow(tr("label_zone", "Климатическая зона:"), self.combo_zone)

        self.edit_width = QLineEdit("50")
        zone_form.addRow(tr("label_width", "Ширина русла, м:"), self.edit_width)

        self.edit_depth = QLineEdit("3")
        zone_form.addRow(tr("label_depth", "Средняя глубина, м:"), self.edit_depth)

        self.edit_velocity = QLineEdit("1.0")
        zone_form.addRow(tr("label_velocity", "Скорость течения, м/с:"), self.edit_velocity)

        self.edit_winter_temp = QLineEdit("-15")
        zone_form.addRow(tr("label_winter_temp", "Средняя температура января, °C:"), self.edit_winter_temp)

        self.edit_latitude = QLineEdit("60.0")
        zone_form.addRow(tr("label_latitude", "Широта, °N:"), self.edit_latitude)

        layout.addWidget(zone_group)

        btn_row = QHBoxLayout()
        self.btn_zone_params = QPushButton(tr("btn_zone_params", "Параметры по зоне"))
        self.btn_zone_params.clicked.connect(self.show_zone_params)
        btn_row.addWidget(self.btn_zone_params)

        self.btn_thickness = QPushButton(tr("btn_thickness", "Рассчитать толщину льда"))
        self.btn_thickness.clicked.connect(self.calc_ice_thickness)
        btn_row.addWidget(self.btn_thickness)

        self.btn_jam = QPushButton(tr("btn_jam", "Заторный паводок"))
        self.btn_jam.clicked.connect(self.calc_ice_jam)
        btn_row.addWidget(self.btn_jam)

        self.btn_load_dates = QPushButton(tr("btn_load_dates", "Загрузить даты ледостава"))
        self.btn_load_dates.clicked.connect(self.load_dates)
        btn_row.addWidget(self.btn_load_dates)

        layout.addLayout(btn_row)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setFont(QFont("Consolas", 10))

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels([tr("col_param", "Параметр"), tr("col_value", "Значение")])
        auto_resize_table(self.table)

        results_splitter = QSplitter(Qt.Orientation.Vertical)
        results_splitter.addWidget(self.result_box)
        results_splitter.addWidget(self.table)
        results_splitter.setStretchFactor(0, 2)
        results_splitter.setStretchFactor(1, 1)
        results_splitter.setSizes([220, 140])
        layout.addWidget(results_splitter)

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
            self.result_box.append(tr("msg_zone_params", "Параметры для зоны: {zone}").format(zone=zone.value))
            for k, v in params.items():
                label = _ZONE_PARAM_LABELS.get(k, k)
                self.result_box.append(f"  {label}: {v}")

            self.table.setRowCount(len(params))
            for i, (k, v) in enumerate(params.items()):
                label = _ZONE_PARAM_LABELS.get(k, k)
                self.table.setItem(i, 0, QTableWidgetItem(str(label)))
                self.table.setItem(i, 1, QTableWidgetItem(str(v)))

        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))

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

            latitude = float(self.edit_latitude.text()) if hasattr(self, 'edit_latitude') else 60.0
            thickness = estimate_max_ice_thickness(
                latitude=latitude,
                mean_jan_temp=T_jan,
                zone=zone
            )

            formula_thick = estimate_ice_thickness_by_formula(
                mean_winter_temp=abs(T_jan),
                water_depth=depth,
                flow_velocity=velocity
            )

            self.result_box.clear()
            self.result_box.append(tr("title_ice_thickness", "ТОЛЩИНА ЛЬДА"))
            self.result_box.append(tr("msg_thickness_range", "Методический диапазон: {range}").format(range=thickness.get('thickness_range_m', 'Н/Д')))
            self.result_box.append(tr("msg_weighted_estimate", "Взвешенная оценка: {val} м").format(val=thickness.get('thickness_m', 'Н/Д')))
            self.result_box.append(tr("msg_kondratiev", "По формуле Кондратьева: {val} м").format(val=formula_thick))
            self.result_box.append(tr("msg_formula_used", "Формула: {formula}").format(formula=thickness.get('formula_used', 'Н/Д')))
            self.result_box.append(tr("msg_width", "Ширина русла: {val} м").format(val=width))
            self.result_box.append(tr("msg_velocity", "Скорость: {val} м/с").format(val=velocity))

            self.table.setRowCount(5)
            items = [
                (tr("item_weighted", "Взвешенная оценка"), f"{thickness.get('thickness_m', 'Н/Д')} м"),
                (tr("item_kondratiev", "Формула Кондратьева"), f"{formula_thick:.3f} м"),
                (tr("item_rd", "Формула РД 52-26-2008"), thickness.get("formula_used", "Н/Д")),
                (tr("label_width", "Ширина русла"), f"{width} м"),
                (tr("label_velocity", "Скорость течения"), f"{velocity} м/с")
            ]
            for i, (k, v) in enumerate(items):
                self.table.setItem(i, 0, QTableWidgetItem(k))
                self.table.setItem(i, 1, QTableWidgetItem(v))

        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))

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
                latitude=float(self.edit_latitude.text()) if hasattr(self, 'edit_latitude') else 60.0,
                mean_jan_temp=T_jan,
                zone=zone
            )
            ice_thickness = thick_result.get('thickness_m', 0.5)

            rise = ice_jam_rise(width, ice_thickness, velocity)

            self.result_box.clear()
            self.result_box.append(tr("title_ice_jam", "ЗАТОРНЫЙ ПАВОДОК"))
            self.result_box.append(tr("msg_ice_thickness", "Толщина льда: {val} м").format(val=ice_thickness))
            self.result_box.append(tr("msg_rise", "Повышение уровня: {val} м").format(val=rise.get('rise_m', 'Н/Д')))
            self.result_box.append(tr("msg_jam_prob", "Вероятность затора: {val}").format(val=rise.get('jam_probability', 'Н/Д')))
            self.result_box.append(tr("msg_severity", "Опасность: {val}").format(val=rise.get('severity', 'Н/Д')))
            self.result_box.append(tr("msg_formula", "Формула: {formula}").format(formula=rise.get('formula_used', 'Н/Д')))

            flood = ice_jam_flood_level(
                H_normal=0.0,
                channel_width=width,
                ice_thickness=ice_thickness,
                flow_velocity=velocity
            )
            self.result_box.append(tr("msg_flood_level", "Расчётный уровень при заторе: {val} м").format(val=flood.get('H_ice_m', 'Н/Д')))
            self.result_box.append(tr("msg_kp", "Коэффициент k_P: {val}").format(val=flood.get('k_P', 'Н/Д')))

            self.table.setRowCount(5)
            items = [
                (tr("item_ice_thickness", "Толщина льда"), f"{ice_thickness:.3f} м"),
                (tr("item_rise", "Повышение уровня"), f"{rise.get('rise_m', 'Н/Д')} м"),
                (tr("item_jam_prob", "Вероятность затора"), str(rise.get('jam_probability', 'Н/Д'))),
                (tr("item_severity", "Опасность"), str(rise.get('severity', 'Н/Д'))),
                (tr("item_H_ice", "Расчётный уровень H_ice"), f"{flood.get('H_ice_m', 'Н/Д')} м")
            ]
            for i, (k, v) in enumerate(items):
                self.table.setItem(i, 0, QTableWidgetItem(k))
                self.table.setItem(i, 1, QTableWidgetItem(v))

        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))

    def load_dates(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("dialog_load_dates", "Загрузить даты ледостава"), "", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            df = pd.read_excel(path)
            freeze_col = [c for c in df.columns if 'ледостав' in str(c).lower() or 'freeze' in str(c).lower()]
            breakup_col = [c for c in df.columns if 'распад' in str(c).lower() or 'breakup' in str(c).lower()]
            if freeze_col:
                self.freeze_dates = pd.to_datetime(df[freeze_col[0]], errors='coerce').dropna()
                self.result_box.append(tr("msg_freeze_loaded", "Загружены даты ледостава: {count}").format(count=len(self.freeze_dates)))
            if breakup_col:
                self.breakup_dates = pd.to_datetime(df[breakup_col[0]], errors='coerce').dropna()
                self.result_box.append(tr("msg_breakup_loaded", "Загружены даты вскрытия: {count}").format(count=len(self.breakup_dates)))
            if not freeze_col and not breakup_col:
                self.result_box.append(f"Столбцы: {list(df.columns)}")
                self.result_box.append(tr("msg_no_date_cols", "Не найдены столбцы с датами ледостава/вскрытия"))
        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))

    def set_data(self, freeze_dates=None, breakup_dates=None):
        if freeze_dates is not None:
            self.freeze_dates = freeze_dates
        if breakup_dates is not None:
            self.breakup_dates = breakup_dates
