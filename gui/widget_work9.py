"""
gui/widget_work9.py
Работа 9 — Гидротехнические расчёты: ППУ, ГВП, регулирование (PyQt6)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from gui.plot_style import apply_global_style, setup_axes_style, COLORS, auto_resize_table

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QGroupBox, QFormLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QComboBox,
    QDoubleSpinBox, QSpinBox, QFileDialog, QTabWidget, QSplitter
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from core.hydrorash.spillway import (
    free_overfall, weir_flow, orifice_flow,
    spillway_capacity_check, emergency_flood_passage
)
from core.hydrorash.backwater import (
    normal_depth, critical_depth, backwater_curve_step,
    backwater_from_reservoir
)
from core.hydrorash.reservoir_regulation import (
    multi_year_regulation, annual_regulation_table,
    reservoir_storage_calculation
)


class Work9Widget(QWidget):
    """Вкладка «Работа 9: Гидротехнические расчёты»."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #FFCC80; border-radius: 4px; }
            QTabBar::tab {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FFF3E0, stop:1 #FFE0B2);
                border: 1px solid #FFA726; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                padding: 6px 14px; margin-right: 2px; font-size: 11px; font-weight: bold;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FB8C00, stop:1 #E65100);
                color: white; border: 1px solid #E65100; padding-bottom: 8px;
            }
            QTabBar::tab:hover:!selected { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FFE0B2, stop:1 #FFCC80); }
        """)
        tabs.addTab(self._create_spillway_tab(), "Пропускная способность ППУ")
        tabs.addTab(self._create_backwater_tab(), "Кривые подпора (ГВП)")
        tabs.addTab(self._create_regulation_tab(), "Регулирование стока")
        layout.addWidget(tabs)

    def _create_spillway_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры водосброса")
        form = QFormLayout(grp)

        self.sp_Q = QDoubleSpinBox()
        self.sp_Q.setRange(0.1, 100000)
        self.sp_Q.setValue(500)
        self.sp_Q.setSuffix(" м³/с")
        form.addRow("Расход паводка Q:", self.sp_Q)

        self.sp_L = QDoubleSpinBox()
        self.sp_L.setRange(1, 1000)
        self.sp_L.setValue(20)
        self.sp_L.setSuffix(" м")
        form.addRow("Длина гребня L:", self.sp_L)

        self.sp_H = QDoubleSpinBox()
        self.sp_H.setRange(0.1, 30)
        self.sp_H.setValue(3)
        self.sp_H.setSuffix(" м")
        form.addRow("Напор H:", self.sp_H)

        self.sp_type = QComboBox()
        self.sp_type.addItems(["Тонкостенная (Cd=1.84)", "Трапеция (Cd=1.50)", "Оgee-профиль (Cd=2.20)", "Шахта (орифиция)"])
        form.addRow("Тип:", self.sp_type)

        lay.addWidget(grp)

        btn = QPushButton("Проверить пропускную способность")
        btn.setStyleSheet("QPushButton { background: #D32F2F; color: white; font-weight: bold; }")
        btn.clicked.connect(self.check_spillway)
        lay.addWidget(btn)

        self.sp_result = QTextEdit()
        self.sp_result.setReadOnly(True)
        lay.addWidget(self.sp_result)

        return w

    def _create_backwater_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры русла и водохранилища")
        form = QFormLayout(grp)

        self.bw_Q = QDoubleSpinBox()
        self.bw_Q.setRange(0.1, 10000)
        self.bw_Q.setValue(50)
        self.bw_Q.setSuffix(" м³/с")
        form.addRow("Расход Q:", self.bw_Q)

        self.bw_B = QDoubleSpinBox()
        self.bw_B.setRange(1, 500)
        self.bw_B.setValue(20)
        self.bw_B.setSuffix(" м")
        form.addRow("Ширина дна B:", self.bw_B)

        self.bw_m = QDoubleSpinBox()
        self.bw_m.setRange(0, 10)
        self.bw_m.setValue(2)
        form.addRow("Откос бортов m:", self.bw_m)

        self.bw_n = QDoubleSpinBox()
        self.bw_n.setRange(0.01, 0.1)
        self.bw_n.setValue(0.035)
        self.bw_n.setSingleStep(0.005)
        form.addRow("Коэфф. Маннинга n:", self.bw_n)

        self.bw_I = QDoubleSpinBox()
        self.bw_I.setRange(0.0001, 0.1)
        self.bw_I.setValue(0.001)
        self.bw_I.setSingleStep(0.0001)
        self.bw_I.setDecimals(4)
        form.addRow("Уклон I:", self.bw_I)

        self.bw_Hres = QDoubleSpinBox()
        self.bw_Hres.setRange(0.5, 50)
        self.bw_Hres.setValue(5)
        self.bw_Hres.setSuffix(" м")
        form.addRow("Уровень в водохр.:", self.bw_Hres)

        self.bw_L = QDoubleSpinBox()
        self.bw_L.setRange(100, 50000)
        self.bw_L.setValue(5000)
        self.bw_L.setSuffix(" м")
        form.addRow("Длина участка:", self.bw_L)

        lay.addWidget(grp)

        btn = QPushButton("Рассчитать ГВП")
        btn.setStyleSheet("QPushButton { background: #1565C0; color: white; font-weight: bold; }")
        btn.clicked.connect(self.calculate_backwater)
        lay.addWidget(btn)

        self.bw_figure = Figure(figsize=(10, 4))
        self.bw_canvas = FigureCanvas(self.bw_figure)

        self.bw_result = QTextEdit()
        self.bw_result.setReadOnly(True)

        bw_splitter = QSplitter(Qt.Orientation.Vertical)
        bw_splitter.addWidget(self.bw_canvas)
        bw_splitter.addWidget(self.bw_result)
        bw_splitter.setStretchFactor(0, 3)
        bw_splitter.setStretchFactor(1, 1)
        bw_splitter.setSizes([260, 140])
        lay.addWidget(bw_splitter)

        return w

    def _create_regulation_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры регулирования")
        form = QFormLayout(grp)

        self.reg_Qmean = QDoubleSpinBox()
        self.reg_Qmean.setRange(1, 50000)
        self.reg_Qmean.setValue(100)
        self.reg_Qmean.setSuffix(" м³/с")
        form.addRow("Средний расход Q:", self.reg_Qmean)

        self.reg_demand = QDoubleSpinBox()
        self.reg_demand.setRange(0.1, 50000)
        self.reg_demand.setValue(30)
        self.reg_demand.setSuffix(" м³/с")
        form.addRow("Забор воды:", self.reg_demand)

        lay.addWidget(grp)

        btn = QPushButton("Рассчитать регулирование")
        btn.setStyleSheet("QPushButton { background: #2E7D32; color: white; font-weight: bold; }")
        btn.clicked.connect(self.calculate_regulation)
        lay.addWidget(btn)

        self.reg_figure = Figure(figsize=(10, 4))
        self.reg_canvas = FigureCanvas(self.reg_figure)

        self.reg_table = QTableWidget()
        auto_resize_table(self.reg_table)

        reg_splitter = QSplitter(Qt.Orientation.Vertical)
        reg_splitter.addWidget(self.reg_canvas)
        reg_splitter.addWidget(self.reg_table)
        reg_splitter.setStretchFactor(0, 3)
        reg_splitter.setStretchFactor(1, 1)
        reg_splitter.setSizes([260, 160])
        lay.addWidget(reg_splitter)

        return w

    def check_spillway(self):
        Q = self.sp_Q.value()
        L = self.sp_L.value()
        H = self.sp_H.value()

        if self.sp_type.currentIndex() < 3:
            cd_map = [1.84, 1.50, 2.20]
            Cd = cd_map[self.sp_type.currentIndex()]
            result = spillway_capacity_check(Q, H, L, Cd=Cd)
        else:
            A = L * 2.0
            Q_cap = orifice_flow(H, A)
            result = {
                'Q_capacity_m3_s': round(Q_cap, 2),
                'Q_design_m3_s': Q,
                'margin_percent': round((Q_cap - Q) / Q * 100, 1) if Q > 0 else 0,
                'is_sufficient': Q_cap >= Q,
                'H_max_m': H,
                'L_m': L,
            }

        self.sp_result.clear()
        if result['is_sufficient']:
            self.sp_result.append(f"✅ Водосброс ПРОПУСКАЕТ паводок (Q={result['Q_capacity_m3_s']:.1f} м³/с)")
        else:
            self.sp_result.append(f"❌ Водосброс НЕ ПРОПУСКАЕТ паводок!")
        self.sp_result.append(f"Пропускная способность: {result['Q_capacity_m3_s']:.1f} м³/с")
        self.sp_result.append(f"Расчётный расход: {result['Q_design_m3_s']:.1f} м³/с")
        self.sp_result.append(f"Запас: {result['margin_percent']:.1f}%")

    def calculate_backwater(self):
        Q = self.bw_Q.value()
        B = self.bw_B.value()
        m = self.bw_m.value()
        n = self.bw_n.value()
        I = self.bw_I.value()
        Hres = self.bw_Hres.value()
        L = self.bw_L.value()

        result = backwater_from_reservoir(Q, B, m, n, I, Hres, L)

        self.bw_result.clear()
        self.bw_result.append(f"Нормальная глубина hн = {result['normal_depth']} м")
        self.bw_result.append(f"Длина линии подпора: {result['L_backwater_km']} км")

        res = result['result']
        self.bw_figure.clear()
        ax = self.bw_figure.add_subplot(111)
        ax.plot([d / 1000 for d in res['distances_m']], res['depths_m'],
                color='#1565C0', linewidth=2)
        ax.axhline(y=result['normal_depth'], color='#388E3C', linestyle='--',
                    label=f"hн = {result['normal_depth']} м")
        ax.axhline(y=Hres, color='#F44336', linestyle=':',
                    label=f"H_вдхр = {Hres} м")
        ax.set_xlabel("Расстояние от плотины, км")
        ax.set_ylabel("Глубина, м")
        ax.set_title("Кривая подпора (ГВП)")
        ax.grid(True, alpha=0.5)
        ax.legend()
        self.bw_canvas.draw()

    def calculate_regulation(self):
        Q = self.reg_Qmean.value()
        demand = self.reg_demand.value()

        np.random.seed(42)
        Q_annual = np.random.normal(Q, Q * 0.3, 30)

        result = multi_year_regulation(Q_annual, demand)

        self.reg_table.setColumnCount(2)
        self.reg_table.setHorizontalHeaderLabels(['Параметр', 'Значение'])
        rows = [
            ('Средний расход Qср', f"{result['Q_mean']} м³/с"),
            ('Забор воды', f"{result['Q_demand']} м³/с"),
            ('Необходимый объём', f"{result.get('required_volume_km3', '∞')} км³"),
            ('Необходимый объём', f"{result.get('required_volume_mln_m3', '∞')} млн м³"),
            ('Гарантия', f"{result['guarantee_percent']}%"),
        ]
        if 'warning' in result:
            rows.append(('ВНИМАНИЕ', result['warning']))

        self.reg_table.setRowCount(len(rows))
        for i, (a, b) in enumerate(rows):
            self.reg_table.setItem(i, 0, QTableWidgetItem(a))
            self.reg_table.setItem(i, 1, QTableWidgetItem(b))

        months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                  'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        Q_monthly = np.random.normal(Q, Q * 0.3, 12)
        table = annual_regulation_table(Q_monthly, demand)

        self.reg_figure.clear()
        ax = self.reg_figure.add_subplot(111)
        x = range(12)
        ax.bar(x, Q_monthly, color='#42A5F5', alpha=0.7, label='Приток')
        ax.axhline(y=demand, color='#F44336', linewidth=2, label=f'Забор = {demand} м³/с')
        ax.set_xticks(x)
        ax.set_xticklabels(months)
        ax.set_ylabel("Расход, м³/с")
        ax.set_title("Годовой баланс стока")
        ax.legend()
        ax.grid(True, alpha=0.5)
        self.reg_figure.tight_layout()
        self.reg_canvas.draw()

    def set_data(self, daily_df=None, Q=None, B=None, slope=None):
        """Приём данных из единого загрузчика."""
        if Q is not None and hasattr(self, 'sp_Q'):
            self.sp_Q.setValue(float(Q))
            if hasattr(self, 'bw_Q'):
                self.bw_Q.setValue(float(Q))
        if B is not None and hasattr(self, 'bw_B'):
            self.bw_B.setValue(float(B))
