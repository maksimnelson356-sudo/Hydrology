"""
gui/widget_work6.py
Работа 6 — Водный баланс и испарение (PyQt6)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QMessageBox, QGroupBox, QFormLayout,
    QLineEdit, QTableWidget, QTableWidgetItem, QComboBox, QSplitter
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from gui.plot_style import auto_resize_table
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.hydrorash.water_balance import (
    water_balance, evaporation_dalton, evaporation_meschersky,
    pan_evaporation_to_lake, runoff_coefficient, water_budget_coefficient
)
from core.hydrorash.min_runoff_extended import (
    ecosystem_minimum, q7_10, compare_minimum_methods
)


class Work6Widget(QWidget):
    """Вкладка «Работа 6: Водный баланс и экосистемный минимум»."""

    def __init__(self):
        super().__init__()
        self.daily_data = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("ВОДНЫЙ БАЛАНС И ЭКОСИСТЕМНЫЙ МИНИМУМ")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2E7D32;")
        layout.addWidget(title)

        wb_group = QGroupBox("Водный баланс бассейна: W = P - E - R")
        wb_form = QFormLayout(wb_group)

        self.edit_precip = QLineEdit("600")
        wb_form.addRow("Осадки P, мм/год:", self.edit_precip)

        self.edit_evap = QLineEdit("400")
        wb_form.addRow("Испарение E, мм/год:", self.edit_evap)

        self.edit_runoff = QLineEdit("180")
        wb_form.addRow("Сток R, мм/год:", self.edit_runoff)

        self.btn_wb = QPushButton("Рассчитать баланс")
        self.btn_wb.clicked.connect(self.calc_water_balance)
        wb_form.addRow(self.btn_wb)

        layout.addWidget(wb_group)

        evap_group = QGroupBox("Калькулятор испарения")
        evap_form = QFormLayout(evap_group)

        self.edit_water_temp = QLineEdit("15")
        evap_form.addRow("Температура воды, °C:", self.edit_water_temp)

        self.edit_air_temp = QLineEdit("20")
        evap_form.addRow("Температура воздуха, °C:", self.edit_air_temp)

        self.edit_wind = QLineEdit("2.0")
        evap_form.addRow("Скорость ветра, м/с:", self.edit_wind)

        self.combo_evap_method = QComboBox()
        self.combo_evap_method.addItems(["Дальтон", "Мещерский"])
        evap_form.addRow("Метод:", self.combo_evap_method)

        self.btn_evap = QPushButton("Рассчитать испарение")
        self.btn_evap.clicked.connect(self.calc_evaporation)
        evap_form.addRow(self.btn_evap)

        layout.addWidget(evap_group)

        eco_group = QGroupBox("Экосистемный минимум")
        eco_form = QFormLayout(eco_group)

        self.edit_q_mean = QLineEdit("50")
        eco_form.addRow("Qср годовой, м³/с:", self.edit_q_mean)

        self.btn_eco = QPushButton("Рассчитать экосистемный минимум")
        self.btn_eco.clicked.connect(self.calc_ecosystem)
        eco_form.addRow(self.btn_eco)

        layout.addWidget(eco_group)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setFont(QFont("Consolas", 10))

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Параметр", "Значение"])
        auto_resize_table(self.table)

        results_splitter = QSplitter(Qt.Orientation.Vertical)
        results_splitter.addWidget(self.result_box)
        results_splitter.addWidget(self.table)
        results_splitter.setStretchFactor(0, 2)
        results_splitter.setStretchFactor(1, 1)
        results_splitter.setSizes([220, 140])
        layout.addWidget(results_splitter)

    def calc_water_balance(self):
        try:
            P = float(self.edit_precip.text())
            E = float(self.edit_evap.text())
            R = float(self.edit_runoff.text())

            result = water_balance(P, E, R)
            alpha = runoff_coefficient(R, P)
            beta = water_budget_coefficient(P, R)

            self.result_box.clear()
            self.result_box.append("=== ВОДНЫЙ БАЛАНС ===")
            self.result_box.append(f"P = {P} мм, E = {E} мм, R = {R} мм")
            self.result_box.append(f"Баланс: {result.get('balance_equation', 'Н/Д')}")
            self.result_box.append(f"Остаток: {result.get('residual_mm', 'Н/Д')} мм")
            self.result_box.append(f"Отклонение: {result.get('residual_pct', 'Н/Д')}%")
            self.result_box.append(f"Сбалансирован: {'да' if result.get('is_balanced') else 'нет'}")
            self.result_box.append(f"Коэффициент стока α = {alpha:.3f}")
            self.result_box.append(f"Водоносный коэффициент β = {beta:.3f}")

            self.table.setRowCount(7)
            items = [
                ("Осадки (P)", f"{P} мм/год"),
                ("Испарение (E)", f"{E} мм/год"),
                ("Сток (R)", f"{R} мм/год"),
                ("Остаток (W)", f"{result.get('residual_mm', 'Н/Д')} мм"),
                ("Отклонение", f"{result.get('residual_pct', 'Н/Д')}%"),
                ("Коэфф. стока (α)", f"{alpha:.3f}"),
                ("Водоносный коэфф. (β)", f"{beta:.3f}")
            ]
            for i, (k, v) in enumerate(items):
                self.table.setItem(i, 0, QTableWidgetItem(k))
                self.table.setItem(i, 1, QTableWidgetItem(v))

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def calc_evaporation(self):
        try:
            T_w = float(self.edit_water_temp.text())
            T_a = float(self.edit_air_temp.text())
            U = float(self.edit_wind.text())

            if self.combo_evap_method.currentText() == "Дальтон":
                E = evaporation_dalton(T_w, T_a, U)
                method = "Дальтон"
                unit = "мм/сут"
            else:
                E = evaporation_meschersky(T_a)
                method = "Мещерский"
                unit = "мм/мес"

            E_lake = pan_evaporation_to_lake(E * 30)

            self.result_box.clear()
            self.result_box.append(f"=== ИСПАРЕНИЕ ({method}) ===")
            self.result_box.append(f"Испарение: {E:.2f} {unit}")
            self.result_box.append(f"Для озера (×0.68): {E_lake:.2f} мм/мес")

            self.table.setRowCount(4)
            items = [
                ("Метод", method),
                ("Испарение", f"{E:.2f} {unit}"),
                ("Испарение для озера", f"{E_lake:.2f} мм/мес"),
                ("Температура воды/воздуха", f"{T_w}°C / {T_a}°C")
            ]
            for i, (k, v) in enumerate(items):
                self.table.setItem(i, 0, QTableWidgetItem(k))
                self.table.setItem(i, 1, QTableWidgetItem(v))

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def calc_ecosystem(self):
        try:
            Q_mean = float(self.edit_q_mean.text())

            result_10pct = ecosystem_minimum(Q_mean, method="tenpct")

            self.result_box.clear()
            self.result_box.append("=== ЭКОСИСТЕМНЫЙ МИНИМУМ ===")
            self.result_box.append(f"Qср = {Q_mean} м³/с")
            self.result_box.append(f"10% от Qср = {Q_mean * 0.1:.2f} м³/с")
            self.result_box.append(f"Q_экосистемный: {result_10pct.get('Q_ecosystem', 'Н/Д')} м³/с")
            self.result_box.append(f"Статус: {result_10pct.get('compliance_status', 'Н/Д')}")

            self.table.setRowCount(3)
            items = [
                ("Qср годовой", f"{Q_mean} м³/с"),
                ("Q_экосистемный", f"{result_10pct.get('Q_ecosystem', 'Н/Д')} м³/с"),
                ("Статус соответствия", str(result_10pct.get('compliance_status', 'Н/Д')))
            ]
            for i, (k, v) in enumerate(items):
                self.table.setItem(i, 0, QTableWidgetItem(k))
                self.table.setItem(i, 1, QTableWidgetItem(v))

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def set_data(self, daily_df=None):
        if daily_df is not None:
            self.daily_data = daily_df

    def set_qsr(self, q_mean=None):
        """Авто-заполнение Qср из Work1."""
        if q_mean is not None:
            self.edit_q_mean.setText(f"{q_mean:.2f}")
