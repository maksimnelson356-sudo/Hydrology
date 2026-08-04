"""
gui/widget_work8.py
Работа 8 — Кривая длительностей FDC, регрессии, продвинутая статистика (PyQt6)
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
    QTextEdit, QGroupBox, QFormLayout, QComboBox,
    QTableWidget, QTableWidgetItem, QDoubleSpinBox, QFileDialog,
    QTabWidget, QSplitter
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from scipy import stats

from core.stats.flow_duration import (
    flow_duration_curve, fdc_percentiles, fdc_slope_index,
    flow_regime_classification
)
from core.hydrorash.regional_regressions import (
    mean_annual_runoff, peak_discharge_regression,
    min_winter_runoff_regression, available_regions
)
from core.stats.advanced_frequency import (
    mle_pearson3, lmom_pearson3, fit_gev, fit_weibull3,
    peaks_over_threshold, compare_distributions,
    qq_plot_data, pp_plot_data, weibull_plotting_position,
    fit_logpearson3
)
from core.stats.sheet_reader import read_work_sheet, numeric_column


class Work8Widget(QWidget):
    """Вкладка «Работа 8: FDC и продвинутая статистика»."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #A5D6A7; border-radius: 4px; }
            QTabBar::tab {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #E8F5E9, stop:1 #C8E6C9);
                border: 1px solid #66BB6A; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                padding: 6px 14px; margin-right: 2px; font-size: 11px; font-weight: bold;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #43A047, stop:1 #1B5E20);
                color: white; border: 1px solid #1B5E20; padding-bottom: 8px;
            }
            QTabBar::tab:hover:!selected { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #C8E6C9, stop:1 #A5D6A7); }
        """)
        tabs.addTab(self._create_fdc_tab(), "FDC кривая")
        tabs.addTab(self._create_regressions_tab(), "Регрессии (нелогометр.)")
        tabs.addTab(self._create_advanced_tab(), "Продвинутая статистика")

        layout.addWidget(tabs)

    def _create_fdc_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        btn_row = QHBoxLayout()
        btn = QPushButton("Загрузить данные (столбец value)")
        btn.clicked.connect(self.load_data)
        btn_row.addWidget(btn)

        btn_manual = QPushButton("Ввести вручную")
        btn_manual.setStyleSheet("QPushButton { background: #FF9800; color: white; }")
        btn_manual.clicked.connect(self.manual_input_fdc)
        btn_row.addWidget(btn_manual)
        lay.addLayout(btn_row)

        self.fdc_figure = Figure(figsize=(10, 4))
        self.fdc_canvas = FigureCanvas(self.fdc_figure)

        self.fdc_table = QTableWidget()
        auto_resize_table(self.fdc_table)

        self.fdc_result = QTextEdit()
        self.fdc_result.setReadOnly(True)

        fdc_splitter = QSplitter(Qt.Orientation.Vertical)
        fdc_splitter.addWidget(self.fdc_canvas)
        fdc_splitter.addWidget(self.fdc_table)
        fdc_splitter.addWidget(self.fdc_result)
        fdc_splitter.setStretchFactor(0, 3)
        fdc_splitter.setStretchFactor(1, 1)
        fdc_splitter.setStretchFactor(2, 1)
        fdc_splitter.setSizes([260, 140, 120])
        lay.addWidget(fdc_splitter)

        return w

    def _create_regressions_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        grp = QGroupBox("Параметры")
        form = QFormLayout(grp)

        self.reg_region = QComboBox()
        for r in available_regions():
            self.reg_region.addItem(r['name'], r['key'])
        form.addRow("Регион:", self.reg_region)

        self.reg_F = QDoubleSpinBox()
        self.reg_F.setRange(1, 100000)
        self.reg_F.setValue(500)
        self.reg_F.setSuffix(" км²")
        form.addRow("Площадь бассейна:", self.reg_F)

        self.reg_T = QDoubleSpinBox()
        self.reg_T.setRange(1, 10000)
        self.reg_T.setValue(10)
        self.reg_T.setSuffix(" лет")
        form.addRow("Обеспеченность:", self.reg_T)

        lay.addWidget(grp)

        btn = QPushButton("Рассчитать")
        btn.setStyleSheet("QPushButton { background: #1976D2; color: white; font-weight: bold; }")
        btn.clicked.connect(self.calculate_regressions)
        lay.addWidget(btn)

        self.reg_table = QTableWidget()
        auto_resize_table(self.reg_table)
        lay.addWidget(self.reg_table)

        return w

    def _create_advanced_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        btn = QPushButton("Загрузить данные и сравнить распределения")
        btn.setStyleSheet("QPushButton { background: #6A1B9A; color: white; font-weight: bold; }")
        btn.clicked.connect(self.compare_dists)
        lay.addWidget(btn)

        self.adv_figure = Figure(figsize=(10, 5))
        self.adv_canvas = FigureCanvas(self.adv_figure)

        self.adv_table = QTableWidget()
        auto_resize_table(self.adv_table)

        self.adv_result = QTextEdit()
        self.adv_result.setReadOnly(True)

        adv_splitter = QSplitter(Qt.Orientation.Vertical)
        adv_splitter.addWidget(self.adv_canvas)
        adv_splitter.addWidget(self.adv_table)
        adv_splitter.addWidget(self.adv_result)
        adv_splitter.setStretchFactor(0, 3)
        adv_splitter.setStretchFactor(1, 1)
        adv_splitter.setStretchFactor(2, 1)
        adv_splitter.setSizes([280, 140, 120])
        lay.addWidget(adv_splitter)

        return w

    def load_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить данные", "", "Excel (*.xlsx);;CSV (*.csv)")
        if not path:
            return
        try:
            df = read_work_sheet(path, ["Работа8", "FDC", "Кривая"])
            if df.empty:
                if path.endswith('.csv'):
                    df = pd.read_csv(path)
                else:
                    df = pd.read_excel(path)

            col = numeric_column(df, prefer_names=["q", "расход", "value"])
            if col is not None:
                self._data = col.values
            elif len(df.columns) >= 1:
                self._data = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().values

            self._plot_fdc()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Ошибка", str(e))

    def manual_input_fdc(self):
        from PyQt6.QtWidgets import QPlainTextEdit, QDialog, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Ввод данных для FDC")
        dlg.setMinimumSize(350, 250)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Введите расходы (по одному на строку или через запятую):"))
        text = QPlainTextEdit()
        lay.addWidget(text)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        vals = []
        for line in text.toPlainText().strip().split('\n'):
            for part in line.replace(';', ',').split(','):
                try:
                    vals.append(float(part.strip()))
                except ValueError:
                    pass

        if len(vals) >= 5:
            self._data = np.array(vals)
            self._plot_fdc()

    def _plot_fdc(self):
        if self._data is None or len(self._data) < 5:
            return

        fdc = flow_duration_curve(self._data)
        pcts = fdc_percentiles(self._data)
        slope = fdc_slope_index(self._data)
        regime = flow_regime_classification(self._data)

        self.fdc_figure.clear()
        ax = self.fdc_figure.add_subplot(111)
        ax.plot([p * 100 for p in fdc['P_values']], fdc['Q_values'],
                color='#1565C0', linewidth=2)
        ax.set_xlabel("Обеспеченность превышения, %")
        ax.set_ylabel("Расход, м³/с")
        ax.set_title("Кривая длительностей (FDC)")
        ax.set_xscale('log')
        ax.grid(True, which='both', alpha=0.5)

        for key, val in pcts.items():
            if key in ('Q10', 'Q50', 'Q90'):
                p_key = float(key[1:]) / 100
                ax.axhline(y=val, color='#F44336', linestyle='--', alpha=0.5)
                ax.annotate(f"{key}={val:.1f}", xy=(p_key * 100, val), fontsize=8)
        self.fdc_canvas.draw()

        self.fdc_table.setColumnCount(3)
        self.fdc_table.setHorizontalHeaderLabels(['Показатель', 'Значение', 'Ед.'])
        rows = [(k, str(v), '') for k, v in pcts.items()]
        rows.append(('n_value', str(slope['n_value']), ''))
        rows.append(('Q90/Q10', str(slope['Q90_Q10_ratio']), ''))
        rows.append(('Cv', str(slope['Cv']), ''))
        rows.append(('Режим', regime['description'], ''))
        self.fdc_table.setRowCount(len(rows))
        for i, (a, b, c) in enumerate(rows):
            self.fdc_table.setItem(i, 0, QTableWidgetItem(a))
            self.fdc_table.setItem(i, 1, QTableWidgetItem(b))

        self.fdc_result.setText(f"Режим: {regime['description']}\nn={slope['n_value']}, Cv={slope['Cv']}")

    def calculate_regressions(self):
        region = self.reg_region.currentData()
        F = self.reg_F.value()
        T = self.reg_T.value()

        mean = mean_annual_runoff(F, region)
        peak = peak_discharge_regression(F, T, region)
        min_w = min_winter_runoff_regression(F, region)

        self.reg_table.setColumnCount(3)
        self.reg_table.setHorizontalHeaderLabels(['Параметр', 'Значение', 'Ед.'])
        rows = [
            ('Qср', str(mean['Q_mean_m3_s']), 'м³/с'),
            ('Модуль стока', str(mean['module_l_s_km2']), 'л/с·км²'),
            ('Объём стока', str(mean['volume_km3']), 'км³'),
            (f'Qmax (T={T})', str(peak['Q_peak_m3_s']), 'м³/с'),
            ('Qмин зимний', str(min_w['Q_min_m3_s']), 'м³/с'),
        ]
        self.reg_table.setRowCount(len(rows))
        for i, (a, b, c) in enumerate(rows):
            self.reg_table.setItem(i, 0, QTableWidgetItem(a))
            self.reg_table.setItem(i, 1, QTableWidgetItem(b))
            self.reg_table.setItem(i, 2, QTableWidgetItem(c))

    def compare_dists(self):
        data = None
        if getattr(self, "_data", None) is not None and len(self._data) >= 5:
            data = np.asarray(self._data, dtype=float)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Загрузить данные", "", "Excel (*.xlsx);;CSV (*.csv)")
            if not path:
                return
            try:
                df = read_work_sheet(path, ["Работа8", "FDC", "Кривая"])
                if df.empty:
                    df = pd.read_csv(path) if path.endswith('.csv') else pd.read_excel(path)
                col = numeric_column(df, prefer_names=["q", "расход", "value"])
                if col is not None:
                    data = col.values
                else:
                    data = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna().values
                self._data = data
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.critical(self, "Ошибка", str(e))
                return

        if data is None or len(data) < 5:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Мало данных", "Нужно минимум 5 значений")
            return

        result_df = compare_distributions(data)

        self.adv_table.setColumnCount(len(result_df.columns))
        self.adv_table.setHorizontalHeaderLabels(result_df.columns.tolist())
        self.adv_table.setRowCount(len(result_df))
        for i, row in result_df.iterrows():
            for j, col in enumerate(result_df.columns):
                val = row[col]
                self.adv_table.setItem(i, j, QTableWidgetItem(str(val) if not pd.isna(val) else '—'))

        mle = mle_pearson3(data)
        lmom = lmom_pearson3(data)
        gev = fit_gev(data)

        self.adv_figure.clear()
        ax1 = self.adv_figure.add_subplot(121)
        qq = qq_plot_data(data)
        ax1.plot(qq['theoretical'], qq['empirical'], 'o', markersize=3, color='#1565C0')
        lim = [min(min(qq['theoretical']), min(qq['empirical'])),
               max(max(qq['theoretical']), max(qq['empirical']))]
        ax1.plot(lim, lim, 'r--', linewidth=1)
        ax1.set_xlabel("Теоретические квантили")
        ax1.set_ylabel("Эмпирические квантили")
        ax1.set_title("Q-Q график")
        ax1.grid(True, alpha=0.5)

        ax2 = self.adv_figure.add_subplot(122)
        pp = pp_plot_data(data)
        ax2.plot(pp['theoretical_probs'], pp['empirical_probs'], 'o', markersize=3, color='#388E3C')
        ax2.plot([0, 1], [0, 1], 'r--', linewidth=1)
        ax2.set_xlabel("Теоретическая вероятность")
        ax2.set_ylabel("Эмпирическая вероятность")
        ax2.set_title("P-P график")
        ax2.grid(True, alpha=0.5)
        self.adv_figure.tight_layout()
        self.adv_canvas.draw()

        self.adv_result.clear()
        self.adv_result.append(f"MLE: среднее={mle['mean']:.3f}, Cv={mle['cv']:.3f}, Cs={mle['cs']:.3f} (AIC={mle['aic']:.1f})")
        self.adv_result.append(f"L-моменты: среднее={lmom['mean']:.3f}, Cv={lmom['cv']:.3f}, Cs={lmom['cs']:.3f}")
        self.adv_result.append(f"GEV: ξ={gev['shape_xi']:.4f}, μ={gev['location_mu']:.3f}, σ={gev['scale_sigma']:.3f}")

    def set_data(self, daily_df=None, values=None):
        """Приём данных из единого загрузчика."""
        if values is not None:
            self._data = np.asarray(values, dtype=float)
        elif daily_df is not None:
            col = numeric_column(daily_df, prefer_names=["q", "расход", "value"])
            if col is not None:
                self._data = col.values
            elif len(daily_df.columns) >= 2:
                self._data = pd.to_numeric(daily_df.iloc[:, 1], errors='coerce').dropna().values
        if self._data is not None and len(self._data) >= 5:
            self._plot_fdc()
