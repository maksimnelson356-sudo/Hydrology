"""
gui/widget_work2.py
Работа 2 — Внутригодовое распределение стока (PyQt6)
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.hydrorash.hydrological_periods import HydrologicalPeriods
from core.hydrorash.intra_annual import (
    calculate_water_year_sums,
    compute_intra_annual_stats,
    distribute_discharge,
    select_model_year,
)
from core.stats.sheet_reader import read_work_sheet
from gui.plot_style import auto_resize_table
from i18n import tr


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

        title = QLabel(tr("title_work2", "ВНУТРИГОДОВОЕ РАСПРЕДЕЛЕНИЕ СТОКА"))
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F4E79;")
        layout.addWidget(title)

        # Кнопки управления
        btn_row = QHBoxLayout()
        self.btn_load = QPushButton(tr("btn_load", "Загрузить данные (Excel)"))
        self.btn_load.clicked.connect(self.load_data)
        btn_row.addWidget(self.btn_load)

        self.btn_periods = QPushButton(tr("btn_periods", "Настроить периоды"))
        self.btn_periods.clicked.connect(self.open_periods_dialog)
        btn_row.addWidget(self.btn_periods)

        self.btn_calc = QPushButton(tr("btn_calc_sums", "РАССЧИТАТЬ СУММЫ"))
        self.btn_calc.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }"
        )
        self.btn_calc.clicked.connect(self.calculate)
        btn_row.addWidget(self.btn_calc)

        self.btn_model = QPushButton(tr("btn_model", "Год-модель (P=90%)"))
        self.btn_model.clicked.connect(self.choose_model_year)
        btn_row.addWidget(self.btn_model)

        self.btn_distribute = QPushButton(tr("btn_distribute", "Распределение"))
        self.btn_distribute.clicked.connect(self.calculate_distribution)
        btn_row.addWidget(self.btn_distribute)

        self.btn_save = QPushButton(tr("btn_save", "Сохранить отчёт"))
        self.btn_save.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; }"
        )
        self.btn_save.clicked.connect(self.save_report)
        btn_row.addWidget(self.btn_save)

        layout.addLayout(btn_row)

        # Таблица результатов
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            tr("col_param", "Параметр"),
            tr("col_mean", "Среднее"),
            tr("col_cv", "Cv"),
            tr("col_epsilon", "ε, %")
        ])
        auto_resize_table(self.table)
        layout.addWidget(self.table)

        # Текст
        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)
        self.result_box.setFont(QFont("Consolas", 10))
        layout.addWidget(self.result_box)

    def load_data(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("dialog_load_data", "Загрузить данные"), "", "Excel (*.xlsx)")
        if not path:
            return
        try:
            df = read_work_sheet(path, ["Внутригодовое распределение"], use_columns=True)
            if df.empty:
                df = pd.read_excel(path, skiprows=2)

            # Нормализуем колонки месяцев к 1-12, индекс — год
            month_map = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
                         "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
                         "ЯНВ": 1, "ФЕВ": 2, "МАР": 3, "АПР": 4, "МАЙ": 5, "ИЮН": 6,
                         "ИЮЛ": 7, "АВГ": 8, "СЕН": 9, "ОКТ": 10, "НОЯ": 11, "ДЕК": 12}
            renamed = {}
            year_col = None
            for c in df.columns:
                cs = str(c).strip().upper()
                if cs in month_map:
                    renamed[c] = month_map[cs]
                elif cs in ["ГОД", "YEAR", "YEARS"]:
                    renamed[c] = "год"
                    year_col = c
            df = df.rename(columns=renamed)
            if year_col is None:
                year_col = next((c for c in df.columns if "год" in str(c).lower() or "year" in str(c).lower()), None)
            if year_col is not None and year_col != "год":
                df = df.rename(columns={year_col: "год"})

            month_cols = [m for m in range(1, 13) if m in df.columns]
            if year_col is not None and month_cols:
                df = df[["год"] + month_cols].copy()
                df["год"] = pd.to_numeric(df["год"], errors="coerce")
                df = df.dropna(subset=["год"]).set_index("год")
                self.monthly_data = df
            else:
                self.monthly_data = df
            self.result_box.append(f"Загружено: {len(df)} строк, столбцы: {list(df.columns)[:6]}...")
        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))

    def open_periods_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("dialog_periods_title", "Настройка периодов"))
        dlg.setMinimumWidth(350)
        form = QFormLayout(dlg)
        e_start = QLineEdit(str(self.periods.water_year_start_month))
        e_nlp = QLineEdit("4-10")
        e_lp = QLineEdit("11-3")
        form.addRow(tr("label_water_year_start", "Начало водного года (месяц):"), e_start)
        form.addRow(tr("label_nlp", "НЛП:"), e_nlp)
        form.addRow(tr("label_lp", "ЛП:"), e_lp)

        def apply():
            try:
                self.periods = HydrologicalPeriods.from_text(
                    int(e_start.text()), e_nlp.text(), e_lp.text()
                )
                self.result_box.append(f"Периоды: {self.periods}")
                dlg.accept()
            except Exception as ex:
                QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(ex))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(apply)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        dlg.exec()

    def calculate(self):
        if self.monthly_data is None:
            QMessageBox.warning(self, tr("dialog_warning", "Внимание"), tr("msg_load_first", "Сначала загрузите данные"))
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

            self.result_box.append(tr("msg_calc_done", "Расчёт сумм выполнен."))
        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))

    def choose_model_year(self):
        if self.sums_df is None:
            QMessageBox.warning(self, tr("dialog_warning", "Внимание"), tr("msg_calc_first", "Сначала рассчитайте суммы"))
            return
        try:
            self.model_year = select_model_year(self.sums_df, target_P=90.0, by="сумма_ЛП")
            self.result_box.append(
                f"Год-модель: {self.model_year['год']}, "
                f"сумма ЛП = {self.model_year['сумма_ЛП']:.2f}"
            )
        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))

    def calculate_distribution(self):
        if self.model_year is None or self.monthly_data is None:
            QMessageBox.warning(self, tr("dialog_warning", "Внимание"), tr("msg_model_first", "Сначала выберите год-модель"))
            return
        try:
            mask = self.sums_df["год"] == self.model_year["год"]
            if mask.any():
                pos = self.sums_df[mask].index[0]
            else:
                pos = 0
            year_row = self.monthly_data.iloc[pos]
            month_map = {"I":1,"II":2,"III":3,"IV":4,"V":5,"VI":6,
                         "VII":7,"VIII":8,"IX":9,"X":10,"XI":11,"XII":12}
            normalized_row = year_row.copy()
            for col in year_row.index:
                col_str = str(col).strip().upper()
                if col_str in month_map:
                    normalized_row[month_map[col_str]] = year_row[col]
            self.distributed_df = distribute_discharge(
                annual_sum_P=self.model_year.get("target_sum"),
                model_year_row=normalized_row, periods=self.periods
            )
            if self.distributed_df is None or self.distributed_df.empty:
                raise ValueError("Не удалось рассчитать распределение (проверьте входные данные)")
            self.result_box.append(tr("msg_dist_done", "Распределение стока выполнено."))
        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))

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
            QMessageBox.warning(self, tr("dialog_warning", "Внимание"), tr("msg_calc_first", "Сначала рассчитайте внутригодовое распределение"))
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, tr("dialog_save_report", "Сохранить отчёт"), "Отчёт_Работа2.xlsx", "Excel (*.xlsx)"
        )
        if not filepath:
            return
        try:
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                self.sums_df.to_excel(writer, sheet_name="Водногодовые суммы", index=False)
                if self.distributed_df is not None:
                    self.distributed_df.to_excel(writer, sheet_name="Распределение", index=False)
            QMessageBox.information(self, tr("dialog_done", "Готово"), f"Отчёт сохранён:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, tr("dialog_error", "Ошибка"), str(e))
