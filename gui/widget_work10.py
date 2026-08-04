"""
gui/widget_work10.py
Работа 10 — Экология, базовый сток, спектральный анализ, засухи (PyQt6)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from gui.plot_style import apply_global_style, setup_axes_style, COLORS, auto_resize_table

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QGroupBox, QFormLayout,
    QTableWidget, QTableWidgetItem, QComboBox,
    QDoubleSpinBox, QSpinBox, QFileDialog, QTabWidget, QSplitter
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from core.hydrorash.ecological_flow import (
    tessmann_seasonal, ecoregime_classes, min_flow_comparison,
    SEASONAL_TESSMANN_PARAMS
)
from core.stats.baseflow import (
    baseflow_straight_line, baseflow_digital_filter,
    baseflow_lyne_hollick, baseflow_statistics
)
from core.stats.spectral import (
    fft_analysis, power_spectrum, hurst_exponent, find_periodicity
)
from core.stats.drought import (
    spi_index, drought_classification, drought_frequency
)
from core.stats.sheet_reader import read_work_sheet, numeric_column


class Work10Widget(QWidget):
    """Вкладка «Работа 10: Экология и специальные расчёты»."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #EF9A9A; border-radius: 4px; }
            QTabBar::tab {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FFEBEE, stop:1 #FFCDD2);
                border: 1px solid #EF5350; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                padding: 6px 14px; margin-right: 2px; font-size: 11px; font-weight: bold;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #E53935, stop:1 #B71C1C);
                color: white; border: 1px solid #B71C1C; padding-bottom: 8px;
            }
            QTabBar::tab:hover:!selected { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #FFCDD2, stop:1 #EF9A9A); }
        """)
        tabs.addTab(self._create_eco_tab(), "Экологический сток")
        tabs.addTab(self._create_baseflow_tab(), "Базовый сток")
        tabs.addTab(self._create_spectral_tab(), "Спектр + Хёрст")
        tabs.addTab(self._create_drought_tab(), "Индексы засухи")
        layout.addWidget(tabs)

    def _create_eco_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры")
        form = QFormLayout(grp)

        self.eco_Qmean = QDoubleSpinBox()
        self.eco_Qmean.setRange(0.1, 100000)
        self.eco_Qmean.setValue(50)
        self.eco_Qmean.setSuffix(" м³/с")
        form.addRow("Средний расход Qср:", self.eco_Qmean)

        self.eco_region = QComboBox()
        for k, v in SEASONAL_TESSMANN_PARAMS.items():
            self.eco_region.addItem(v['name'], k)
        self.eco_region.setCurrentIndex(1)
        form.addRow("Тип региона:", self.eco_region)

        lay.addWidget(grp)

        btn = QPushButton("Рассчитать экологический сток")
        btn.setStyleSheet("QPushButton { background: #2E7D32; color: white; font-weight: bold; }")
        btn.clicked.connect(self.calculate_eco)
        lay.addWidget(btn)

        self.eco_figure = Figure(figsize=(10, 4))
        self.eco_canvas = FigureCanvas(self.eco_figure)

        self.eco_table = QTableWidget()
        auto_resize_table(self.eco_table)

        eco_splitter = QSplitter(Qt.Orientation.Vertical)
        eco_splitter.addWidget(self.eco_canvas)
        eco_splitter.addWidget(self.eco_table)
        eco_splitter.setStretchFactor(0, 3)
        eco_splitter.setStretchFactor(1, 2)
        eco_splitter.setSizes([240, 200])
        lay.addWidget(eco_splitter)

        return w

    def _create_baseflow_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        btn_row = QHBoxLayout()
        btn = QPushButton("Загрузить суточные данные")
        btn.clicked.connect(self.load_baseflow_data)
        btn_row.addWidget(btn)
        btn_manual = QPushButton("Ввести вручную")
        btn_manual.setStyleSheet("QPushButton { background: #FF9800; color: white; }")
        btn_manual.clicked.connect(self.manual_baseflow)
        btn_row.addWidget(btn_manual)
        lay.addLayout(btn_row)

        self.bf_figure = Figure(figsize=(10, 4))
        self.bf_canvas = FigureCanvas(self.bf_figure)

        self.bf_result = QTextEdit()
        self.bf_result.setReadOnly(True)

        bf_splitter = QSplitter(Qt.Orientation.Vertical)
        bf_splitter.addWidget(self.bf_canvas)
        bf_splitter.addWidget(self.bf_result)
        bf_splitter.setStretchFactor(0, 3)
        bf_splitter.setStretchFactor(1, 1)
        bf_splitter.setSizes([260, 140])
        lay.addWidget(bf_splitter)

        return w

    def _create_spectral_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        btn = QPushButton("Загрузить данные для спектрального анализа")
        btn.setStyleSheet("QPushButton { background: #6A1B9A; color: white; }")
        btn.clicked.connect(self.load_spectral_data)
        lay.addWidget(btn)

        self.sp_figure = Figure(figsize=(10, 5))
        self.sp_canvas = FigureCanvas(self.sp_figure)

        self.sp_result = QTextEdit()
        self.sp_result.setReadOnly(True)

        sp_splitter = QSplitter(Qt.Orientation.Vertical)
        sp_splitter.addWidget(self.sp_canvas)
        sp_splitter.addWidget(self.sp_result)
        sp_splitter.setStretchFactor(0, 3)
        sp_splitter.setStretchFactor(1, 1)
        sp_splitter.setSizes([280, 140])
        lay.addWidget(sp_splitter)

        return w

    def _create_drought_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры")
        form = QFormLayout(grp)

        self.dr_scale = QSpinBox()
        self.dr_scale.setRange(1, 24)
        self.dr_scale.setValue(12)
        self.dr_scale.setSuffix(" мес.")
        form.addRow("Масштаб SPI:", self.dr_scale)

        lay.addWidget(grp)

        btn_row = QHBoxLayout()
        btn = QPushButton("Загрузить месячные осадки")
        btn.clicked.connect(self.load_drought_data)
        btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        self.dr_figure = Figure(figsize=(10, 4))
        self.dr_canvas = FigureCanvas(self.dr_figure)

        self.dr_result = QTextEdit()
        self.dr_result.setReadOnly(True)

        dr_splitter = QSplitter(Qt.Orientation.Vertical)
        dr_splitter.addWidget(self.dr_canvas)
        dr_splitter.addWidget(self.dr_result)
        dr_splitter.setStretchFactor(0, 3)
        dr_splitter.setStretchFactor(1, 1)
        dr_splitter.setSizes([260, 140])
        lay.addWidget(dr_splitter)

        return w

    def calculate_eco(self):
        Qmean = self.eco_Qmean.value()
        region = self.eco_region.currentData()

        result = tessmann_seasonal(Qmean, region)

        months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                  'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        Q_eco = result['Q_eco_monthly']

        self.eco_figure.clear()
        ax = self.eco_figure.add_subplot(111)
        x = range(12)
        ax.bar(x, Q_eco, color='#66BB6A', alpha=0.7, label='Экологический сток')
        ax.axhline(y=Qmean * 0.10, color='#F44336', linestyle='--', label='10% от Qср (мин.)')
        ax.axhline(y=Qmean * 0.30, color='#FF9800', linestyle='--', label='30% от Qср (опт.)')
        ax.set_xticks(x)
        ax.set_xticklabels(months)
        ax.set_ylabel("Расход, м³/с")
        ax.set_title(f"Сезонный Тессман — {result['region']}")
        ax.legend()
        ax.grid(True, alpha=0.5)
        self.eco_figure.tight_layout()
        self.eco_canvas.draw()

        table = result['monthly_table']
        self.eco_table.setColumnCount(4)
        self.eco_table.setHorizontalHeaderLabels(['Месяц', 'Q_ср', 'α', 'Q_эколог'])
        self.eco_table.setRowCount(12)
        for i in range(12):
            self.eco_table.setItem(i, 0, QTableWidgetItem(str(table.iloc[i]['Месяц'])))
            self.eco_table.setItem(i, 1, QTableWidgetItem(str(table.iloc[i]['Q_ср_месяц'])))
            self.eco_table.setItem(i, 2, QTableWidgetItem(str(table.iloc[i]['α_i'])))
            self.eco_table.setItem(i, 3, QTableWidgetItem(str(table.iloc[i]['Q_эколог'])))

    def load_baseflow_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "", "", "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        try:
            import pandas as pd
            df = read_work_sheet(path, ["Работа10", "Экология", "Базовый"])
            if df.empty:
                df = pd.read_csv(path) if path.endswith('.csv') else pd.read_excel(path)
            col = numeric_column(df, prefer_names=["базовый", "value", "q"])
            if col is not None:
                self._data = col.values
            else:
                self._data = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().values
            self._plot_baseflow()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", str(e))

    def manual_baseflow(self):
        from PyQt6.QtWidgets import QPlainTextEdit, QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Ввод данных")
        dlg.setMinimumSize(350, 250)
        lay = QVBoxLayout(dlg)
        text = QPlainTextEdit()
        lay.addWidget(text)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = [float(p.strip()) for line in text.toPlainText().strip().split('\n')
                for p in line.replace(';', ',').split(',') if p.strip()]
        if len(vals) >= 10:
            self._data = np.array(vals)
            self._plot_baseflow()

    def _plot_baseflow(self):
        if self._data is None or len(self._data) < 10:
            return

        bf_result = baseflow_digital_filter(self._data)
        bf = np.array(bf_result['baseflow'])
        sf = np.array(bf_result['surface_flow'])
        stats = baseflow_statistics(self._data, bf)

        self.bf_figure.clear()
        ax = self.bf_figure.add_subplot(111)
        ax.fill_between(range(len(self._data)), bf, alpha=0.4, color='#42A5F5', label='Базовый сток')
        ax.fill_between(range(len(self._data)), bf, self._data, alpha=0.3, color='#EF5350', label='Поверхностный сток')
        ax.plot(self._data, color='#1565C0', linewidth=1, alpha=0.7, label='Общий сток')
        ax.set_xlabel("День")
        ax.set_ylabel("Расход, м³/с")
        ax.set_title("Разделение стока на базовый и поверхностный")
        ax.legend()
        ax.grid(True, alpha=0.5)
        self.bf_canvas.draw()

        self.bf_result.clear()
        self.bf_result.append(f"Доля базового стока: {stats['bf_ratio'] * 100:.1f}%")
        self.bf_result.append(f"Средний базовый: {stats['bf_mean_m3_s']:.2f} м³/с | Мин: {stats['bf_min_m3_s']:.2f}")

    def load_spectral_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "", "", "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        try:
            import pandas as pd
            df = read_work_sheet(path, ["Работа10", "Экология", "Базовый"])
            if df.empty:
                df = pd.read_csv(path) if path.endswith('.csv') else pd.read_excel(path)
            col = numeric_column(df, prefer_names=["базовый", "сток", "value", "q"])
            data = col.values if col is not None else pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().values
            self._analyze_spectral(data)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", str(e))

    def _analyze_spectral(self, data):
        spectrum = power_spectrum(data)
        hurst = hurst_exponent(data)
        periodicity = find_periodicity(data)

        self.sp_figure.clear()
        ax1 = self.sp_figure.add_subplot(121)
        if spectrum['power_density']:
            ax1.plot(spectrum['periods_years'], spectrum['power_density'],
                     color='#6A1B9A', linewidth=1.5)
            ax1.set_xlabel("Период, лет")
            ax1.set_ylabel("Мощность")
            ax1.set_title("Энергетический спектр")
            ax1.set_xscale('log')
            ax1.grid(True, alpha=0.5)

        ax2 = self.sp_figure.add_subplot(122)
        periods = [p['period_years'] for p in periodicity['dominant_periods']] if periodicity['dominant_periods'] else []
        powers = [p['power'] for p in periodicity['dominant_periods']] if periodicity['dominant_periods'] else []
        if periods:
            ax2.bar(range(len(periods)), powers, color='#1565C0')
            ax2.set_xticks(range(len(periods)))
            ax2.set_xticklabels([f"{p:.1f} л" for p in periods], rotation=45)
            ax2.set_ylabel("Мощность")
            ax2.set_title("Доминирующие периоды")
        self.sp_figure.tight_layout()
        self.sp_canvas.draw()

        self.sp_result.clear()
        self.sp_result.append(f"Экспонента Хёрста: H = {hurst['H']} — {hurst['confidence']}")
        if periodicity['dominant_periods']:
            for p in periodicity['dominant_periods'][:3]:
                self.sp_result.append(f"Период: {p['period_years']} лет (мощность: {p['power']:.4f})")

    def load_drought_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "", "", "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        try:
            import pandas as pd
            df = read_work_sheet(path, ["Работа10", "Экология", "Базовый"])
            if df.empty:
                df = pd.read_csv(path) if path.endswith('.csv') else pd.read_excel(path)
            col = numeric_column(df, prefer_names=["базовый", "сток", "value", "q"])
            P = col.values if col is not None else pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().values
            scale = self.dr_scale.value()
            result = spi_index(P, scale)
            self._plot_drought(result, scale)
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", str(e))

    def _plot_drought(self, result, scale):
        spi = np.array(result['spi_values'])
        n = len(spi)

        self.dr_figure.clear()
        ax = self.dr_figure.add_subplot(111)
        colors = ['#F44336' if s < -1 else '#FF9800' if s < -0.5 else '#42A5F5' if s > 1 else '#A5D6A7' for s in spi]
        ax.bar(range(n), spi, color=colors, alpha=0.7)
        ax.axhline(y=-1, color='#F44336', linestyle='--', alpha=0.5)
        ax.axhline(y=1, color='#1565C0', linestyle='--', alpha=0.5)
        ax.axhline(y=0, color='black', linewidth=0.5)
        ax.set_xlabel("Месяц")
        ax.set_ylabel("SPI")
        ax.set_title(f"Стандартный индекс осадков (SPI-{scale})")
        ax.grid(True, alpha=0.5)
        self.dr_figure.tight_layout()
        self.dr_canvas.draw()

        freq = drought_frequency(spi)
        self.dr_result.clear()
        self.dr_result.append(f"Засух: {freq['n_droughts']} | Средняя длительность: {freq['mean_duration_months']} мес.")
        self.dr_result.append(f"Макс. тяжесть: {freq['max_severity']} | Без засух: {freq['drought_free_percent']}%")

    def set_data(self, daily_df=None, values=None):
        """Приём данных из единого загрузчика."""
        if values is not None:
            self._data = np.asarray(values, dtype=float)
        elif daily_df is not None:
            col = numeric_column(daily_df, prefer_names=["базовый", "сток", "value", "q"])
            if col is not None:
                self._data = col.values
            elif len(daily_df.columns) >= 2:
                self._data = pd.to_numeric(daily_df.iloc[:, 1], errors='coerce').dropna().values
        if self._data is not None and len(self._data) >= 10:
            if hasattr(self, 'bf_result') and hasattr(self, '_plot_baseflow'):
                self.bf_result.clear()
                self.bf_result.append(f"Загружено из шаблона: n={len(self._data)}")
                self._plot_baseflow()

    def set_qsr(self, q_mean=None):
        """Авто-заполнение Qср из Work1."""
        if q_mean is not None and hasattr(self, 'eco_Qmean'):
            self.eco_Qmean.setValue(float(q_mean))
