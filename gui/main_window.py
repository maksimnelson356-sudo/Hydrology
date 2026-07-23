"""
gui/main_window.py
ГидроСтатистика 2026 — полная версия с таблицами Крицкого-Менкеля
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                             QVBoxLayout, QWidget, QLabel, QTableWidget, 
                             QTableWidgetItem, QFileDialog, QMessageBox,
                             QTabWidget, QStatusBar, QComboBox, QHBoxLayout,
                             QTextEdit, QDialog, QRadioButton, QButtonGroup, QDialogButtonBox,
                             QInputDialog, QGroupBox, QFormLayout, QLineEdit,
                             QPlainTextEdit, QSplitter, QStackedWidget, QListWidget, QListWidgetItem, QAbstractItemView)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QAction, QIcon, QFont
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from scipy import stats

from core.stats.data_loader import load_hydrological_data, get_series_by_post, get_basic_stats
from core.stats.frequency import calculate_frequency_curve, fit_pearson3
from core.stats.missing_data import fill_missing_interpolation, detect_missing
from core.stats.trends import full_trend_analysis
from core.stats.gts_integration import build_gts_frequency_curve, gts_summary_table
from core.stats.composite_curves import compute_composite_curve, find_change_point
from core.stats.series_extension import full_extension_workflow
from core.stats.report_export import generate_txt_report, generate_excel_report
from core.gts_reference import GTSClass


class ManualInputDialog(QDialog):
    """Диалог ручного ввода данных для быстрых расчётов."""

    def __init__(self, parent=None, current_post=None, current_values=None, current_years=None):
        super().__init__(parent)
        self.setWindowTitle("Ручной ввод данных")
        self.setMinimumSize(500, 500)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Введите данные (каждое значение на новой строке или через запятую/точку с запятой):"))

        self.edit_post = QLineEdit(current_post or "Пост 1")
        post_form = QFormLayout()
        post_form.addRow("Название поста:", self.edit_post)
        layout.addLayout(post_form)

        mode_layout = QHBoxLayout()
        self.radio_values_only = QRadioButton("Только значения")
        self.radio_years_values = QRadioButton("Год + Значение")
        self.radio_values_only.setChecked(True)
        mode_layout.addWidget(self.radio_values_only)
        mode_layout.addWidget(self.radio_years_values)
        layout.addWidget(QLabel("Режим ввода:"))
        layout.addLayout(mode_layout)

        years_values_widget = QWidget()
        years_values_layout = QHBoxLayout(years_values_widget)
        years_values_layout.setContentsMargins(0, 0, 0, 0)

        years_values_layout.addWidget(QLabel("Годы:"))
        self.edit_years = QPlainTextEdit()
        self.edit_years.setPlaceholderText("1990\n1991\n1992\n...")
        self.edit_years.setMaximumHeight(150)
        years_values_layout.addWidget(self.edit_years)

        self.edit_years_values_widget = years_values_widget
        self.edit_years_values_widget.setVisible(False)

        layout.addWidget(self.edit_years_values_widget)

        values_widget = QWidget()
        values_layout = QHBoxLayout(values_widget)
        values_layout.setContentsMargins(0, 0, 0, 0)

        values_layout.addWidget(QLabel("Значения:"))
        self.edit_values = QPlainTextEdit()
        self.edit_values.setPlaceholderText("120.5\n98.3\n145.7\n...\n\nИли через запятую: 120.5, 98.3, 145.7")
        self.edit_values.setMaximumHeight(150)
        values_layout.addWidget(self.edit_values)

        layout.addWidget(values_widget)

        self.radio_years_values.toggled.connect(self._toggle_mode)

        self.btn_paste = QPushButton("Вставить из буфера (Ctrl+V)")
        self.btn_paste.clicked.connect(self.paste_from_clipboard)
        layout.addWidget(self.btn_paste)

        preview_group = QGroupBox("Предпросмотр")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(120)
        self.preview_table.setColumnCount(2)
        self.preview_table.setHorizontalHeaderLabels(["Год", "Значение"])
        preview_layout.addWidget(self.preview_table)
        layout.addWidget(preview_group)

        self.edit_values.textChanged.connect(self._update_preview)
        self.edit_years.textChanged.connect(self._update_preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_mode(self, checked):
        self.edit_years_values_widget.setVisible(checked)

    def _parse_values(self, text):
        vals = []
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            for part in line.replace(';', ',').split(','):
                part = part.strip()
                if part:
                    try:
                        vals.append(float(part.replace(',', '.')))
                    except ValueError:
                        pass
        return vals

    def _update_preview(self):
        years_text = self.edit_years.toPlainText() if self.radio_years_values.isChecked() else ""
        values_text = self.edit_values.toPlainText()

        values = self._parse_values(values_text)

        if self.radio_years_values.isChecked() and years_text:
            years = self._parse_values(years_text)
            n = min(len(years), len(values))
            self.preview_table.setRowCount(n)
            for i in range(n):
                self.preview_table.setItem(i, 0, QTableWidgetItem(str(int(years[i]) if years[i] == int(years[i]) else years[i])))
                self.preview_table.setItem(i, 1, QTableWidgetItem(f"{values[i]:.4f}"))
        else:
            self.preview_table.setRowCount(len(values))
            for i, v in enumerate(values):
                self.preview_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
                self.preview_table.setItem(i, 1, QTableWidgetItem(f"{v:.4f}"))

    def _validate_and_accept(self):
        values = self._parse_values(self.edit_values.toPlainText())
        if len(values) < 2:
            QMessageBox.warning(self, "Ошибка", "Нужно минимум 2 значения")
            return
        if self.radio_years_values.isChecked():
            years = self._parse_values(self.edit_years.toPlainText())
            if len(years) == 0:
                QMessageBox.warning(self, "Ошибка", "Введите годы")
                return
            if len(years) != len(values):
                QMessageBox.warning(self, "Ошибка",
                    f"Количество лет ({len(years)}) не совпадает с количеством значений ({len(values)})")
                return
        self.accept()

    def paste_from_clipboard(self):
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            if self.radio_years_values.isChecked():
                self.edit_years.setPlainText(text)
            else:
                self.edit_values.setPlainText(text)

    def get_data(self):
        values = self._parse_values(self.edit_values.toPlainText())
        post_name = self.edit_post.text().strip() or "Пост 1"

        if self.radio_years_values.isChecked():
            years = self._parse_values(self.edit_years.toPlainText())
            import pandas as pd
            df = pd.DataFrame({
                'year': [int(y) for y in years],
                'value': values
            })
        else:
            import pandas as pd
            df = pd.DataFrame({
                'year': list(range(1, len(values) + 1)),
                'value': values
            })

        return post_name, df


class CurveSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор интерполяционной кривой")
        self.setFixedSize(340, 320)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Тип кривой:"))
        
        self.curve_group = QButtonGroup(self)
        self.radio_pearson = QRadioButton("Кривая Пирсона III типа")
        self.radio_kritsky = QRadioButton("Кривая Крицкого-Менкеля")
        self.radio_normal = QRadioButton("Нормальное распределение")
        self.radio_empirical = QRadioButton("Интерпол. ломаной линией")
        self.radio_pearson.setChecked(True)
        
        for radio in [self.radio_pearson, self.radio_kritsky, self.radio_normal, self.radio_empirical]:
            self.curve_group.addButton(radio)
            layout.addWidget(radio)
        
        layout.addSpacing(15)
        layout.addWidget(QLabel("Метод расчета Cv и Cs:"))
        self.method_group = QButtonGroup(self)
        self.radio_moments = QRadioButton("моментов")
        self.radio_mle = QRadioButton("наибольшего правдоподобия")
        self.radio_moments.setChecked(True)
        
        self.method_group.addButton(self.radio_moments)
        self.method_group.addButton(self.radio_mle)
        
        layout.addWidget(self.radio_moments)
        layout.addWidget(self.radio_mle)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_selection(self):
        if self.radio_pearson.isChecked():
            curve_type = "pearson3"
        elif self.radio_kritsky.isChecked():
            curve_type = "kritsky_menkel"
        elif self.radio_normal.isChecked():
            curve_type = "normal"
        else:
            curve_type = "empirical"
        method = "moments" if self.radio_moments.isChecked() else "mle"
        return curve_type, method


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ГидроСтатистика 2026")
        self.setGeometry(60, 30, 1600, 950)
        
        icon_path = "icon.ico" if os.path.exists("icon.ico") else "icon.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Готово")
        
        self.df_raw = None
        self.year_col = None
        self.available_posts = []
        self.current_post = None
        self.df = None
        self.curve_type = "pearson3"
        self.calc_method = "moments"
        self.break_year = None
        self.last_quantiles = None
        
        menubar = self.menuBar()
        file_menu = menubar.addMenu("Файл данных")
        file_menu.addAction("Открыть данные...", self.load_data)
        file_menu.addAction("Загрузить единый шаблон...", self.load_unified_template)
        file_menu.addAction("Создать шаблон", self.create_unified_template)
        file_menu.addAction("Сохранить отчёт в Excel...", self.save_report)
        file_menu.addSeparator()
        file_menu.addAction("Выход", self.close)
        
        self.tabs = QStackedWidget()
        self.setCentralWidget(self.tabs)
        
        self.tab_data = QWidget()
        self.setup_data_tab()
        
        self.tab_graph = QWidget()
        self.setup_graph_tab()
        
        self.tab_trend = QWidget()
        self.setup_trend_tab()
        
        self.tab_viz = QWidget()
        self.setup_viz_tab()
        
        self.tab_kritsky = QWidget()
        self.setup_kritsky_tab()
        
        self.tab_params = QWidget()
        self.setup_params_tab()

        # === Вкладки из объединённых проектов ===
        from gui.widget_work1 import Work1Widget
        from gui.widget_work2 import Work2Widget
        from gui.widget_work3 import Work3Widget
        from gui.widget_work4 import Work4Widget
        from gui.widget_work5 import Work5Widget
        from gui.widget_work6 import Work6Widget
        from gui.widget_work7 import Work7Widget
        from gui.widget_work8 import Work8Widget
        from gui.widget_work9 import Work9Widget
        from gui.widget_work10 import Work10Widget

        self.tab_work1 = Work1Widget()
        self.tab_work2 = Work2Widget()
        self.tab_work3 = Work3Widget()
        self.tab_work4 = Work4Widget()
        self.tab_work5 = Work5Widget()
        self.tab_work6 = Work6Widget()
        self.tab_work7 = Work7Widget()
        self.tab_work8 = Work8Widget()
        self.tab_work9 = Work9Widget()
        self.tab_work10 = Work10Widget()

        self._nav_names = [
            "Данные и статистика",
            "Кривая обеспеченности",
            "Анализ трендов",
            "Визуализация",
            "Крицкий-Менкель (ординаты)",
            "Параметры",
            "Норма годового стока",
            "Внутригодовое распределение",
            "Минимальный сток",
            "Максимальный сток",
            "Ледовые явления",
            "Водный баланс",
            "Рацион + IDF + Гидрографы",
            "FDC + Регрессии + Статистика",
            "ППУ + ГВП + Регулирование",
            "Экология + Базовый сток",
        ]
        self._nav_pages = [
            self.tab_data, self.tab_graph, self.tab_trend, self.tab_viz,
            self.tab_kritsky, self.tab_params,
            self.tab_work1, self.tab_work2, self.tab_work3, self.tab_work4,
            self.tab_work5, self.tab_work6, self.tab_work7, self.tab_work8,
            self.tab_work9, self.tab_work10,
        ]
        self._nav_colors = [
            "#1565C0", "#1565C0", "#1565C0", "#1565C0", "#1565C0", "#1565C0",
            "#2E7D32", "#00695C", "#E65100", "#C62828",
            "#4527A0", "#00838F", "#6A1B9A", "#2E7D32",
            "#EF6C00", "#880E4F",
        ]

        self._nav_list = QListWidget()
        self._nav_list.setIconSize(QSize(0, 0))
        self._nav_list.setSpacing(1)
        self._nav_list.setMinimumWidth(240)
        self._nav_list.setMaximumWidth(280)
        self._nav_list.setStyleSheet("""
            QListWidget {
                background: #1A237E;
                border: none;
                outline: none;
                font-size: 11px;
                font-weight: bold;
            }
            QListWidget::item {
                color: #C5CAE9;
                padding: 12px 16px;
                border-left: 4px solid transparent;
                border-bottom: 1px solid #283593;
            }
            QListWidget::item:selected {
                background: #3F51B5;
                color: white;
                border-left: 4px solid #FFD54F;
            }
            QListWidget::item:hover:!selected {
                background: #283593;
                color: #E8EAF6;
            }
        """)

        for i, name in enumerate(self._nav_names):
            item = QListWidgetItem(name)
            item.setSizeHint(QSize(0, 42))
            self._nav_list.addItem(item)
            self.tabs.addWidget(self._nav_pages[i])

        self._nav_list.currentRowChanged.connect(self._switch_page)
        self._nav_list.setCurrentRow(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._nav_list)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 1300])
        self.setCentralWidget(splitter)

    def _switch_page(self, index):
        if 0 <= index < self.tabs.count():
            self.tabs.setCurrentIndex(index)
            self._nav_list.setCurrentRow(index)

    def setup_data_tab(self):
        layout = QVBoxLayout(self.tab_data)

        hint = QLabel("Данные загружаются через меню или вводятся вручную")
        hint.setStyleSheet("color: #666; font-style: italic; padding: 8px; background: #f0f0f0; border-radius: 4px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_manual = QPushButton("✏ Ввести данные вручную")
        btn_manual.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 6px; }")
        btn_manual.clicked.connect(self.open_manual_input)
        layout.addWidget(btn_manual)

        post_layout = QHBoxLayout()
        post_layout.addWidget(QLabel("Пост:"))
        self.combo_post = QComboBox()
        self.combo_post.setMinimumWidth(120)
        self.combo_post.currentTextChanged.connect(self.on_post_changed)
        post_layout.addWidget(self.combo_post)
        post_layout.addStretch()
        
        self.btn_fill = QPushButton("Восстановить пропуски (простое)")
        self.btn_fill.clicked.connect(self.fill_missing_data)
        self.btn_fill.setEnabled(False)
        
        self.btn_fill_corr = QPushButton("Восстановить пропуски (по корреляции)")
        self.btn_fill_corr.clicked.connect(self.fill_missing_with_correlation)
        self.btn_fill_corr.setEnabled(False)
        
        self.btn_homogeneity = QPushButton("Проверить однородность ряда")
        self.btn_homogeneity.clicked.connect(self.check_homogeneity)
        self.btn_homogeneity.setEnabled(False)
        
        self.btn_outliers = QPushButton("Найти выдающиеся значения")
        self.btn_outliers.clicked.connect(self.detect_outliers)
        self.btn_outliers.setEnabled(False)
        
        self.btn_composite = QPushButton("Составная кривая (указать год разрыва)")
        self.btn_composite.clicked.connect(self.set_composite_break)
        self.btn_composite.setEnabled(False)
        
        self.btn_clear_break = QPushButton("Сбросить составную кривую")
        self.btn_clear_break.clicked.connect(self.clear_composite)
        self.btn_clear_break.setEnabled(False)
        
        self.btn_quantiles = QPushButton("Расчётные расходы (Q заданной обеспеченности)")
        self.btn_quantiles.clicked.connect(self.calculate_quantiles)
        self.btn_quantiles.setEnabled(False)

        self.btn_gts_curve = QPushButton("Кривая с точками ГТС")
        self.btn_gts_curve.clicked.connect(self.build_curve_with_gts)
        self.btn_gts_curve.setEnabled(False)

        self.btn_composite_auto = QPushButton("Составная кривая (авто)")
        self.btn_composite_auto.clicked.connect(self.build_composite_curve)
        self.btn_composite_auto.setEnabled(False)

        self.btn_extend = QPushButton("Удлинить ряд по аналогу")
        self.btn_extend.clicked.connect(self.extend_series)
        self.btn_extend.setEnabled(False)
        
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        
        layout.addLayout(post_layout)
        layout.addWidget(self.btn_fill)
        layout.addWidget(self.btn_fill_corr)
        layout.addWidget(self.btn_homogeneity)
        layout.addWidget(self.btn_outliers)
        layout.addWidget(self.btn_composite)
        layout.addWidget(self.btn_clear_break)
        layout.addWidget(self.btn_quantiles)
        layout.addWidget(self.btn_gts_curve)
        layout.addWidget(self.btn_composite_auto)
        layout.addWidget(self.btn_extend)
        layout.addWidget(QLabel("Статистика:"))
        layout.addWidget(self.table)
    
    def setup_graph_tab(self):
        layout = QVBoxLayout(self.tab_graph)
        
        btn_layout = QHBoxLayout()
        self.btn_select_curve = QPushButton("Выбор кривой")
        self.btn_select_curve.clicked.connect(self.open_curve_dialog)
        self.btn_calc = QPushButton("Построить кривую обеспеченности")
        self.btn_calc.clicked.connect(self.calculate_and_plot)
        self.btn_calc.setEnabled(False)
        self.btn_save_plot = QPushButton("Сохранить график как картинку")
        self.btn_save_plot.clicked.connect(self.save_plot_as_image)
        self.btn_save_plot.setEnabled(False)
        
        btn_layout.addWidget(self.btn_select_curve)
        btn_layout.addWidget(self.btn_calc)
        btn_layout.addWidget(self.btn_save_plot)
        btn_layout.addStretch()
        
        self.figure = plt.figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        
        layout.addLayout(btn_layout)
        layout.addWidget(self.canvas)
    
    def setup_trend_tab(self):
        layout = QVBoxLayout(self.tab_trend)
        self.btn_trend = QPushButton("Выполнить анализ тренда")
        self.btn_trend.clicked.connect(self.run_trend_analysis)
        self.btn_trend.setEnabled(False)
        
        self.trend_table = QTableWidget()
        self.trend_table.setColumnCount(2)
        self.trend_table.setHorizontalHeaderLabels(["Показатель", "Значение"])
        
        self.trend_text = QTextEdit()
        self.trend_text.setReadOnly(True)
        self.trend_text.setMaximumHeight(80)
        
        self.trend_figure = plt.figure(figsize=(10, 5))
        self.trend_canvas = FigureCanvas(self.trend_figure)
        
        layout.addWidget(self.btn_trend)
        layout.addWidget(QLabel("Результаты анализа тренда:"))
        layout.addWidget(self.trend_table)
        layout.addWidget(QLabel("Интерпретация:"))
        layout.addWidget(self.trend_text)
        layout.addWidget(self.trend_canvas)
    
    def setup_viz_tab(self):
        layout = QVBoxLayout(self.tab_viz)
        
        btn_layout = QHBoxLayout()
        self.btn_plot_series = QPushButton("Временной ряд")
        self.btn_plot_series.clicked.connect(self.plot_time_series)
        self.btn_plot_hist = QPushButton("Гистограмма")
        self.btn_plot_hist.clicked.connect(self.plot_histogram)
        self.btn_plot_box = QPushButton("Ящик с усами")
        self.btn_plot_box.clicked.connect(self.plot_boxplot)
        self.btn_plot_corr = QPushButton("Корреляция постов")
        self.btn_plot_corr.clicked.connect(self.plot_correlation)
        
        btn_layout.addWidget(self.btn_plot_series)
        btn_layout.addWidget(self.btn_plot_hist)
        btn_layout.addWidget(self.btn_plot_box)
        btn_layout.addWidget(self.btn_plot_corr)
        btn_layout.addStretch()
        
        self.viz_figure = plt.figure(figsize=(10, 6))
        self.viz_canvas = FigureCanvas(self.viz_figure)
        
        layout.addLayout(btn_layout)
        layout.addWidget(self.viz_canvas)
    
    def setup_kritsky_tab(self):
        layout = QVBoxLayout(self.tab_kritsky)
        
        title = QLabel("Ординаты кривых трёхпараметрического гамма-распределения\nС.Н. Крицкого и М.Ф. Менкеля")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        form_group = QGroupBox("Параметры ряда")
        form = QFormLayout(form_group)
        
        self.edit_cs_cv = QLineEdit("1.0")
        self.edit_cv = QLineEdit("0.5")
        
        form.addRow("Cs/Cv — отношение коэффициентов асимметрии к вариации:", self.edit_cs_cv)
        form.addRow("Cv — коэффициент вариации:", self.edit_cv)
        
        btn_calc_km = QPushButton("Показать результат")
        btn_calc_km.clicked.connect(self.calculate_kritsky_ordinates)
        
        layout.addWidget(form_group)
        layout.addWidget(btn_calc_km)
        
        self.km_table = QTableWidget()
        self.km_table.setColumnCount(2)
        self.km_table.setHorizontalHeaderLabels(["Обеспеченность, %", "Ординаты кривой распределения"])
        layout.addWidget(self.km_table)
    
    def setup_params_tab(self):
        layout = QVBoxLayout(self.tab_params)
        group = QGroupBox("Применение связи при продлении данных")
        form = QFormLayout(group)
        
        self.edit_ncr = QLineEdit("12")
        self.edit_ro = QLineEdit("0.70")
        self.edit_ro_sigma = QLineEdit("2.0")
        self.edit_ki_sigma = QLineEdit("2.0")
        self.edit_yi_sigma = QLineEdit("0.2")
        
        form.addRow("Nср >", self.edit_ncr)
        form.addRow("Ro >", self.edit_ro)
        form.addRow("Ro / σRo >", self.edit_ro_sigma)
        form.addRow("ki / σki >", self.edit_ki_sigma)
        form.addRow("Yi / σ >", self.edit_yi_sigma)
        
        btn_apply = QPushButton("Применить параметры")
        btn_apply.clicked.connect(self.apply_parameters)
        
        layout.addWidget(group)
        layout.addWidget(btn_apply)
        layout.addStretch()
    
    def plot_time_series(self):
        if self.df is None:
            QMessageBox.warning(self, "Нет данных", "Сначала загрузите данные")
            return
        try:
            self.viz_figure.clear()
            ax = self.viz_figure.add_subplot(111)
            years = self.df['year'].values
            values = self.df['value'].values
            ax.plot(years, values, 'o-', color='#1f77b4', markersize=4)
            ax.set_title(f"Временной ряд — Пост {self.current_post}")
            ax.set_xlabel("Год")
            ax.set_ylabel("Q")
            ax.grid(True, alpha=0.3)
            self.viz_canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def plot_histogram(self):
        if self.df is None:
            QMessageBox.warning(self, "Нет данных", "Сначала загрузите данные")
            return
        try:
            self.viz_figure.clear()
            ax = self.viz_figure.add_subplot(111)
            values = self.df['value'].dropna().values
            ax.hist(values, bins=15, color='#1f77b4', edgecolor='black', alpha=0.7)
            ax.set_title(f"Гистограмма — Пост {self.current_post}")
            ax.set_xlabel("Q")
            ax.set_ylabel("Частота")
            ax.grid(True, alpha=0.3)
            self.viz_canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def plot_boxplot(self):
        if self.df is None:
            QMessageBox.warning(self, "Нет данных", "Сначала загрузите данные")
            return
        try:
            self.viz_figure.clear()
            ax = self.viz_figure.add_subplot(111)
            values = self.df['value'].dropna().values
            ax.boxplot(values, orientation='vertical', patch_artist=True,
                       boxprops=dict(facecolor='#1f77b4', color='black'),
                       medianprops=dict(color='red'))
            ax.set_title(f"Ящик с усами — Пост {self.current_post}")
            ax.set_ylabel("Q")
            ax.grid(True, alpha=0.3)
            self.viz_canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def plot_correlation(self):
        if self.df_raw is None or len(self.available_posts) < 2:
            QMessageBox.warning(self, "Недостаточно данных", "Нужно минимум 2 поста")
            return
        try:
            self.viz_figure.clear()
            ax = self.viz_figure.add_subplot(111)
            
            corr = self.df_raw[self.available_posts].corr()
            im = ax.imshow(corr, cmap='coolwarm', vmin=-1, vmax=1)
            ax.set_xticks(range(len(self.available_posts)))
            ax.set_yticks(range(len(self.available_posts)))
            ax.set_xticklabels(self.available_posts, rotation=45, ha='right')
            ax.set_yticklabels(self.available_posts)
            
            for i in range(len(self.available_posts)):
                for j in range(len(self.available_posts)):
                    ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha='center', va='center', color='black')
            
            self.viz_figure.colorbar(im, ax=ax)
            ax.set_title("Корреляционная матрица постов")
            self.viz_canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def calculate_kritsky_ordinates(self):
        try:
            from core.stats.kritsky_tables import get_ordinates, PROBS
            
            cs_cv = float(self.edit_cs_cv.text().replace(',', '.'))
            cv = float(self.edit_cv.text().replace(',', '.'))
            
            if cv <= 0:
                QMessageBox.warning(self, "Ошибка", "Cv должен быть > 0")
                return
            
            ordinates = get_ordinates(cs_cv, cv)
            
            self.km_table.setRowCount(len(PROBS))
            for i, (p, k) in enumerate(zip(PROBS * 100, ordinates)):
                self.km_table.setItem(i, 0, QTableWidgetItem(f"{p:.3f}"))
                val = f"{k:.3f}" if not np.isnan(k) and k > 0 else "—"
                self.km_table.setItem(i, 1, QTableWidgetItem(val))
            
            self.statusBar.showMessage(f"Ординаты (табличные) рассчитаны (Cs/Cv={cs_cv:.2f}, Cv={cv:.2f})")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось рассчитать:\n{str(e)}")
    
    def open_curve_dialog(self):
        dialog = CurveSelectionDialog(self)
        if dialog.exec():
            self.curve_type, self.calc_method = dialog.get_selection()
            curve_names = {
                "pearson3": "Пирсон III",
                "kritsky_menkel": "Крицкий-Менкель",
                "normal": "Нормальное распределение",
                "empirical": "Интерполяция ломаной"
            }
            self.statusBar.showMessage(f"Выбрана кривая: {curve_names.get(self.curve_type)}")
            if self.df is not None and len(self.df) > 5:
                self.calculate_and_plot()
    
    def set_composite_break(self):
        if self.df is None:
            return
        year, ok = QInputDialog.getInt(self, "Составная кривая", 
            "Введите год разрыва:", value=2000, min=1900, max=2100)
        if ok:
            self.break_year = year
            self.btn_clear_break.setEnabled(True)
            self.statusBar.showMessage(f"Год разрыва: {year}. Постройте кривую.")
            self.calculate_and_plot()
    
    def clear_composite(self):
        self.break_year = None
        self.btn_clear_break.setEnabled(False)
        self.statusBar.showMessage("Составная кривая сброшена")
        if self.df is not None:
            self.calculate_and_plot()
    
    def calculate_quantiles(self):
        if self.df is None or len(self.df) < 5:
            QMessageBox.warning(self, "Мало данных", "Нужно минимум 5 значений")
            return
        try:
            values = self.df['value'].dropna().values
            curve = calculate_frequency_curve(values)
            
            probs = [0.01, 0.03, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
            labels = ['1%', '3%', '5%', '10%', '25%', '50%', '75%', '90%', '95%', '99%']
            
            quantiles = []
            for p, lab in zip(probs, labels):
                idx = np.argmin(np.abs(curve['P_%'].values - p*100))
                q_val = curve['Q'].values[idx]
                quantiles.append((lab, round(q_val, 2)))
            
            self.last_quantiles = quantiles
            
            self.table.setRowCount(len(quantiles) + 1)
            self.table.setItem(0, 0, QTableWidgetItem("Обеспеченность"))
            self.table.setItem(0, 1, QTableWidgetItem("Q, м³/с"))
            
            for i, (lab, q) in enumerate(quantiles):
                self.table.setItem(i+1, 0, QTableWidgetItem(lab))
                self.table.setItem(i+1, 1, QTableWidgetItem(str(q)))
            
            msg = "Расчётные расходы:\n\n"
            for lab, q in quantiles:
                msg += f"{lab:>5} → {q:.2f}\n"
            
            QMessageBox.information(self, "Расчётные расходы", msg)
            self.statusBar.showMessage("Расчётные расходы рассчитаны")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def load_data(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Открыть файл", "", "Excel Files (*.xlsx)")
        if not filepath:
            return
        try:
            self.df_raw, self.year_col, self.available_posts = load_hydrological_data(filepath)
            self.combo_post.clear()
            self.combo_post.addItems(self.available_posts)
            if self.available_posts:
                self.combo_post.setCurrentIndex(0)
                self.on_post_changed(self.available_posts[0])
            
            for btn in [self.btn_fill, self.btn_fill_corr, self.btn_calc, self.btn_trend,
                        self.btn_save_plot, self.btn_homogeneity, self.btn_outliers,
                        self.btn_composite, self.btn_quantiles, self.btn_gts_curve,
                        self.btn_composite_auto, self.btn_extend]:
                btn.setEnabled(True)
            self.statusBar.showMessage(f"Загружено постов: {len(self.available_posts)}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def open_manual_input(self):
        """Открыть диалог ручного ввода данных."""
        dialog = ManualInputDialog(
            self,
            current_post=self.current_post,
        )
        if dialog.exec():
            post_name, df = dialog.get_data()

            self._all_posts = {post_name: df}
            self.available_posts = [post_name]
            self.current_post = post_name
            self.df = df

            self.combo_post.clear()
            self.combo_post.addItems(self.available_posts)

            stats = get_basic_stats(self.df)
            self.table.setRowCount(len(stats))
            for i, (key, value) in enumerate(stats.items()):
                self.table.setItem(i, 0, QTableWidgetItem(str(key)))
                self.table.setItem(i, 1, QTableWidgetItem(str(value)))

            for btn in [self.btn_fill, self.btn_fill_corr, self.btn_calc, self.btn_trend,
                        self.btn_save_plot, self.btn_homogeneity, self.btn_outliers,
                        self.btn_composite, self.btn_quantiles, self.btn_gts_curve,
                        self.btn_composite_auto, self.btn_extend]:
                btn.setEnabled(True)

            self.statusBar.showMessage(f"Введено вручную: {post_name} ({len(df)} значений)")
    
    def on_post_changed(self, post_name):
        if not post_name:
            return
        self.current_post = post_name
        # Если данные загружены из единого шаблона — берём из _all_posts
        if hasattr(self, '_all_posts') and post_name in self._all_posts:
            self.df = self._all_posts[post_name]
        elif self.df_raw is not None:
            self.df = get_series_by_post(self.df_raw, self.year_col, post_name)
        else:
            return

        stats = get_basic_stats(self.df)
        self.table.setRowCount(len(stats))
        for i, (key, value) in enumerate(stats.items()):
            self.table.setItem(i, 0, QTableWidgetItem(str(key)))
            self.table.setItem(i, 1, QTableWidgetItem(str(value)))

        self.statusBar.showMessage(f"Пост {post_name} | Значений: {len(self.df)}")
    
    def fill_missing_with_correlation(self):
        if self.df is None or len(getattr(self, 'available_posts', [])) < 2:
            QMessageBox.warning(self, "Недостаточно данных", "Нужно минимум 2 поста")
            return
        try:
            target_name = self.current_post
            all_posts = getattr(self, '_all_posts', {})
            if not all_posts and self.df_raw is None:
                QMessageBox.warning(self, "Ошибка", "Нет загруженных данных")
                return

            # Собираем единый DataFrame из всех постов
            if all_posts:
                combined = pd.DataFrame()
                for name, df in all_posts.items():
                    s = df.set_index('year')['value'].rename(name)
                    if combined.empty:
                        combined = pd.DataFrame(s)
                    else:
                        combined = combined.join(s, how='outer')
                missing_mask = combined[target_name].isna()
            else:
                combined = self.df_raw
                missing_mask = combined[target_name].isna()

            if not missing_mask.any():
                QMessageBox.information(self, "Информация", "Пропусков нет")
                return

            correlations = {}
            for post in self.available_posts:
                if post == target_name:
                    continue
                vals = combined[[target_name, post]].dropna()
                if len(vals) >= 5:
                    corr = vals.corr().iloc[0, 1]
                    if not np.isnan(corr):
                        correlations[post] = abs(corr)

            if not correlations:
                QMessageBox.warning(self, "Ошибка", "Нет коррелирующих постов")
                return

            best_post = max(correlations, key=correlations.get)
            best_corr = correlations[best_post]

            common = combined[[target_name, best_post]].dropna()
            if len(common) < 5:
                QMessageBox.warning(self, "Мало данных", "Мало пересечений")
                return
            
            slope, intercept, _, _, _ = stats.linregress(common[best_post], common[target_name])
            
            if all_posts:
                missing_idx = combined[missing_mask].index
                predicted = slope * combined.loc[missing_idx, best_post] + intercept
                combined.loc[missing_idx, target_name] = predicted
                # Обновляем конкретный пост в _all_posts
                updated_series = combined[target_name].dropna()
                self._all_posts[target_name] = pd.DataFrame({
                    "year": updated_series.index.astype(int),
                    "value": updated_series.values
                }).reset_index(drop=True)
                self.df = self._all_posts[target_name]
            else:
                missing_idx = self.df_raw[missing_mask].index
                predicted = slope * self.df_raw.loc[missing_idx, best_post] + intercept
                self.df_raw.loc[missing_idx, target_name] = predicted
                self.df = get_series_by_post(self.df_raw, self.year_col, target_name)
            stats_dict = get_basic_stats(self.df)
            self.table.setRowCount(len(stats_dict))
            for i, (key, value) in enumerate(stats_dict.items()):
                self.table.setItem(i, 0, QTableWidgetItem(str(key)))
                self.table.setItem(i, 1, QTableWidgetItem(str(value)))
            
            self.statusBar.showMessage(f"Восстановлено с помощью {best_post} (r={best_corr:.3f})")
            QMessageBox.information(self, "Готово", f"Восстановлено с помощью поста {best_post}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def fill_missing_data(self):
        if self.df is None: return
        try:
            missing_before = detect_missing(self.df)
            self.df = fill_missing_interpolation(self.df, 'value', {})
            missing_after = detect_missing(self.df)
            stats = get_basic_stats(self.df)
            self.table.setRowCount(len(stats))
            for i, (key, value) in enumerate(stats.items()):
                self.table.setItem(i, 0, QTableWidgetItem(str(key)))
                self.table.setItem(i, 1, QTableWidgetItem(str(value)))
            QMessageBox.information(self, "Готово", f"Пропусков было: {missing_before} → стало: {missing_after}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def check_homogeneity(self):
        if self.df is None or len(self.df) < 20:
            QMessageBox.warning(self, "Мало данных", "Для проверки однородности нужно минимум 20 значений")
            return
        try:
            values = self.df['value'].values
            n = len(values)
            half = n // 2
            part1 = values[:half]
            part2 = values[half:]
            
            t_stat, t_p = stats.ttest_ind(part1, part2)
            f_stat = np.var(part1, ddof=1) / np.var(part2, ddof=1)
            f_p = 1 - stats.f.cdf(f_stat, len(part1)-1, len(part2)-1)
            
            try:
                w_stat, w_p = stats.ranksums(part1, part2)
            except:
                w_stat, w_p = np.nan, np.nan
            
            try:
                ks_stat, ks_p = stats.ks_2samp(part1, part2)
            except:
                ks_stat, ks_p = np.nan, np.nan
            
            homogeneous = (t_p > 0.05) and (f_p > 0.05) and (w_p > 0.05 or np.isnan(w_p))
            
            result_text = (
                f"Проверка однородности ряда (разделение на две половины)\n\n"
                f"1. t-критерий Стьюдента (средние):\n"
                f"   t = {t_stat:.3f}, p = {t_p:.4f}  → {'однородны' if t_p > 0.05 else 'различаются'}\n\n"
                f"2. F-критерий Фишера (дисперсии):\n"
                f"   F = {f_stat:.3f}, p = {f_p:.4f}  → {'однородны' if f_p > 0.05 else 'различаются'}\n\n"
                f"3. Критерий Wilcoxon (ранги):\n"
                f"   W = {w_stat:.3f}, p = {w_p if np.isnan(w_p) else f'{w_p:.4f}'}  → {'однородны' if w_p > 0.05 else 'различаются' if not np.isnan(w_p) else 'не определено'}\n\n"
                f"4. Критерий Колмогорова-Смирнова:\n"
                f"   KS = {ks_stat:.3f}, p = {ks_p if np.isnan(ks_p) else f'{ks_p:.4f}'}  → {'однородны' if ks_p > 0.05 else 'различаются' if not np.isnan(ks_p) else 'не определено'}\n\n"
            )
            
            if homogeneous:
                result_text += "✅ ОБЩИЙ ВЫВОД: ряд статистически ОДНОРОДЕН"
            else:
                result_text += "⚠️ ОБЩИЙ ВЫВОД: ряд может быть НЕОДНОРОДНЫМ\nРекомендуется проверить причины и рассмотреть составную кривую"
            
            QMessageBox.information(self, "Результат проверки однородности", result_text)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def detect_outliers(self):
        if self.df is None or len(self.df) < 10:
            QMessageBox.warning(self, "Мало данных", "Нужно минимум 10 значений")
            return
        try:
            values = self.df['value'].values
            years = self.df['year'].values if 'year' in self.df.columns else np.arange(len(values))
            
            z_scores = np.abs(stats.zscore(values))
            z_outliers = np.where(z_scores > 3)[0]
            
            q1, q3 = np.percentile(values, [25, 75])
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr
            iqr_outliers = np.where((values < lower) | (values > upper))[0]
            
            outlier_idx = np.unique(np.concatenate([z_outliers, iqr_outliers]))
            
            if len(outlier_idx) == 0:
                QMessageBox.information(self, "Результат", "Выдающихся значений не обнаружено")
                return
            
            self.table.setRowCount(len(outlier_idx) + 1)
            self.table.setItem(0, 0, QTableWidgetItem("Год / Индекс"))
            self.table.setItem(0, 1, QTableWidgetItem("Значение | Z-score"))
            
            for i, idx in enumerate(outlier_idx):
                year_str = str(int(years[idx])) if not np.isnan(years[idx]) else str(idx)
                z_val = z_scores[idx]
                self.table.setItem(i+1, 0, QTableWidgetItem(year_str))
                self.table.setItem(i+1, 1, QTableWidgetItem(f"{values[idx]:.2f} | Z={z_val:.2f}"))
            
            QMessageBox.information(self, "Выдающиеся значения", 
                f"Обнаружено {len(outlier_idx)} выдающихся значений.\n\nРекомендуется проверить их.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def calculate_and_plot(self):
        if self.df is None:
            return
        try:
            values = self.df['value'].dropna().values
            years = self.df['year'].values if 'year' in self.df.columns else None
            if years is not None and len(years) != len(values):
                years = self.df.dropna(subset=['value'])['year'].values
            if len(values) < 5:
                QMessageBox.warning(self, "Мало данных", "Нужно минимум 5 значений")
                return
            
            pearson = fit_pearson3(values)
            mean_q = pearson['mean']
            
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            
            n = len(values)
            sorted_values = np.sort(values)
            p_emp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
            x_emp = stats.norm.ppf(p_emp)
            modular_emp = sorted_values / mean_q
            
            ax.plot(x_emp, modular_emp, 'o', color='#1f77b4', markersize=5, label='Эмпирические точки')
            
            is_composite = self.break_year is not None and years is not None
            
            if is_composite:
                mask1 = years < self.break_year
                mask2 = years >= self.break_year
                
                if mask1.sum() > 5 and mask2.sum() > 5:
                    values1 = values[mask1]
                    values2 = values[mask2]
                    
                    p1 = fit_pearson3(values1)
                    p2 = fit_pearson3(values2)
                    
                    curve1 = calculate_frequency_curve(values1)
                    curve2 = calculate_frequency_curve(values2)
                    
                    modular_theor1 = curve1['Q'].values / p1['mean']
                    modular_theor2 = curve2['Q'].values / p2['mean']
                    
                    p_theor = np.array([0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5,
                                        0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999])
                    x_theor = stats.norm.ppf(p_theor)
                    
                    ax.plot(x_theor[:len(modular_theor1)], modular_theor1[:len(x_theor)], 
                            color='#d62728', linewidth=2.5, label=f'До {self.break_year}')
                    ax.plot(x_theor[:len(modular_theor2)], modular_theor2[:len(x_theor)], 
                            color='#2ca02c', linewidth=2.5, label=f'После {self.break_year}')
                    title = f"Составная кривая (разрыв {self.break_year})"
                    
                    textstr = (f"До {self.break_year}:\n"
                               f"Qср={p1['mean']:.2f}  Cv={p1.get('cv',0):.3f}  Cs={p1.get('cs',0):.3f}\n\n"
                               f"После {self.break_year}:\n"
                               f"Qср={p2['mean']:.2f}  Cv={p2.get('cv',0):.3f}  Cs={p2.get('cs',0):.3f}")
                else:
                    title = "Составная кривая (недостаточно данных в частях)"
                    textstr = f"Qср = {mean_q:.2f}\nCv = {pearson.get('cv', 0):.3f}\nCs = {pearson.get('cs', 0):.3f}"
            else:
                if self.curve_type == "pearson3":
                    curve = calculate_frequency_curve(values)
                    modular_theor = curve['Q'].values / mean_q
                    p_theor = np.array([0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5,
                                        0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999])
                    x_theor = stats.norm.ppf(p_theor)
                    ax.plot(x_theor[:len(modular_theor)], modular_theor[:len(x_theor)], 
                            color='#d62728', linewidth=2.5, label='Пирсон III')
                    title = "Кривая Пирсона III типа"
                elif self.curve_type == "kritsky_menkel":
                    shape, loc, scale = stats.gamma.fit(values, floc=0)
                    p_theor = np.linspace(0.001, 0.999, 200)
                    x_theor = stats.norm.ppf(p_theor)
                    theor_q = stats.gamma.ppf(p_theor, a=shape, loc=loc, scale=scale)
                    modular_theor = theor_q / mean_q
                    ax.plot(x_theor, modular_theor, color='#d62728', linewidth=2.5, label='Крицкий-Менкель')
                    title = "Кривая Крицкого-Менкеля"
                elif self.curve_type == "normal":
                    p_theor = np.linspace(0.001, 0.999, 100)
                    x_theor = stats.norm.ppf(p_theor)
                    theor_values = stats.norm.ppf(p_theor, loc=mean_q, scale=values.std())
                    modular_theor = theor_values / mean_q
                    ax.plot(x_theor, modular_theor, color='#d62728', linewidth=2.5, label='Нормальное распределение')
                    title = "Нормальное распределение"
                else:
                    ax.plot(x_emp, modular_emp, '-', color='#d62728', linewidth=2, label='Интерполяция')
                    title = "Интерполяция ломаной линией"
                
                textstr = f"Qср = {mean_q:.2f}\nCv = {pearson.get('cv', 0):.3f}\nCs = {pearson.get('cs', 0):.3f}"
            
            ax.set_xlabel('Обеспеченность, %', fontsize=11)
            ax.set_ylabel('Модульный коэффициент K = Q / Qср', fontsize=11)
            ax.set_title(f'{title} — Пост {self.current_post}', fontsize=13)
            ax.grid(True, which='both', linestyle='--', alpha=0.6)
            ax.legend(loc='upper right')
            
            prob_ticks = [0.01, 0.05, 0.1, 0.2, 0.5, 0.8, 0.9, 0.95, 0.99]
            prob_labels = ['1%', '5%', '10%', '20%', '50%', '80%', '90%', '95%', '99%']
            ax.set_xticks(stats.norm.ppf(prob_ticks))
            ax.set_xticklabels(prob_labels)
            
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.85)
            ax.text(0.02, -0.07, textstr, transform=ax.transAxes, fontsize=9, verticalalignment='bottom', bbox=props)
            
            self.canvas.draw()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def save_plot_as_image(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить график", "", 
            "PNG Files (*.png);;JPEG Files (*.jpg);;PDF Files (*.pdf)")
        if not filepath:
            return
        try:
            self.figure.savefig(filepath, dpi=300, bbox_inches='tight')
            self.statusBar.showMessage(f"График сохранён: {filepath}")
            QMessageBox.information(self, "Готово", "График успешно сохранён")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def save_report(self):
        if self.df is None:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите данные")
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить отчёт", "", "Excel Files (*.xlsx)")
        if not filepath: return
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                info = {
                    'Параметр': [
                        'Пост', 'Количество значений', 'Выбранная кривая',
                        'Метод расчёта Cv/Cs', 'Год разрыва (составная)',
                        'Дата формирования отчёта'
                    ],
                    'Значение': [
                        self.current_post or '-',
                        len(self.df),
                        self.curve_type,
                        self.calc_method,
                        self.break_year or 'Не задан',
                        pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')
                    ]
                }
                pd.DataFrame(info).to_excel(writer, sheet_name='Информация', index=False)
                
                stats = get_basic_stats(self.df)
                pd.DataFrame(list(stats.items()), columns=['Показатель', 'Значение']).to_excel(
                    writer, sheet_name='Статистика', index=False)
                
                values = self.df['value'].dropna().values
                curve = calculate_frequency_curve(values)
                pd.DataFrame({
                    'Обеспеченность_%': curve['P_%'].round(2),
                    'Q_теоретическое': curve['Q'].round(2)
                }).to_excel(writer, sheet_name='Кривая_обеспеченности', index=False)
                
                if self.last_quantiles:
                    pd.DataFrame(self.last_quantiles, columns=['Обеспеченность', 'Q_м3_с']).to_excel(
                        writer, sheet_name='Расчётные_расходы', index=False)
                else:
                    probs = [0.01, 0.03, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
                    labels = ['1%', '3%', '5%', '10%', '25%', '50%', '75%', '90%', '95%', '99%']
                    quantiles = []
                    for p, lab in zip(probs, labels):
                        idx = np.argmin(np.abs(curve['P_%'].values - p*100))
                        quantiles.append((lab, round(curve['Q'].values[idx], 2)))
                    pd.DataFrame(quantiles, columns=['Обеспеченность', 'Q_м3_с']).to_excel(
                        writer, sheet_name='Расчётные_расходы', index=False)
                
                self.df.to_excel(writer, sheet_name='Исходные_данные', index=False)
            
            self.statusBar.showMessage(f"Отчёт сохранён: {filepath}")
            QMessageBox.information(self, "Готово", "Отчёт успешно сохранён")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def run_trend_analysis(self):
        if self.df is None or len(self.df) < 10:
            QMessageBox.warning(self, "Мало данных", "Для анализа тренда нужно минимум 10 значений")
            return
        try:
            result = full_trend_analysis(self.df)
            linear = result['linear']
            mk = result['mann_kendall']
            sen = result['sen_slope']
            pettitt = result['pettitt']
            
            data = [
                ("Показатель", "Значение"),
                ("Линейный наклон", f"{linear['slope']:.5f}"),
                ("95% ДИ наклона", f"[{linear['slope_ci_lower']:.5f} ; {linear['slope_ci_upper']:.5f}]"),
                ("R²", f"{linear['r_squared']:.4f}"),
                ("p-value (линейный)", f"{linear['p_value']:.4f}"),
                ("Значимый тренд", "Да" if linear['significant'] else "Нет"),
                ("Mann-Kendall Z", f"{mk['z']:.3f}"),
                ("Mann-Kendall p-value", f"{mk['p_value']:.4f}"),
                ("Направление (MK)", f"{mk['trend']} {'(p<0.05)' if mk['significant'] else '(p≥0.05)'}"),
                ("Наклон Сена", f"{sen['slope']:.5f}"),
            ]
            if pettitt:
                data.append(("Pettitt: точка изменения", f"~{pettitt['change_year']} г."))
            
            self.trend_table.setRowCount(len(data))
            for i, (key, value) in enumerate(data):
                self.trend_table.setItem(i, 0, QTableWidgetItem(key))
                self.trend_table.setItem(i, 1, QTableWidgetItem(str(value)))
            
            self.trend_text.setPlainText(result['interpretation'])
            
            self.trend_figure.clear()
            ax = self.trend_figure.add_subplot(111)
            years = result['years']
            values = result['values']
            ax.plot(years, values, 'o', color='#1f77b4', markersize=4, label='Наблюдения')
            
            slope = linear['slope']
            intercept = linear['intercept']
            ax.plot(years, slope * years + intercept, color='#d62728', linewidth=2.5, label=f'Тренд')
            
            ci_lower = linear['slope_ci_lower'] * years + intercept
            ci_upper = linear['slope_ci_upper'] * years + intercept
            ax.fill_between(years, ci_lower, ci_upper, color='#d62728', alpha=0.15, label='95% ДИ')
            
            if pettitt and pettitt['significant']:
                ax.axvline(x=pettitt['change_year'], color='green', linestyle='--', linewidth=2, label='Точка изменения')
            
            ax.set_title(f'Анализ тренда — Пост {self.current_post}')
            ax.legend()
            ax.grid(True, alpha=0.3)
            self.trend_canvas.draw()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
    
    def apply_parameters(self):
        pass

    def build_curve_with_gts(self):
        """Построение кривой с расчётными точками по классу ГТС."""
        if self.df is None or len(self.df) < 5:
            QMessageBox.warning(self, "Мало данных", "Нужно минимум 5 значений")
            return
        try:
            gts_classes = {
                "Класс I (Особо ответственные)": GTSClass.CLASS_I,
                "Класс II (Ответственные)": GTSClass.CLASS_II,
                "Класс III (Средней ответственности)": GTSClass.CLASS_III,
                "Класс IV (Некапитальные)": GTSClass.CLASS_IV,
            }
            from PyQt6.QtWidgets import QInputDialog
            items = list(gts_classes.keys())
            item, ok = QInputDialog.getItem(self, "Класс ГТС", "Выберите класс:", items, 1, False)
            if not ok:
                return

            gts_class = gts_classes[item]
            values = self.df['value'].dropna().values
            mean_q = np.mean(values)

            result = build_gts_frequency_curve(values, gts_class)
            summary = gts_summary_table(gts_class, values)

            self.table.setRowCount(len(summary) + 1)
            self.table.setItem(0, 0, QTableWidgetItem("Параметр"))
            self.table.setItem(0, 1, QTableWidgetItem("Q, м³/с"))
            self.table.setItem(0, 2, QTableWidgetItem("P, %"))
            for i, row in summary.iterrows():
                self.table.setItem(i+1, 0, QTableWidgetItem(row['Параметр']))
                self.table.setItem(i+1, 1, QTableWidgetItem(f"{row['Q_м3_с']:.2f}"))
                self.table.setItem(i+1, 2, QTableWidgetItem(f"{row['Обеспеченность_%']:.3f}"))

            n = len(values)
            sorted_values = np.sort(values)
            p_emp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
            x_emp = stats.norm.ppf(p_emp)
            modular_emp = sorted_values / mean_q

            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.plot(x_emp, modular_emp, 'o', color='#1f77b4', markersize=5, label='Эмпирические точки')

            p_theor = np.array([0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5,
                                0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999])
            x_theor = stats.norm.ppf(p_theor)
            curve = result['curve_df']
            modular_curve = curve['Q'].values / mean_q
            ax.plot(x_theor[:len(modular_curve)], modular_curve[:len(x_theor)],
                    color='#d62728', linewidth=2.5, label=f'Пирсон III ({item})')

            gts_pts = result['gts_points']
            gts_x = []
            gts_y = []
            gts_labels = []
            for key, pt in gts_pts.items():
                px = stats.norm.ppf(pt['P_%'] / 100)
                py = pt['Q'] / mean_q
                gts_x.append(px)
                gts_y.append(py)
                gts_labels.append(pt['label'])
            ax.plot(gts_x, gts_y, 's', color='#FF9800', markersize=10, zorder=5, label='Расчётные точки ГТС')
            for gx, gy, gl in zip(gts_x, gts_y, gts_labels):
                ax.annotate(gl, (gx, gy), textcoords="offset points",
                            xytext=(5, 8), fontsize=7, color='#E65100',
                            bbox=dict(boxstyle='round,pad=0.2', facecolor='#FFF3E0', alpha=0.9))

            ax.set_xlabel('Обеспеченность, %', fontsize=11)
            ax.set_ylabel('Модульный коэффициент K = Q / Qср', fontsize=11)
            ax.set_title(f'{item} — {self.current_post}', fontsize=13)
            ax.grid(True, which='both', linestyle='--', alpha=0.6)
            ax.legend(loc='upper right')

            prob_ticks = [0.01, 0.05, 0.1, 0.2, 0.5, 0.8, 0.9, 0.95, 0.99]
            prob_labels = ['1%', '5%', '10%', '20%', '50%', '80%', '90%', '95%', '99%']
            ax.set_xticks(stats.norm.ppf(prob_ticks))
            ax.set_xticklabels(prob_labels)

            stats_dict = result['stats']
            textstr = f"Qср={stats_dict['mean']:.2f}  Cv={stats_dict['Cv']:.3f}  Cs={stats_dict['Cs']:.3f}  n={stats_dict['n']}"
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.85)
            ax.text(0.02, -0.07, textstr, transform=ax.transAxes, fontsize=9, verticalalignment='bottom', bbox=props)
            self.canvas.draw()

            msg = f"Кривая для {item}\n\n"
            for key, pt in gts_pts.items():
                msg += f"{pt['label']}: P={pt['P_%']:.2f}%, Q={pt['Q']:.2f} м³/с\n"
            QMessageBox.information(self, "ГТС: расчётные точки", msg)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def build_composite_curve(self):
        """Построение составной кривой с автоматическим определением границы."""
        if self.df is None or len(self.df) < 20:
            QMessageBox.warning(self, "Мало данных", "Нужно минимум 20 значений")
            return
        try:
            values = self.df['value'].dropna().values
            years = self.df['year'].values if 'year' in self.df.columns else np.arange(len(values))

            cp = find_change_point(values, years)
            suggested_year = cp.get('change_year') or (int(np.median(years)) if len(years) > 0 else 2000)

            from PyQt6.QtWidgets import QInputDialog
            break_year, ok = QInputDialog.getInt(
                self, "Год разрыва", f"Введите год разрыва (Pettitt: {suggested_year}):",
                suggested_year, int(years.min()), int(years.max()))
            if not ok:
                return

            change = compute_composite_curve(values, years, break_year)
            homo = change['homogeneity_test']
            cp_info = change['change_point']

            self.table.setRowCount(8)
            labels = ['Cv (часть 1)', 'Cs (часть 1)', 'n (часть 1)',
                       'Cv (часть 2)', 'Cs (часть 2)', 'n (часть 2)',
                       'Pettitt p-value', 'Однородность']
            vals = [change['part1_stats']['cv'], change['part1_stats']['cs'], change['n_part1'],
                     change['part2_stats']['cv'], change['part2_stats']['cs'], change['n_part2'],
                     cp_info.get('p_value', '?'),
                     'Да' if homo.get('is_homogeneous') else 'Нет']
            for i, (l, v) in enumerate(zip(labels, vals)):
                self.table.setItem(i, 0, QTableWidgetItem(l))
                self.table.setItem(i, 1, QTableWidgetItem(str(v)))

            mean1 = change['part1_stats']['mean']
            mean2 = change['part2_stats']['mean']
            cv1 = change['part1_stats']['cv']
            cv2 = change['part2_stats']['cv']
            cs1 = change['part1_stats']['cs']
            cs2 = change['part2_stats']['cs']

            n = len(values)
            sorted_values = np.sort(values)
            p_emp = (np.arange(1, n + 1) - 0.375) / (n + 0.25)
            x_emp = stats.norm.ppf(p_emp)
            mean_total = np.mean(values)
            modular_emp = sorted_values / mean_total

            self.figure.clear()
            ax = self.figure.add_subplot(111)
            ax.plot(x_emp, modular_emp, 'o', color='#1f77b4', markersize=4, label='Эмпирические точки', alpha=0.7)

            p_theor = np.array([0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5,
                                0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 0.99, 0.995, 0.999])
            x_theor = stats.norm.ppf(p_theor)

            from core.stats.frequency import pearson3_ppf
            Q1 = pearson3_ppf(p_theor, mean1, cv1, cs1)
            Q2 = pearson3_ppf(p_theor, mean2, cv2, cs2)
            Q_comp = np.minimum(Q1, Q2)

            ax.plot(x_theor, Q1 / mean_total, color='#d62728', linewidth=2,
                    label=f'Часть 1 (до {break_year}): Cv={cv1:.3f}', linestyle='--')
            ax.plot(x_theor, Q2 / mean_total, color='#2ca02c', linewidth=2,
                    label=f'Часть 2 (после {break_year}): Cv={cv2:.3f}', linestyle='--')
            ax.plot(x_theor, Q_comp / mean_total, color='#7B1FA2', linewidth=2.5,
                    label='Составная кривая')

            ax.set_xlabel('Обеспеченность, %', fontsize=11)
            ax.set_ylabel('Модульный коэффициент K = Q / Qср', fontsize=11)
            ax.set_title(f'Составная кривая (разрыв {break_year}) — {self.current_post}', fontsize=13)
            ax.grid(True, which='both', linestyle='--', alpha=0.6)
            ax.legend(loc='upper right')

            prob_ticks = [0.01, 0.05, 0.1, 0.2, 0.5, 0.8, 0.9, 0.95, 0.99]
            prob_labels = ['1%', '5%', '10%', '20%', '50%', '80%', '90%', '95%', '99%']
            ax.set_xticks(stats.norm.ppf(prob_ticks))
            ax.set_xticklabels(prob_labels)

            homo_text = 'Однородны' if homo.get('is_homogeneous') else 'НЕОДНОРОДНЫ'
            textstr = (f"До {break_year}: Qср={mean1:.2f} Cv={cv1:.3f} Cs={cs1:.3f} (n={change['n_part1']})\n"
                       f"После {break_year}: Qср={mean2:.2f} Cv={cv2:.3f} Cs={cs2:.3f} (n={change['n_part2']})\n"
                       f"Pettitt p={cp_info.get('p_value', '?')} | Штрихов: {homo_text}")
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.85)
            ax.text(0.02, -0.10, textstr, transform=ax.transAxes, fontsize=9, verticalalignment='bottom', bbox=props)
            self.canvas.draw()

            msg = "Составная кривая\n\n"
            msg += f"Точка изменения (Pettitt): {cp_info.get('change_year', '?')} г. (p={cp_info.get('p_value', '?')})\n"
            msg += f"Тест Штрихова (Манн-Уитни): p={homo.get('u_p', '?')} → {homo_text}\n\n"
            msg += f"Часть 1 (до {break_year}): Cv={cv1}, Cs={cs1}, n={change['n_part1']}\n"
            msg += f"Часть 2 (после {break_year}): Cv={cv2}, Cs={cs2}, n={change['n_part2']}\n"

            QMessageBox.information(self, "Составная кривая", msg)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def extend_series(self):
        """Удлинение ряда по аналогу."""
        if self.df is None:
            return
        from PyQt6.QtWidgets import QInputDialog
        filepath, _ = QFileDialog.getOpenFileName(self, "Загрузить ряд-аналог", "", "Excel (*.xlsx)")
        if not filepath:
            return
        try:
            df_analog = pd.read_excel(filepath)
            if 'value' in df_analog.columns and 'year' in df_analog.columns:
                Q_analog = df_analog.set_index('year')['value']
            elif len(df_analog.columns) >= 2:
                Q_analog = df_analog.iloc[:, 1]
                Q_analog.index = df_analog.iloc[:, 0].astype(int)
            else:
                QMessageBox.warning(self, "Ошибка", "Файл должен содержать колонки year и value")
                return

            Q_calc = self.df.set_index('year')['value']
            result = full_extension_workflow(Q_calc, Q_analog)

            val = result['validation']
            err = result['error_estimate']
            ext = result['extension_result']

            common_years = sorted(set(Q_calc.index) & set(Q_analog.index))
            mc = Q_calc.loc[common_years].values
            ma = Q_analog.loc[common_years].values

            self.figure.clear()
            ax = self.figure.add_subplot(111)

            ax.scatter(ma, mc, color='#1f77b4', s=40, zorder=5, label=f'Общие годы (n={len(mc)})')

            if 'a' in ext and 'b' in ext:
                x_line = np.linspace(ma.min(), ma.max(), 100)
                y_line = ext['a'] * x_line + ext['b']
                ax.plot(x_line, y_line, 'r-', linewidth=2,
                        label=f'Regression: Q={ext["a"]:.3f}×Qаналог+{ext["b"]:.2f}')
            elif 'k' in ext:
                x_line = np.linspace(ma.min(), ma.max(), 100)
                y_line = ext['k'] * x_line
                ax.plot(x_line, y_line, 'r-', linewidth=2,
                        label=f'Пропорции: Q={ext["k"]:.3f}×Qаналог')

            ax.set_xlabel('Q аналог (м³/с)', fontsize=11)
            ax.set_ylabel('Q расчётный (м³/с)', fontsize=11)
            ax.set_title(f'Корреляция для удлинения — {self.current_post}', fontsize=13)
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.legend(loc='upper left')

            is_sig = "ЗНАЧИМА" if val['is_significant'] else "НЕЗНАЧИМА"
            textstr = (f"R = {val['R']:.3f}, Ro = {val['Ro_crit']:.3f} → {is_sig}\n"
                       f"Качество связи: {val['quality_class']}\n"
                       f"ε до: {err['epsilon_original']:.1f}% → ε после: {err['epsilon_extended']:.1f}%\n"
                       f"Метод: {result['method']} | Надёжность: {err['reliability']}")
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.85)
            ax.text(0.02, -0.12, textstr, transform=ax.transAxes, fontsize=9, verticalalignment='bottom', bbox=props)
            self.canvas.draw()

            msg = f"Удлинение ряда (метод: {result['method']})\n\n"
            msg += f"Общих лет: {val['n_common']}\n"
            msg += f"R = {val['R']:.3f}, Ro = {val['Ro_crit']:.3f} → {is_sig}\n"
            msg += f"Качество связи: {val['quality_class']}\n\n"
            msg += f"ε до: {err['epsilon_original']:.1f}%\n"
            msg += f"ε после: {err['epsilon_extended']:.1f}%\n"
            msg += f"Надёжность: {err['reliability']}\n"

            for w in result.get('warnings', []):
                msg += f"\n⚠ {w}"

            QMessageBox.information(self, "Результат удлинения", msg)

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def create_unified_template(self):
        """Создать единый Excel-шаблон."""
        try:
            from create_unified_template import create_unified_template
            path = create_unified_template()
            QMessageBox.information(self, "Готово", f"Шаблон создан:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def load_unified_template(self):
        """Загрузить единый шаблон и раздать данные по вкладкам."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить единый шаблон", "", "Excel (*.xlsx)"
        )
        if not path:
            return

        try:
            xls = pd.ExcelFile(path)
            loaded = []

            # === Лист "Гидропост" (или первый лист с Год + Q) ===
            sheet_name = None
            for candidate in ["Гидропост", "Лист1"]:
                if candidate in xls.sheet_names:
                    sheet_name = candidate
                    break
            # Если нет ни Гидропост ни Лист1 — берём первый лист
            if sheet_name is None:
                # Пропускаем листы Работа1/2/3/ГТС, ищем первый с данными
                for sn in xls.sheet_names:
                    if not any(kw in sn for kw in ["Работа", "ГТС"]):
                        sheet_name = sn
                        break
                if sheet_name is None:
                    sheet_name = xls.sheet_names[0]

            if sheet_name:
                # Сканируем файл построчно, ищем строку с "Год"
                all_rows = pd.read_excel(xls, sheet_name, header=None).astype(str).values
                year_row_idx = None
                year_col_idx = None
                for r in range(min(50, len(all_rows))):
                    for c in range(min(30, all_rows.shape[1])):
                        v = str(all_rows[r, c]).strip().lower()
                        if v in ["год", "year", "years"]:
                            year_row_idx = r
                            year_col_idx = c
                            break
                    if year_row_idx is not None:
                        break

                if year_row_idx is None:
                    self.statusBar.showMessage("Лист " + sheet_name + ": не найден столбец Год")
                else:
                    df_sheet = pd.read_excel(xls, sheet_name, skiprows=year_row_idx)
                    year_col_name = df_sheet.columns[year_col_idx]

                    # Собираем ВСЕ числовые столбцы (все посты)
                    post_dfs = {}  # name -> DataFrame
                    for c in df_sheet.columns:
                        if c == year_col_name:
                            continue
                        vals = pd.to_numeric(df_sheet[c], errors="coerce").dropna()
                        if len(vals) >= 3:
                            post_dfs[str(c)] = pd.DataFrame({
                                "year": pd.to_numeric(df_sheet[year_col_name], errors="coerce"),
                                "value": pd.to_numeric(df_sheet[c], errors="coerce"),
                            }).dropna(subset=["value"]).reset_index(drop=True)

                    if post_dfs:
                        # Сохраняем все посты, заполняем combo
                        self._all_posts = post_dfs
                        self.available_posts = list(post_dfs.keys())
                        self.combo_post.clear()
                        self.combo_post.addItems(self.available_posts)
                        # Берём первый пост
                        first = self.available_posts[0]
                        self.df = post_dfs[first]
                        self.current_post = first
                        loaded.append(f"Гидропост ({len(post_dfs)} постов)")
                        # Включаем кнопки после загрузки
                        self.on_post_changed(first)
                        self.btn_fill.setEnabled(True)
                        self.btn_fill_corr.setEnabled(True)
                        self.btn_homogeneity.setEnabled(True)
                        self.btn_outliers.setEnabled(True)
                        self.btn_composite.setEnabled(True)
                        self.btn_quantiles.setEnabled(True)
                        self.btn_gts_curve.setEnabled(True)
                        self.btn_composite_auto.setEnabled(True)
                        self.btn_extend.setEnabled(True)
                        self.btn_calc.setEnabled(True)
                        self.btn_save_plot.setEnabled(True)
                        self.btn_trend.setEnabled(True)
                        self.btn_plot_series.setEnabled(True)
                        self.btn_plot_hist.setEnabled(True)
                        self.btn_plot_box.setEnabled(True)
                        self.btn_plot_corr.setEnabled(True)
            # === Лист "Работа1" ===
            if "Работа1" in xls.sheet_names:
                df_r1 = pd.read_excel(xls, "Работа1")
                # Ищем расчётную реку (строка 7-8)
                r1_raw = pd.read_excel(xls, "Работа1", header=None)
                f_calc = None
                name_calc = None
                f_analog = None
                name_analog = None
                calc_years = []
                calc_Q = []
                analog_years = []
                analog_Q = []

                # Сканируем строки
                for i, row in r1_raw.iterrows():
                    val_a = str(row[0]).strip() if pd.notna(row[0]) else ""
                    val_b = row[1] if pd.notna(row[1]) else None
                    if "Площадь F" in val_a and "РАСЧЁТНАЯ" not in val_a and "АНАЛОГ" not in val_a:
                        try:
                            if not f_calc:
                                f_calc = float(val_b)
                            else:
                                f_analog = float(val_b)
                        except: pass
                    elif "Название" in val_a and val_b:
                        if not name_calc:
                            name_calc = str(val_b)
                        else:
                            name_analog = str(val_b)
                    else:
                        try:
                            year = int(val_a)
                            q = float(val_b)
                            if i < 40:
                                calc_years.append(year); calc_Q.append(q)
                            else:
                                analog_years.append(year); analog_Q.append(q)
                        except: pass

                if calc_years:
                    calc_series = pd.Series(calc_Q, index=calc_years)
                    analog_series = pd.Series(analog_Q, index=analog_years) if analog_years else None
                    self.tab_work1.set_data(
                        calc_series=calc_series,
                        analog_series=analog_series,
                        f_calc=f_calc, f_analog=f_analog,
                        name_calc=name_calc, name_analog=name_analog
                    )
                    loaded.append("Работа1")

            # === Лист "Работа2" ===
            if "Работа2" in xls.sheet_names:
                df_r2 = pd.read_excel(xls, "Работа2", skiprows=3)
                if len(df_r2) >= 2:
                    month_map = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,
                                "VII":7,"VIII":8,"IX":9,"X":10,"XI":11,"XII":12}
                    renamed = {}
                    for c in df_r2.columns:
                        cs = str(c).strip().upper()
                        if cs in month_map:
                            renamed[c] = month_map[cs]
                        elif cs == "ГОД":
                            renamed[c] = "год"
                    df_r2 = df_r2.rename(columns=renamed)
                    if "год" in df_r2.columns:
                        df_r2 = df_r2.set_index("год")
                        self.tab_work2.set_data(monthly_df=df_r2)
                        loaded.append("Работа2")

            # === Лист "Работа3" ===
            if "Работа3" in xls.sheet_names:
                df_r3 = pd.read_excel(xls, "Работа3", skiprows=2)
                if len(df_r3) >= 3:
                    years = pd.to_numeric(df_r3.iloc[:, 0], errors='coerce')
                    winter = pd.Series(pd.to_numeric(df_r3.iloc[:, 1], errors='coerce').values, index=years)
                    summer = pd.Series(pd.to_numeric(df_r3.iloc[:, 2], errors='coerce').values, index=years)
                    self.tab_work3.set_data(winter_series=winter, summer_series=summer)
                    loaded.append("Работа3")

            # === Итог ===
            if loaded:
                self.statusBar.showMessage(f"Загружен шаблон: {', '.join(loaded)}")
                msg = "\n".join([f"✅ {s}" for s in loaded])
                QMessageBox.information(self, "Загрузка шаблона", f"Загружены разделы:\n\n{msg}")
            else:
                QMessageBox.warning(self, "Внимание", "Не удалось загрузить данные ни из одного листа")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка загрузки шаблона", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())