"""
gui/widget_work1.py
Работа 1 — Норма годового стока (PyQt6)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from gui.plot_style import apply_global_style, setup_axes_style, COLORS

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QLineEdit, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout, QTableWidget, QTableWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.hydrorash.utils import (
    compute_basic_stats, linear_regression_reduction,
    extend_series, empirical_probability, kritsky_menkel_quantiles, module_layer
)


class Work1Widget(QWidget):
    """Вкладка «Работа 1: Норма годового стока»."""

    calculation_done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.last_result = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # === Верхняя панель ===
        top = QHBoxLayout()

        btn_group = QGroupBox("Данные")
        btn_layout = QVBoxLayout(btn_group)

        self.btn_load_calc = QPushButton("Загрузить расчётную реку (Excel)")
        self.btn_load_calc.clicked.connect(self.load_calc_data)
        btn_layout.addWidget(self.btn_load_calc)

        self.btn_load_analog = QPushButton("Загрузить реку-аналог (Excel)")
        self.btn_load_analog.clicked.connect(self.load_analog_data)
        btn_layout.addWidget(self.btn_load_analog)

        self.btn_calc = QPushButton("РАССЧИТАТЬ")
        self.btn_calc.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; "
            "font-weight: bold; padding: 10px 20px; font-size: 14px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.btn_calc.clicked.connect(self.calculate)
        btn_layout.addWidget(self.btn_calc)

        self.btn_graphs = QPushButton("Показать графики")
        self.btn_graphs.clicked.connect(self.show_graphs)
        btn_layout.addWidget(self.btn_graphs)

        self.btn_save = QPushButton("Сохранить отчёт")
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; "
            "font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )
        self.btn_save.clicked.connect(self.save_report)
        btn_layout.addWidget(self.btn_save)

        # Поля ввода
        form_group = QGroupBox("Параметры")
        form = QFormLayout(form_group)

        self.edit_f_calc = QLineEdit("31800")
        self.edit_f_analog = QLineEdit("24700")
        self.edit_name_calc = QLineEdit("Бирюса, с. Шиткино")
        self.edit_name_analog = QLineEdit("Бирюса, р.п. Суетиха")

        form.addRow("Река:", self.edit_name_calc)
        form.addRow("F расчётной (км²):", self.edit_f_calc)
        form.addRow("Река-аналог:", self.edit_name_analog)
        form.addRow("F аналога (км²):", self.edit_f_analog)

        top.addWidget(btn_group)
        top.addWidget(form_group)
        layout.addLayout(top)

        # === Текст результатов ===
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setFont(__import__("PyQt6.QtGui", fromlist=["QFont"]).QFont("Consolas", 10))
        self.result_box.setMaximumHeight(220)
        layout.addWidget(QLabel("Результаты расчёта:"))
        layout.addWidget(self.result_box)

        # === График ===
        self.figure = Figure(figsize=(12, 5))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    def load_calc_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить данные", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            df = pd.read_excel(path)
            if df.shape[1] >= 2:
                self._q_calc_data = pd.Series(df.iloc[:, 1].values, index=df.iloc[:, 0].astype(int).values)
                self.result_box.append(f"Загружена расчётная река: {len(self._q_calc_data)} значений")
            else:
                self._q_calc_data = None
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def load_analog_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить аналог", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            df = pd.read_excel(path)
            if df.shape[1] >= 2:
                self._q_analog_data = pd.Series(df.iloc[:, 1].values, index=df.iloc[:, 0].astype(int).values)
                self.result_box.append(f"Загружен аналог: {len(self._q_analog_data)} значений")
            else:
                self._q_analog_data = None
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _generate_demo_data(self):
        """Генерация демо-данных для тестирования."""
        years_calc = list(range(1944, 1976))
        Q_calc_vals = [361,210,364,250,225,241,287,284,403,274,306,395,243,291,253,264,276,288,268,266,243,318,376,308,310,226,226,260,307,372,203,290]

        years_analog = list(range(1936, 1976))
        Q_analog_vals = [335,280,276,292,252,339,200,159,329,177,320,229,203,221,262,249,368,243,283,367,218,256,223,250,260,269,252,244,215,297,341,280,203,250,369,252,278,323,181,264]

        self._q_calc_data = pd.Series(Q_calc_vals, index=years_calc)
        self._q_analog_data = pd.Series(Q_analog_vals, index=years_analog)
        self.result_box.append("Загружены демо-данные (Бирюса)")

    def calculate(self):
        # Используем загруженные данные или демо
        q_calc = getattr(self, '_q_calc_data', None)
        q_analog = getattr(self, '_q_analog_data', None)

        if q_calc is None or q_analog is None:
            self._generate_demo_data()
            q_calc = self._q_calc_data
            q_analog = self._q_analog_data

        try:
            f_calc = float(self.edit_f_calc.text().replace(",", "."))
            f_analog = float(self.edit_f_analog.text().replace(",", "."))

            stats_short = compute_basic_stats(q_calc, use_normative_Cs=True)
            reg = linear_regression_reduction(q_calc, q_analog)
            q_ext = extend_series(q_calc, q_analog, reg)
            stats_ext = compute_basic_stats(q_ext, use_normative_Cs=True)

            mod_short = module_layer(stats_short["mean"], f_calc)
            mod_ext = module_layer(stats_ext["mean"], f_calc)

            self.last_result = {
                "q_calc": q_calc, "q_analog": q_analog,
                "stats_short": stats_short, "stats_ext": stats_ext,
                "reg": reg, "q_ext": q_ext,
                "mod_short": mod_short, "mod_ext": mod_ext,
                "f_calc": f_calc
            }

            self.result_box.clear()
            self.result_box.append("═══ НОРМА ГОДОВОГО СТОКА (СП 33-101-2003) ═══\n")

            self.result_box.append(f"▸ Короткий ряд (n={stats_short['n']}):")
            self.result_box.append(f"  Q̅ = {stats_short['mean']:.3f} м³/с | Cv = {stats_short['Cv']:.4f} | ε = {stats_short['epsilon']:.2f}%")
            self.result_box.append(f"  Модуль: {mod_short['q']:.2f} л/с·км² | Объём: {mod_short['W']:.4f} км³ | Слой: {mod_short['h']:.1f} мм")
            self.result_box.append(f"  Надёжность: {stats_short['reliability_class']}\n")

            self.result_box.append(f"▸ Приведённый ряд (n={stats_ext['n']}):")
            self.result_box.append(f"  Q̅ = {stats_ext['mean']:.3f} м³/с | Cv = {stats_ext['Cv']:.4f} | ε = {stats_ext['epsilon']:.2f}%")
            self.result_box.append(f"  Модуль: {mod_ext['q']:.2f} л/с·км² | Объём: {mod_ext['W']:.4f} км³ | Слой: {mod_ext['h']:.1f} мм")
            self.result_box.append(f"  Надёжность: {stats_ext['reliability_class']}\n")

            self.result_box.append(f"▸ Регрессия: a = {reg['a']:.6f}, b = {reg['b']:.4f}, R = {reg['R']:.6f}")

            for w in stats_short.get('warnings', []):
                self.result_box.append(f"  {w}")

            self.result_box.append("\n═══ Рекомендуется: приведённый ряд ═══")

            self.calculation_done.emit(self.last_result)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def set_data(self, calc_series=None, analog_series=None, f_calc=None, f_analog=None, name_calc=None, name_analog=None):
        """Приём данных из единого загрузчика шаблона."""
        if calc_series is not None:
            self._q_calc_data = calc_series
        if analog_series is not None:
            self._q_analog_data = analog_series
        if f_calc is not None:
            self.edit_f_calc.setText(str(f_calc))
        if f_analog is not None:
            self.edit_f_analog.setText(str(f_analog))
        if name_calc is not None:
            self.edit_name_calc.setText(name_calc)
        if name_analog is not None:
            self.edit_name_analog.setText(name_analog)
        self.result_box.append("📥 Данные загружены из шаблона.")

    def show_graphs(self):
        if not self.last_result:
            QMessageBox.warning(self, "Внимание", "Сначала нажмите «РАССЧИТАТЬ»")
            return

        r = self.last_result
        self.figure.clear()

        # График 1: Хронологический
        ax1 = self.figure.add_subplot(121)
        ax1.plot(r["q_calc"].index, r["q_calc"].values, 'o-', color='#0066CC',
                 markersize=4, label='Расчётная река', linewidth=1.5)
        ax1.plot(r["q_analog"].index, r["q_analog"].values, 's--', color='#FF6600',
                 markersize=3, label='Аналог', linewidth=1, alpha=0.7)
        ax1.axhline(r["stats_short"]["mean"], color='red', ls='--', lw=1.5,
                     label=f'Q̅ = {r["stats_short"]["mean"]:.2f}')
        ax1.axhline(r["stats_ext"]["mean"], color='darkred', ls='-.', lw=1.5,
                     label=f'Q̅прив. = {r["stats_ext"]["mean"]:.2f}')
        ax1.set_title('Хронологический график', fontsize=11, fontweight='bold')
        ax1.set_xlabel('Годы')
        ax1.set_ylabel('Q, м³/с')
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # График 2: Кривая обеспеченностей
        ax2 = self.figure.add_subplot(122)
        emp_calc = empirical_probability(r["q_calc"])
        emp_ext = empirical_probability(r["q_ext"])
        ax2.plot(emp_calc["P_%"], emp_calc["Q"], 'o', color='#0066CC', markersize=4, label='Короткий ряд')
        ax2.plot(emp_ext["P_%"], emp_ext["Q"], 's', color='#FF6600', markersize=4, label='Приведённый')
        km = kritsky_menkel_quantiles(r["stats_ext"]["mean"], r["stats_ext"]["Cv"], 2.0,
                                       [0.1, 1, 5, 10, 25, 50, 75, 90, 95, 99])
        ax2.plot(km["P_%"], km["Q_p"], '-', color='red', lw=2, label='Крицкий-Менкель')
        ax2.set_title('Кривые обеспеченностей', fontsize=11, fontweight='bold')
        ax2.set_xlabel('Обеспеченность P, %')
        ax2.set_ylabel('Q, м³/с')
        ax2.set_xlim(0, 100)
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

        self.figure.tight_layout()
        self.canvas.draw()

    def save_report(self):
        if not self.last_result:
            QMessageBox.warning(self, "Внимание", "Сначала рассчитайте")
            return

        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", "Отчёт_Работа1.xlsx", "Excel (*.xlsx)")
        if not filepath:
            return

        r = self.last_result
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            pd.DataFrame([r["stats_short"], r["stats_ext"]]).to_excel(writer, sheet_name="Статистика")
            km = kritsky_menkel_quantiles(r["stats_ext"]["mean"], r["stats_ext"]["Cv"], 2.0,
                                           [0.1,1,5,10,25,50,75,90,95,99])
            km.to_excel(writer, sheet_name="Кривая К-М", index=False)

        QMessageBox.information(self, "Готово", f"Отчёт сохранён:\n{filepath}")
