"""
gui/widget_work7.py
Работа 7 — Метод рациона, IDF, паводочная кривая, снеготаяние (PyQt6)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from gui.plot_style import apply_global_style, setup_axes_style, COLORS

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QGroupBox, QFormLayout, QLineEdit,
    QTableWidget, QTableWidgetItem, QComboBox, QTabWidget,
    QDoubleSpinBox, QSpinBox, QSplitter
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from core.hydrorash.rational_method import (
    rational_method, idf_curve, design_rainfall,
    time_of_concentration, check_rational_validity,
    IDF_ZONES, ZONE_RUNOFF_COEFFICIENTS
)
from core.hydrorash.flood_hydrograph import (
    triangular_hydrograph, gamma_hydrograph,
    unit_hydrograph, flood_volume
)
from core.hydrorash.snowmelt import (
    snowmelt_degree_day, snowmelt_peak_runoff,
    melt_rate_by_zone, MELT_COEFFICIENTS
)


class Work7Widget(QWidget):
    """Вкладка «Работа 7: Метод рациона и гидрографы»."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #CE93D8; border-radius: 4px; }
            QTabBar::tab {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #F3E5F5, stop:1 #E1BEE7);
                border: 1px solid #BA68C8; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                padding: 6px 14px; margin-right: 2px; font-size: 11px; font-weight: bold;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #8E24AA, stop:1 #4A148C);
                color: white; border: 1px solid #4A148C; padding-bottom: 8px;
            }
            QTabBar::tab:hover:!selected { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #E1BEE7, stop:1 #CE93D8); }
        """)
        tabs.addTab(self._create_rational_tab(), "Метод рациона + IDF")
        tabs.addTab(self._create_hydrograph_tab(), "Паводочный гидрограф")
        tabs.addTab(self._create_snowmelt_tab(), "Снеготаяние")

        layout.addWidget(tabs)

    def _create_rational_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры расчёта")
        form = QFormLayout(grp)

        self.zone_combo = QComboBox()
        for k, v in IDF_ZONES.items():
            self.zone_combo.addItem(f"{v['name']} ({k})", k)
        self.zone_combo.setCurrentIndex(2)
        form.addRow("Климатическая зона:", self.zone_combo)

        self.spin_F = QDoubleSpinBox()
        self.spin_F.setRange(0.1, 1000)
        self.spin_F.setValue(25)
        self.spin_F.setSuffix(" км²")
        form.addRow("Площадь бассейна F:", self.spin_F)

        self.spin_T = QDoubleSpinBox()
        self.spin_T.setRange(1, 1000)
        self.spin_T.setValue(10)
        self.spin_T.setSuffix(" лет")
        form.addRow("Обеспеченность T:", self.spin_T)

        self.spin_t = QDoubleSpinBox()
        self.spin_t.setRange(5, 1440)
        self.spin_t.setValue(60)
        self.spin_t.setSuffix(" мин")
        form.addRow("Время концентрации t:", self.spin_t)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(0.1, 1.0)
        self.spin_alpha.setValue(0.70)
        self.spin_alpha.setSingleStep(0.05)
        form.addRow("Коэфф. стока α:", self.spin_alpha)

        lay.addWidget(grp)

        btn_row = QHBoxLayout()
        btn_calc = QPushButton("Рассчитать")
        btn_calc.setStyleSheet("QPushButton { background: #1976D2; color: white; font-weight: bold; }")
        btn_calc.clicked.connect(self.calculate_rational)
        btn_row.addWidget(btn_calc)
        lay.addLayout(btn_row)

        self.figure = Figure(figsize=(10, 4))
        self.canvas = FigureCanvas(self.figure)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self.result_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 140])
        lay.addWidget(splitter)

        return w

    def _create_hydrograph_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры гидрографа")
        form = QFormLayout(grp)

        self.hg_Qpeak = QDoubleSpinBox()
        self.hg_Qpeak.setRange(0.1, 100000)
        self.hg_Qpeak.setValue(100)
        self.hg_Qpeak.setSuffix(" м³/с")
        form.addRow("Q пиковый:", self.hg_Qpeak)

        self.hg_Tpeak = QDoubleSpinBox()
        self.hg_Tpeak.setRange(0.5, 720)
        self.hg_Tpeak.setValue(12)
        self.hg_Tpeak.setSuffix(" ч")
        form.addRow("Время нарастания:", self.hg_Tpeak)

        self.hg_Tbase = QDoubleSpinBox()
        self.hg_Tbase.setRange(1, 2000)
        self.hg_Tbase.setValue(48)
        self.hg_Tbase.setSuffix(" ч")
        form.addRow("Длительность паводка:", self.hg_Tbase)

        self.hg_method = QComboBox()
        self.hg_method.addItems(["Гамма (СП 33)", "Треугольный"])
        form.addRow("Метод:", self.hg_method)

        lay.addWidget(grp)

        btn_row = QHBoxLayout()
        btn = QPushButton("Построить гидрограф")
        btn.setStyleSheet("QPushButton { background: #388E3C; color: white; font-weight: bold; }")
        btn.clicked.connect(self.build_hydrograph)
        btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        self.hg_figure = Figure(figsize=(10, 4))
        self.hg_canvas = FigureCanvas(self.hg_figure)

        self.hg_result = QTextEdit()
        self.hg_result.setReadOnly(True)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.hg_canvas)
        splitter.addWidget(self.hg_result)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 140])
        lay.addWidget(splitter)

        return w

    def _create_snowmelt_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры снеготаяния")
        form = QFormLayout(grp)

        self.sm_zone = QComboBox()
        for k, v in MELT_COEFFICIENTS.items():
            self.sm_zone.addItem(f"{v['name']} ({k})", k)
        self.sm_zone.setCurrentIndex(2)
        form.addRow("Климатическая зона:", self.sm_zone)

        self.sm_W = QDoubleSpinBox()
        self.sm_W.setRange(10, 500)
        self.sm_W.setValue(150)
        self.sm_W.setSuffix(" мм")
        form.addRow("Начальный запас воды (ЗВС):", self.sm_W)

        self.sm_T = QDoubleSpinBox()
        self.sm_T.setRange(-5, 25)
        self.sm_T.setValue(8)
        self.sm_T.setSuffix(" °С")
        form.addRow("Средняя T воздуха:", self.sm_T)

        self.sm_days = QSpinBox()
        self.sm_days.setRange(5, 120)
        self.sm_days.setValue(30)
        self.sm_days.setSuffix(" суток")
        form.addRow("Длительность периода:", self.sm_days)

        lay.addWidget(grp)

        btn_row = QHBoxLayout()
        btn = QPushButton("Рассчитать снеготаяние")
        btn.setStyleSheet("QPushButton { background: #00897B; color: white; font-weight: bold; }")
        btn.clicked.connect(self.calculate_snowmelt)
        btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        self.sm_figure = Figure(figsize=(10, 4))
        self.sm_canvas = FigureCanvas(self.sm_figure)

        self.sm_result = QTextEdit()
        self.sm_result.setReadOnly(True)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.sm_canvas)
        splitter.addWidget(self.sm_result)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 140])
        lay.addWidget(splitter)

        return w

    def calculate_rational(self):
        zone = self.zone_combo.currentData()
        F = self.spin_F.value()
        T = self.spin_T.value()
        t = self.spin_t.value()
        alpha = self.spin_alpha.value()

        validity = check_rational_validity(F, t, zone)
        result = rational_method(F, T, t, alpha, zone)
        idf = idf_curve(T, zone=zone)

        self.result_box.clear()
        if not validity['is_valid']:
            for w in validity['warnings']:
                self.result_box.append(f"⚠ {w}")

        self.result_box.append(f"Q = {result['Q_m3_s']:.2f} м³/с")
        self.result_box.append(f"Интенсивность: {result['intensity_mm_h']:.1f} мм/ч")
        self.result_box.append(f"Глубина дождя: {result['depth_mm']:.1f} мм")
        self.result_box.append(f"α = {alpha}, F = {F} км², T = {T} лет, t = {t} мин")

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(idf['durations_min'], idf['intensities_mm_h'], 'o-', color='#1976D2', linewidth=2)
        ax.axhline(y=result['intensity_mm_h'], color='#F44336', linestyle='--',
                    label=f"i = {result['intensity_mm_h']:.1f} мм/ч")
        ax.axvline(x=t, color='#F44336', linestyle=':', alpha=0.5)
        ax.set_xlabel("Длительность, мин")
        ax.set_ylabel("Интенсивность, мм/ч")
        ax.set_title(f"IDF-кривая (T={T} лет)")
        ax.set_xscale('log')
        ax.grid(True, alpha=0.5)
        ax.legend()
        self.canvas.draw()

    def build_hydrograph(self):
        Qpeak = self.hg_Qpeak.value()
        Tpeak = self.hg_Tpeak.value()
        Tbase = self.hg_Tbase.value()

        if self.hg_method.currentIndex() == 0:
            hg = gamma_hydrograph(Qpeak, Tpeak, Tbase)
            method = "Гамма"
        else:
            hg = triangular_hydrograph(Qpeak, Tpeak, Tbase)
            method = "Треугольный"

        vol = flood_volume(np.array(hg['Q_m3_s']))

        self.hg_result.clear()
        self.hg_result.append(f"Qпик = {Qpeak} м³/с | Tнар = {Tpeak} ч | Tполн = {Tbase} ч")
        self.hg_result.append(f"Объём паводка: {vol['volume_mln_m3']:.1f} млн м³ ({vol['volume_km3']:.4f} км³)")

        self.hg_figure.clear()
        ax = self.hg_figure.add_subplot(111)
        ax.fill_between(hg['t_hours'], hg['Q_m3_s'], alpha=0.3, color='#42A5F5')
        ax.plot(hg['t_hours'], hg['Q_m3_s'], color='#1565C0', linewidth=2)
        ax.set_xlabel("Время, ч")
        ax.set_ylabel("Расход, м³/с")
        ax.set_title(f"Гидрограф паводка ({method})")
        ax.grid(True, alpha=0.5)
        ax.axhline(y=Qpeak, color='#F44336', linestyle='--', alpha=0.5, label=f"Qпик = {Qpeak}")
        ax.legend()
        self.hg_canvas.draw()

    def calculate_snowmelt(self):
        zone = self.sm_zone.currentData()
        W = self.sm_W.value()
        T = self.sm_T.value()
        days = self.sm_days.value()

        A = MELT_COEFFICIENTS[zone]['A']
        melt_total = A * max(T, 0) * days
        melt_total = min(melt_total, W)

        self.sm_result.clear()
        self.sm_result.append(f"Степень таяния: {A} × {max(T, 0)} = {A * max(T, 0):.1f} мм/сутки")
        self.sm_result.append(f"Общее таяние за {days} суток: {melt_total:.1f} мм из {W} мм запаса")
        self.sm_result.append(f"Остаток снега: {max(W - melt_total, 0):.1f} мм")

        t_array = np.arange(days, dtype=float)
        T_array = np.full(days, T, dtype=float)

        result = snowmelt_degree_day(W, T_array, A)

        self.sm_figure.clear()
        ax = self.sm_figure.add_subplot(121)
        ax.bar(t_array, result['daily_melt_mm'], color='#42A5F5', alpha=0.7)
        ax.set_xlabel("День")
        ax.set_ylabel("Таяние, мм/сутки")
        ax.set_title("Суточное таяние")
        ax.grid(True, alpha=0.5)

        ax2 = self.sm_figure.add_subplot(122)
        ax2.plot(t_array, result['remaining_snow_mm'], color='#1565C0', linewidth=2)
        ax2.set_xlabel("День")
        ax2.set_ylabel("Запас воды, мм")
        ax2.set_title("Остаток снега")
        ax2.grid(True, alpha=0.5)
        self.sm_figure.tight_layout()
        self.sm_canvas.draw()

    def set_data(self, daily_df=None, F=None, zone=None):
        """Приём данных из единого загрузчика."""
        if F is not None and hasattr(self, 'spin_F'):
            self.spin_F.setValue(float(F))
        if zone is not None and hasattr(self, 'zone_combo'):
            idx = self.zone_combo.findData(zone)
            if idx >= 0:
                self.zone_combo.setCurrentIndex(idx)
