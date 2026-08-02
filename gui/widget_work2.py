"""
gui/widget_work2.py
Работа 2 — Внутригодовое распределение стока (PyQt6)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QLineEdit, QTableWidget, QTableWidgetItem
)
from PyQt6.QtGui import QFont

from gui.plot_style import auto_resize_table

from core.hydrorash.hydrological_periods import HydrologicalPeriods
from core.hydrorash.intra_annual import (
    calculate_water_year_sums, compute_intra_annual_stats,
    select_model_year, distribute_discharge
)


class Work2Widget(QWidget):
    """Вкладка «Работа 2: Внутригодовое распределение стока»."""

    def __init__(self):
        super().__init__()
        self.monthly_data = None
        self.periods = HydrologicalPeriods()
        self.sums_df = None
        self.stats = None
        self.model_year = None
        self.distributed_df = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("ВНУТРИГОДОВОЕ РАСПРЕДЕЛЕНИЕ СТОКА")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F4E79;")
        layout.addWidget(title)

        # Кнопки управления
        btn_row = QHBoxLayout()
        self.btn_load = QPushButton("Загрузить данные (Excel)")
        self.btn_load.clicked.connect(self.load_data)
        btn_row.addWidget(self.btn_load)

        self.btn_periods = QPushButton("Настроить периоды")
        self.btn_periods.clicked.connect(self.open_periods_dialog)
        btn_row.addWidget(self.btn_periods)

        self.btn_calc = QPushButton("РАССЧИТАТЬ СУММЫ")
        self.btn_calc.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }"
        )
        self.btn_calc.clicked.connect(self.calculate)
        btn_row.addWidget(self.btn_calc)

        self.btn_model = QPushButton("Год-модель (P=90%)")
        self.btn_model.clicked.connect(self.choose_model_year)
        btn_row.addWidget(self.btn_model)

        self.btn_distribute = QPushButton("Распределение")
        self.btn_distribute.clicked.connect(self.calculate_distribution)
        btn_row.addWidget(self.btn_distribute)

        self.btn_save = QPushButton("Сохранить отчёт")
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; }"
        )
        self.btn_save.clicked.connect(self.save_report)
        btn_row.addWidget(self.btn_save)

        layout.addLayout(btn_row)

        # Таблица результатов
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Параметр", "Среднее", "Cv", "ε, %"])
        auto_resize_table(self.table)
        layout.addWidget(self.table)

        # Текст
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setFont(QFont("Consolas", 10))
        layout.addWidget(self.result_box)

    def load_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Загрузить данные", "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            df = pd.read_excel(path, skiprows=2)
            self.monthly_data = df
            self.result_box.append(f"Загружено: {len(df)} строк, столбцы: {list(df.columns)[:5]}...")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def open_periods_dialog(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("Настройка периодов")
        dlg.setMinimumWidth(350)
        form = QFormLayout(dlg)
        e_start = QLineEdit(str(self.periods.water_year_start_month))
        e_nlp = QLineEdit("4-10")
        e_lp = QLineEdit("11-3")
        form.addRow("Начало водного года (месяц):", e_start)
        form.addRow("НЛП:", e_nlp)
        form.addRow("ЛП:", e_lp)

        def apply():
            try:
                self.periods = HydrologicalPeriods.from_text(
                    int(e_start.text()), e_nlp.text(), e_lp.text()
                )
                self.result_box.append(f"Периоды: {self.periods}")
                dlg.accept()
            except Exception as ex:
                QMessageBox.critical(self, "Ошибка", str(ex))

        from PyQt6.QtWidgets import QDialogButtonBox
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(apply)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        dlg.exec()

    def calculate(self):
        if self.monthly_data is None:
            QMessageBox.warning(self, "Внимание", "Сначала загрузите данные")
            return
        try:
            self.sums_df = calculate_water_year_sums(self.monthly_data, periods=self.periods)
            self.stats = compute_intra_annual_stats(self.sums_df)

            self.table.setRowCount(len(self.stats))
            col_names = {"сумма_год": "Год", "сумма_НЛП": "НЛП", "сумма_ЛП": "ЛП", "сумма_ЛС": "ЛС"}
            for i, (key, val) in enumerate(self.stats.items()):
                self.table.setItem(i, 0, QTableWidgetItem(col_names.get(key, key)))
                self.table.setItem(i, 1, QTableWidgetItem(f"{val['mean']:.2f}" if val['mean'] else "—"))
                self.table.setItem(i, 2, QTableWidgetItem(f"{val['Cv']:.4f}" if val['Cv'] else "—"))
                self.table.setItem(i, 3, QTableWidgetItem(f"{val['epsilon']:.2f}" if val['epsilon'] else "—"))

            self.result_box.append("Расчёт сумм выполнен.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def choose_model_year(self):
        if self.sums_df is None:
            QMessageBox.warning(self, "Внимание", "Сначала рассчитайте суммы")
            return
        try:
            self.model_year = select_model_year(self.sums_df, target_P=90.0, by="сумма_ЛП")
            self.result_box.append(
                f"Год-модель: {self.model_year['год']}, "
                f"сумма ЛП = {self.model_year['сумма_ЛП']:.2f}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def calculate_distribution(self):
        if self.model_year is None or self.monthly_data is None:
            QMessageBox.warning(self, "Внимание", "Сначала выберите год-модель")
            return
        try:
            mask = self.sums_df["год"] == self.model_year["год"]
            if mask.any():
                pos = self.sums_df[mask].index[0]
            else:
                pos = 0
            year_row = self.monthly_data.iloc[pos]
            # Нормализуем ключи: строки "I"-"XII" → целые числа 1-12
            month_map = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,
                         "VII":7,"VIII":8,"IX":9,"X":10,"XI":11,"XII":12}
            normalized_row = year_row.copy()
            for col in year_row.index:
                col_str = str(col).strip().upper()
                if col_str in month_map:
                    normalized_row[month_map[col_str]] = year_row[col]
            self.distributed_df = distribute_discharge(
                annual_sum_P=self.model_year["target_sum"],
                model_year_row=normalized_row, periods=self.periods
            )
            self.result_box.append("Распределение стока выполнено.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def set_data(self, monthly_df=None, periods=None):
        """Приём данных из единого загрузчика."""
        if monthly_df is not None:
            self.monthly_data = monthly_df
        if periods is not None:
            self.periods = periods
        if monthly_df is not None:
            self.result_box.append(f"Загружено: {len(monthly_df)} строк из шаблона")

    def save_report(self):
        if self.sums_df is None:
            QMessageBox.warning(self, "Внимание", "Сначала рассчитайте внутригодовое распределение")
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчёт", "Отчёт_Работа2.xlsx", "Excel (*.xlsx)"
        )
        if not filepath:
            return
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                self.sums_df.to_excel(writer, sheet_name="Водногодовые суммы", index=False)
                if self.distributed_df is not None:
                    self.distributed_df.to_excel(writer, sheet_name="Распределение", index=False)
            QMessageBox.information(self, "Готово", f"Отчёт сохранён:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", str(e))
