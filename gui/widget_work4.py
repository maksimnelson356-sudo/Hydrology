"""
gui/widget_work4.py
Работа 4 — Максимальный сток (паводки) (PyQt6)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QLineEdit, QTableWidget, QTableWidgetItem, QComboBox, QTabWidget,
    QPlainTextEdit, QDialog, QDialogButtonBox
)
from PyQt6.QtGui import QFont
from scipy import stats

from core.hydrorash.max_runoff import (
    extract_max_annual, compute_max_runoff_stats,
    max_runoff_frequency_curve, index_year_method,
    build_rating_curve, discharge_from_level, level_from_discharge
)
from core.stats.frequency import pearson3_ppf


class Work4Widget(QWidget):
    """Вкладка «Работа 4: Максимальный сток (паводки)»."""

    def __init__(self):
        super().__init__()
        self.daily_data = None
        self.max_series = None
        self.rating_params = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("МАКСИМАЛЬНЫЙ СТОК (ПАВОДКИ)")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #C62828;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #90CAF9; border-radius: 4px; background: white; }
            QTabBar::tab {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #E3F2FD, stop:1 #BBDEFB);
                border: 1px solid #64B5F6; border-bottom: none;
                border-top-left-radius: 6px; border-top-right-radius: 6px;
                padding: 6px 14px; margin-right: 2px; font-size: 11px; font-weight: bold;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1E88E5, stop:1 #0D47A1);
                color: white; border: 1px solid #0D47A1; padding-bottom: 8px;
            }
            QTabBar::tab:hover:!selected { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #BBDEFB, stop:1 #90CAF9); }
        """)

        self.tab_calc = QWidget()
        self._setup_calc_tab()
        self.tabs.addTab(self.tab_calc, "Расчёт максимумов")

        self.tab_rating = QWidget()
        self._setup_rating_tab()
        self.tabs.addTab(self.tab_rating, "Кривая Q=f(H)")

        self.tab_index = QWidget()
        self._setup_index_tab()
        self.tabs.addTab(self.tab_index, "Метод индексных годов")

        layout.addWidget(self.tabs)

    def _setup_calc_tab(self):
        layout = QVBoxLayout(self.tab_calc)

        btn_row = QHBoxLayout()
        self.btn_load = QPushButton("Загрузить суточные данные")
        self.btn_load.clicked.connect(self.load_daily_data)
        btn_row.addWidget(self.btn_load)

        self.btn_manual = QPushButton("Ввести вручную (значения за год)")
        self.btn_manual.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; }")
        self.btn_manual.clicked.connect(self.manual_input)
        btn_row.addWidget(self.btn_manual)

        self.combo_period = QComboBox()
        self.combo_period.addItems(["1 сутки", "5 суток", "7 суток", "10 суток"])
        btn_row.addWidget(QLabel("Период:"))
        btn_row.addWidget(self.combo_period)

        self.btn_calc = QPushButton("РАССЧИТАТЬ")
        self.btn_calc.setStyleSheet(
            "QPushButton { background-color: #C62828; color: white; font-weight: bold; padding: 8px; }"
        )
        self.btn_calc.clicked.connect(self.calculate_max)
        btn_row.addWidget(self.btn_calc)

        layout.addLayout(btn_row)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Обеспеченность, %", "Q_max, м³/с", "kp"])
        layout.addWidget(self.table)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setFont(QFont("Consolas", 10))
        self.result_box.setMaximumHeight(120)
        layout.addWidget(self.result_box)

        self.figure = Figure(figsize=(10, 5))
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    def _setup_rating_tab(self):
        layout = QVBoxLayout(self.tab_rating)

        hint = QLabel("Загрузите данные с уровнями и расходами для построения кривой Q=f(H)")
        hint.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        self.btn_load_rating = QPushButton("Загрузить данные H-Q")
        self.btn_load_rating.clicked.connect(self.load_rating_data)
        btn_row.addWidget(self.btn_load_rating)

        self.btn_fit_rating = QPushButton("Построить кривую")
        self.btn_fit_rating.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }"
        )
        self.btn_fit_rating.clicked.connect(self.fit_rating_curve)
        btn_row.addWidget(self.btn_fit_rating)

        layout.addLayout(btn_row)

        self.rating_table = QTableWidget()
        self.rating_table.setColumnCount(4)
        self.rating_table.setHorizontalHeaderLabels(["a", "b", "H0", "R²"])
        self.rating_table.setMaximumHeight(50)
        layout.addWidget(self.rating_table)

        self.rating_result = QTextEdit()
        self.rating_result.setReadOnly(True)
        self.rating_result.setFont(QFont("Consolas", 10))
        self.rating_result.setMaximumHeight(80)
        layout.addWidget(self.rating_result)

        self.rating_figure = Figure(figsize=(10, 4))
        self.rating_canvas = FigureCanvas(self.rating_figure)
        layout.addWidget(self.rating_canvas)

    def _setup_index_tab(self):
        layout = QVBoxLayout(self.tab_index)

        hint = QLabel(
            "Метод индексных годов для безструментных рек\n"
            "(нужны Qmax и Qср на струментном участке)"
        )
        hint.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(hint)

        form = QGroupBox("Параметры")
        form_lay = QFormLayout(form)
        self.edit_gauged_mean = QLineEdit("100")
        self.edit_target_mean = QLineEdit("80")
        form_lay.addRow("Qср струментного участка, м³/с:", self.edit_gauged_mean)
        form_lay.addRow("Qср целевой реки, м³/с:", self.edit_target_mean)
        layout.addWidget(form)

        btn = QPushButton("Рассчитать методом индексных годов")
        btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }"
        )
        btn.clicked.connect(self.calc_index_year)
        layout.addWidget(btn)

        self.index_table = QTableWidget()
        self.index_table.setColumnCount(3)
        self.index_table.setHorizontalHeaderLabels(["Обеспеченность, %", "Kp", "Q_max, м³/с"])
        layout.addWidget(self.index_table)

        self.index_result = QTextEdit()
        self.index_result.setReadOnly(True)
        self.index_result.setFont(QFont("Consolas", 10))
        self.index_result.setMaximumHeight(80)
        layout.addWidget(self.index_result)

    def manual_input(self):
        """Быстрый ввод максимальных значений вручную."""
        from PyQt6.QtWidgets import QPlainTextEdit as QPE

        dlg = QDialog(self)
        dlg.setWindowTitle("Ручной ввод максимальных стоков")
        dlg.setMinimumSize(400, 350)
        lay = QVBoxLayout(dlg)

        lay.addWidget(QLabel("Введите максимальные расходы (по одному на строку или через запятую):"))
        lay.addWidget(QLabel("Или формат: Год, Qmax\n1990, 150.3\n1991, 220.1"))

        text_edit = QPE()
        text_edit.setPlaceholderText("150.3\n220.1\n180.5\n...\n\nИли:\n1990, 150.3\n1991, 220.1\n1992, 180.5")
        lay.addWidget(text_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        lay.addWidget(btn_box)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        text = text_edit.toPlainText().strip()
        if not text:
            return

        values = []
        years = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            parts = line.replace(';', ',').split(',')
            if len(parts) >= 2:
                try:
                    years.append(int(float(parts[0].strip())))
                    values.append(float(parts[1].strip()))
                except ValueError:
                    pass
            else:
                try:
                    values.append(float(parts[0].strip().replace(',', '.')))
                except ValueError:
                    pass

        if len(values) < 3:
            QMessageBox.warning(self, "Ошибка", "Нужно минимум 3 значения")
            return

        if years and len(years) == len(values):
            self.max_series = pd.Series(values, index=years)
        else:
            self.max_series = pd.Series(values)

        params = compute_max_runoff_stats(self.max_series)

        self.result_box.clear()
        self.result_box.append(f"Введено вручную: n={params['n']}")
        self.result_box.append(f"Qср={params['mean']:.2f}  Cv={params['Cv']:.3f}  Cs={params['Cs']:.3f}")
        self.result_box.append(f"ε={params['epsilon']:.1f}%  Надёжность: {params['reliability_class']}")

        curve = max_runoff_frequency_curve(self.max_series)

        self.table.setRowCount(len(curve))
        for i, row in curve.iterrows():
            self.table.setItem(i, 0, QTableWidgetItem(f"{row['P_%']:.3f}"))
            self.table.setItem(i, 1, QTableWidgetItem(f"{row['Q_max']:.2f}"))
            self.table.setItem(i, 2, QTableWidgetItem(f"{row['kp']:.4f}"))

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        p_emp = (np.arange(1, len(self.max_series) + 1) - 0.375) / (len(self.max_series) + 0.25)
        x_emp = stats.norm.ppf(p_emp)
        sorted_max = np.sort(self.max_series.values)
        modular_emp = sorted_max / params['mean']

        ax.plot(x_emp, modular_emp, 'o', color='#C62828', markersize=5, label='Эмпирические')

        p_theor = np.linspace(0.001, 0.999, 200)
        x_theor = stats.norm.ppf(p_theor)
        q_theor = pearson3_ppf(p_theor, params['mean'], params['Cv'], params['Cs'])
        modular_theor = q_theor / params['mean']

        ax.plot(x_theor, modular_theor, color='#1565C0', linewidth=2, label='Пирсон III')

        prob_ticks = [0.01, 0.05, 0.1, 0.2, 0.5, 0.8, 0.9, 0.95, 0.99]
        prob_labels = ['0.1%', '5%', '10%', '20%', '50%', '80%', '90%', '95%', '99%']
        ax.set_xticks(stats.norm.ppf(prob_ticks))
        ax.set_xticklabels(prob_labels)

        ax.set_title('Кривая обеспечённости максимумов')
        ax.set_xlabel('Обеспеченность')
        ax.set_ylabel('K = Qmax / Qср')
        ax.grid(True, which='both', linestyle='--', alpha=0.6)
        ax.legend()
        self.canvas.draw()

    def load_daily_data(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить суточные данные", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            df = pd.read_excel(path)
            col_map = {}
            cols_lower = {c.strip().lower(): c for c in df.columns}
            if 'year' in cols_lower:
                col_map[cols_lower['year']] = 'year'
            if 'q' in cols_lower:
                col_map[cols_lower['q']] = 'value'
            if col_map:
                df = df.rename(columns=col_map)
            self.daily_data = df
            self.result_box.clear()
            self.result_box.append(
                f"Загружено: {len(df)} строк, столбцы: {list(df.columns)[:6]}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def calculate_max(self):
        if self.daily_data is None:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите данные")
            return
        try:
            period_map = {"1 сутки": 1, "5 суток": 5, "7 суток": 7, "10 суток": 10}
            period = period_map[self.combo_period.currentText()]

            self.max_series = extract_max_annual(
                self.daily_data, period_days=period
            )

            params = compute_max_runoff_stats(self.max_series)

            self.result_box.clear()
            self.result_box.append(
                f"Ряд максимальных стоков ({period} сут.): n={params['n']}"
            )
            self.result_box.append(
                f"Qср={params['mean']:.2f}  Cv={params['Cv']:.3f}  Cs={params['Cs']:.3f}"
            )
            self.result_box.append(
                f"ε={params['epsilon']:.1f}%  Надёжность: {params['reliability_class']}"
            )
            for w in params.get("warnings", []):
                self.result_box.append(f"  {w}")

            curve = max_runoff_frequency_curve(self.max_series)

            self.table.setRowCount(len(curve))
            for i, row in curve.iterrows():
                self.table.setItem(i, 0, QTableWidgetItem(f"{row['P_%']:.3f}"))
                self.table.setItem(i, 1, QTableWidgetItem(f"{row['Q_max']:.2f}"))
                self.table.setItem(i, 2, QTableWidgetItem(f"{row['kp']:.4f}"))

            self._plot_frequency_curve(period, params)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _plot_frequency_curve(self, period, params):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        n = len(self.max_series)
        p_emp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
        x_emp = stats.norm.ppf(p_emp)
        sorted_max = np.sort(self.max_series.values)
        modular_emp = sorted_max / params["mean"]

        ax.plot(x_emp, modular_emp, "o", color="#C62828", markersize=5, label="Эмпирические")

        p_theor = np.linspace(0.001, 0.999, 200)
        x_theor = stats.norm.ppf(p_theor)
        q_theor = pearson3_ppf(p_theor, params["mean"], params["Cv"], params["Cs"])
        modular_theor = q_theor / params["mean"]

        ax.plot(x_theor, modular_theor, color="#1565C0", linewidth=2, label="Пирсон III")

        prob_ticks = [0.01, 0.05, 0.1, 0.2, 0.5, 0.8, 0.9, 0.95, 0.99]
        prob_labels = ["0.1%", "5%", "10%", "20%", "50%", "80%", "90%", "95%", "99%"]
        ax.set_xticks(stats.norm.ppf(prob_ticks))
        ax.set_xticklabels(prob_labels)

        ax.set_title(f"Кривая обеспечённости максимумов ({period} сут.)")
        ax.set_xlabel("Обеспеченность")
        ax.set_ylabel("K = Qmax / Qср")
        ax.grid(True, which="both", linestyle="--", alpha=0.6)
        ax.legend()
        self.figure.tight_layout()
        self.canvas.draw()

    def load_rating_data(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить данные H-Q", "", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            df = pd.read_excel(path)
            self._rating_df = df
            self.rating_result.clear()
            self.rating_result.append(
                f"Загружено: {len(df)} строк, столбцы: {list(df.columns)}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def fit_rating_curve(self):
        if not hasattr(self, "_rating_df") or self._rating_df is None:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите данные H-Q")
            return
        try:
            df = self._rating_df
            cols_lower = {c.strip().lower(): c for c in df.columns}
            h_col = cols_lower.get("h") or cols_lower.get("уровень")
            q_col = cols_lower.get("q") or cols_lower.get("расход")
            if h_col is None or q_col is None:
                QMessageBox.warning(
                    self, "Внимание",
                    "Не найдены столбцы H и Q. Нужны столбцы с именами H и Q."
                )
                return

            H = pd.to_numeric(df[h_col], errors="coerce").dropna().values
            Q = pd.to_numeric(df[q_col], errors="coerce").dropna().values
            n = min(len(H), len(Q))
            self.rating_params = build_rating_curve(H[:n], Q[:n])

            self.rating_table.setRowCount(1)
            self.rating_table.setItem(0, 0, QTableWidgetItem(f"{self.rating_params['a']:.6f}"))
            self.rating_table.setItem(0, 1, QTableWidgetItem(f"{self.rating_params['b']:.4f}"))
            self.rating_table.setItem(0, 2, QTableWidgetItem(f"{self.rating_params['H0']:.4f}"))
            self.rating_table.setItem(0, 3, QTableWidgetItem(f"{self.rating_params['R2']:.6f}"))

            self.rating_result.clear()
            self.rating_result.append(self.rating_params["formula"])
            self.rating_result.append(
                f"R² = {self.rating_params['R2']:.6f}"
            )

            self.rating_figure.clear()
            ax = self.rating_figure.add_subplot(111)
            ax.scatter(H[:n], Q[:n], color="#C62828", s=20, label="Данные")

            H_fit = np.linspace(
                self.rating_params["H0"] + 0.01,
                float(np.max(H[:n])) * 1.05,
                200
            )
            Q_fit = np.array([
                discharge_from_level(h, self.rating_params) for h in H_fit
            ])
            ax.plot(H_fit, Q_fit, color="#1565C0", linewidth=2, label="Кривая Q=f(H)")
            ax.set_xlabel("H, м")
            ax.set_ylabel("Q, м³/с")
            ax.set_title("Кривая функционирования Q = f(H)")
            ax.grid(True, alpha=0.3)
            ax.legend()
            self.rating_figure.tight_layout()
            self.rating_canvas.draw()

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def calc_index_year(self):
        if self.max_series is None:
            QMessageBox.warning(
                self, "Внимание", "Сначала рассчитайте максимальные стоки"
            )
            return
        try:
            gauged_mean = float(self.edit_gauged_mean.text())
            target_mean = float(self.edit_target_mean.text())

            curve = index_year_method(self.max_series, gauged_mean, target_mean)

            self.index_table.setRowCount(len(curve))
            for i, row in curve.iterrows():
                self.index_table.setItem(i, 0, QTableWidgetItem(f"{row['P_%']:.3f}"))
                self.index_table.setItem(i, 1, QTableWidgetItem(f"{row['K_p']:.4f}"))
                self.index_table.setItem(i, 2, QTableWidgetItem(f"{row['Q_max']:.2f}"))

            self.index_result.clear()
            self.index_result.append(
                f"Qср струм={gauged_mean}, Qср целев={target_mean}"
            )
            self.index_result.append("Расчёт завершён. Таблица заполнена.")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def set_data(self, daily_df=None):
        """Приём данных из единого загрузчика."""
        if daily_df is not None:
            self.daily_data = daily_df
            self.result_box.append(f"Получены данные: {len(daily_df)} строк")

    def save_report(self):
        if self.max_series is None:
            QMessageBox.warning(self, "Внимание", "Сначала рассчитайте максимумы")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Сохранить", "Отчёт_Работа4.xlsx", "Excel (*.xlsx)"
        )
        if not filepath:
            return
        try:
            with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
                curve = max_runoff_frequency_curve(self.max_series)
                curve.to_excel(writer, sheet_name="Кривая обеспечённости", index=False)

                max_df = pd.DataFrame({
                    "Год": self.max_series.index,
                    "Q_max": self.max_series.values
                })
                max_df.to_excel(writer, sheet_name="Ряд максимумов", index=False)

            QMessageBox.information(self, "Готово", f"Отчёт: {filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
