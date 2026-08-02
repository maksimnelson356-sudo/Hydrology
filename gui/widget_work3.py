"""
gui/widget_work3.py
Работа 3 — Минимальный сток (PyQt6)
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
    QTextEdit, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QSplitter
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from core.hydrorash.minimal_runoff import (
    prepare_minimal_series, compute_minimal_stats,
    calculate_probability_curves
)


class Work3Widget(QWidget):
    """Вкладка «Работа 3: Минимальный сток»."""

    def __init__(self):
        super().__init__()
        self.winter = None
        self.summer = None
        self.minimal_stats = None
        self.probability_curves = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("МИНИМАЛЬНЫЙ СТОК (30-СУТОЧНЫЙ)")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F4E79;")
        layout.addWidget(title)

        row = QHBoxLayout()
        self.btn_load = QPushButton("Загрузить данные")
        self.btn_load.clicked.connect(self.load_data)
        row.addWidget(self.btn_load)

        self.btn_calc = QPushButton("РАССЧИТАТЬ СТАТИСТИКУ")
        self.btn_calc.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }"
        )
        self.btn_calc.clicked.connect(self.calc_stats)
        row.addWidget(self.btn_calc)

        self.btn_save = QPushButton("Сохранить отчёт")
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; }"
        )
        self.btn_save.clicked.connect(self.save_report)
        row.addWidget(self.btn_save)
        layout.addLayout(row)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Сезон", "n", "Qmin", "Cv", "Cs/Cv", "eps,%"])
        auto_resize_table(self.table)
        layout.addWidget(self.table)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setFont(QFont("Consolas", 10))
        layout.addWidget(self.result_box)

        self.figure = Figure(figsize=(12, 4))
        self.canvas = FigureCanvas(self.figure)

        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.result_box)
        self.splitter.addWidget(self.canvas)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([160, 240])
        layout.addWidget(self.splitter)

    def load_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            df = pd.read_excel(path)
            years = pd.to_numeric(df.iloc[:, 0], errors='coerce')
            self.winter = pd.Series(
                pd.to_numeric(df.iloc[:, 1], errors='coerce').values, index=years
            )
            self.summer = pd.Series(
                pd.to_numeric(df.iloc[:, 2], errors='coerce').values, index=years
            )
            self.result_box.append("Загружено")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def calc_stats(self):
        if self.winter is None:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите данные")
            return
        try:
            data = prepare_minimal_series(self.winter, self.summer)
            self.minimal_stats = compute_minimal_stats(data)
            self.probability_curves = calculate_probability_curves(self.minimal_stats)
            cols = ["зима", "лето"]
            self.table.setRowCount(len(cols))
            for i, season in enumerate(cols):
                s = self.minimal_stats.get(season, {})
                self.table.setItem(i, 0, QTableWidgetItem(season.upper()))
                self.table.setItem(i, 1, QTableWidgetItem(str(s.get("n", 0))))
                self.table.setItem(i, 2, QTableWidgetItem(f"{s.get('mean', 0):.2f}" if s.get('mean') else "---"))
                self.table.setItem(i, 3, QTableWidgetItem(f"{s.get('Cv', 0):.4f}" if s.get('Cv') else "---"))
                self.table.setItem(i, 4, QTableWidgetItem(f"{s.get('Cs/Cv', 0):.2f}" if s.get('Cs/Cv') else "---"))
                self.table.setItem(i, 5, QTableWidgetItem(f"{s.get('epsilon', 0):.2f}" if s.get('epsilon') else "---"))
            self._plot_curves()
            self.result_box.append("Статистика рассчитана.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def _plot_curves(self):
        if not self.probability_curves:
            return
        self.figure.clear()
        colors = {"зима": "#0066CC", "лето": "#FF6600"}
        for idx, (season, df) in enumerate(self.probability_curves.items()):
            ax = self.figure.add_subplot(1, 2, idx + 1)
            color = colors.get(season, "#0066CC")
            ax.plot(df["P_%"], df["Q_p"], "o-", color=color, lw=2)
            ax.set_title(f"Минимальный сток — {season.upper()}")
            ax.set_xlim(70, 100)
            ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
        self.canvas.draw()

    def set_data(self, winter_series=None, summer_series=None):
        """Приём данных из единого загрузчика."""
        if winter_series is not None:
            self.winter = winter_series
        if summer_series is not None:
            self.summer = summer_series
        if winter_series is not None or summer_series is not None:
            self.result_box.append("Данные загружены из шаблона")

    def save_report(self):
        if not self.minimal_stats:
            QMessageBox.warning(self, "Внимание", "Сначала рассчитайте")
            return
        filepath, _ = QFileDialog.getSaveFileName(self, "Сохранить", "Отчёт_Работа3.xlsx", "Excel (*.xlsx)")
        if not filepath:
            return
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            rows = []
            for season, s in self.minimal_stats.items():
                rows.append({"Сезон": season, **s})
            pd.DataFrame(rows).to_excel(writer, sheet_name="Минимальный сток", index=False)
        QMessageBox.information(self, "Готово", f"Отчёт: {filepath}")
