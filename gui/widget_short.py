"""
gui/widget_short.py
Виджет «Восстановление коротких рядов» (Short)

Аналог программы Short2012 (ГГИ):
- Загрузка данных с коротким рядом (1-6 лет) + ряды аналогов
- Интерактивный выбор аналогов
- Построение графиков связей (scatter + regression)
- Восстановление пропущенных значений
- Протокол результатов
"""

import numpy as np
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit,
    QLabel, QCheckBox, QSpinBox, QMessageBox, QFileDialog,
    QGroupBox, QFormLayout, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from core.short_series import (
    fit_analog_relationship,
    restore_short_series,
    build_protocol,
)
from gui.plot_style import apply_global_style, setup_axes_style, COLORS, auto_resize_table


class ShortWidget(QWidget):
    """Виджет восстановления коротких рядов (<6 лет)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._all_posts = {}          # post_name → DataFrame{year, value}
        self._available_posts = []
        self._analogs_data = {}       # analog_name → pd.Series
        self._selected_analogs = []
        self._excluded_analogs = set()
        self._fits = {}
        self._result = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Заголовок
        title = QLabel('Восстановление коротких рядов (<6 лет)')
        title.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        title.setStyleSheet('color: #F57C00; padding: 4px 0;')
        layout.addWidget(title)

        # Кнопки управления
        btn_row = QHBoxLayout()
        self.btn_load = QPushButton('Загрузить данные из файла')
        self.btn_load.setStyleSheet(
            'QPushButton { background: #1565C0; color: white; '
            'padding: 8px 16px; border-radius: 4px; font-weight: bold; }')
        self.btn_load.clicked.connect(self._load_data)

        self.btn_select = QPushButton('Выбрать аналоги')
        self.btn_select.setEnabled(False)
        self.btn_select.clicked.connect(self._select_analogs)

        self.btn_restore = QPushButton('Восстановить данные')
        self.btn_restore.setStyleSheet(
            'QPushButton { background: #2E7D32; color: white; '
            'padding: 8px 16px; border-radius: 4px; font-weight: bold; }')
        self.btn_restore.setEnabled(False)
        self.btn_restore.clicked.connect(self._restore)

        self.btn_save = QPushButton('Сохранить протокол')
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_protocol)

        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_select)
        btn_row.addWidget(self.btn_restore)
        btn_row.addWidget(self.btn_save)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Настройки
        opts_row = QHBoxLayout()
        self.cb_single = QCheckBox('Единое решение (k1=σy/σx)')
        self.cb_single.setChecked(True)
        self.cb_module = QCheckBox('Преобразовать к q (л/с·км²)')
        self.spin_min = QSpinBox()
        self.spin_min.setRange(2, 20)
        self.spin_min.setValue(5)
        self.spin_min.setPrefix('Мин. аналогов: ')
        opts_row.addWidget(self.cb_single)
        opts_row.addWidget(self.cb_module)
        opts_row.addWidget(self.spin_min)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        # Основной splitter: таблица данных | графики
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая часть: таблица данных
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        lbl_data = QLabel('Исходные данные:')
        lbl_data.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        left_layout.addWidget(lbl_data)

        self.table_data = QTableWidget()
        self.table_data.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_data.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        left_layout.addWidget(self.table_data)

        main_splitter.addWidget(left_widget)

        # Правая часть: графики связей
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        lbl_plots = QLabel('Графики связей с аналогами:')
        lbl_plots.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        right_layout.addWidget(lbl_plots)

        self.figure = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        right_layout.addWidget(self.canvas)

        main_splitter.addWidget(right_widget)
        main_splitter.setSizes([400, 600])

        layout.addWidget(main_splitter, stretch=3)

        # Нижняя часть: результаты + протокол
        bottom_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Таблица результатов
        res_widget = QWidget()
        res_layout = QVBoxLayout(res_widget)
        res_layout.setContentsMargins(0, 0, 0, 0)

        lbl_res = QLabel('Результаты восстановления:')
        lbl_res.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        res_layout.addWidget(lbl_res)

        self.table_results = QTableWidget()
        self.table_results.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        res_layout.addWidget(self.table_results)

        bottom_splitter.addWidget(res_widget)

        # Протокол
        proto_widget = QWidget()
        proto_layout = QVBoxLayout(proto_widget)
        proto_layout.setContentsMargins(0, 0, 0, 0)

        lbl_proto = QLabel('Протокол:')
        lbl_proto.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        proto_layout.addWidget(lbl_proto)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont('Consolas', 9))
        self.result_text.setStyleSheet(
            'QTextEdit { background: #FAFAFA; border: 1px solid #DDD; }')
        proto_layout.addWidget(self.result_text)

        bottom_splitter.addWidget(proto_widget)
        bottom_splitter.setSizes([500, 400])

        layout.addWidget(bottom_splitter, stretch=2)

    def set_data(self, all_posts: dict = None, available_posts: list = None,
                 daily_df: pd.DataFrame = None, **kwargs):
        """
        Получение данных от main_window.

        all_posts: dict[post_name → DataFrame{year, value}]
        """
        if all_posts:
            self._all_posts = all_posts
            self._available_posts = available_posts or list(all_posts.keys())
            self._populate_data_table()
            self.btn_select.setEnabled(True)
            self.result_text.setText(
                f'Загружено {len(self._available_posts)} постов.\n'
                'Выберите расчётный пост (короткий ряд) и аналоги.')

    def _populate_data_table(self):
        """Заполнение таблицы исходных данных."""
        if not self._all_posts:
            return

        # Собираем все годы
        all_years = set()
        for post_name, df in self._all_posts.items():
            if 'year' in df.columns:
                all_years.update(df['year'].dropna().astype(int).tolist())
            elif hasattr(df.index, 'tolist'):
                all_years.update(df.index.tolist())

        years = sorted(all_years)
        post_names = list(self._all_posts.keys())

        self.table_data.setRowCount(len(years))
        self.table_data.setColumnCount(len(post_names) + 1)
        self.table_data.setHorizontalHeaderLabels(
            ['Год'] + post_names)

        for i, year in enumerate(years):
            self.table_data.setItem(i, 0, QTableWidgetItem(str(year)))
            for j, post_name in enumerate(post_names):
                df = self._all_posts[post_name]
                val = ''
                if 'year' in df.columns:
                    match = df[df['year'] == year]
                    if not match.empty and 'value' in match.columns:
                        v = match['value'].iloc[0]
                        if pd.notna(v):
                            val = f'{v:.2f}'
                elif year in df.index:
                    v = df.loc[year]
                    if hasattr(v, 'iloc'):
                        v = v.iloc[0]
                    if pd.notna(v):
                        val = f'{v:.2f}'
                item = QTableWidgetItem(val)
                if val == '':
                    item.setBackground(QColor('#FFF9C4'))
                self.table_data.setItem(i, j + 1, item)

        auto_resize_table(self.table_data)

    def _load_data(self):
        """Загрузка данных из Excel файла."""
        path, _ = QFileDialog.getOpenFileName(
            self, 'Загрузить данные', '',
            'Excel (*.xlsx);;Все файлы (*)')
        if not path:
            return

        try:
            xls = pd.ExcelFile(path)
            all_posts = {}
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name)
                # Ищем колонку года
                year_col = None
                for col in df.columns:
                    if str(col).lower() in ('год', 'year', 'years', 'годы'):
                        year_col = col
                        break
                if year_col is None:
                    year_col = df.columns[0]

                for col in df.columns:
                    if col == year_col:
                        continue
                    try:
                        values = pd.to_numeric(df[col], errors='raise')
                        if values.notna().sum() >= 1:
                            post_df = pd.DataFrame({
                                'year': pd.to_numeric(
                                    df[year_col], errors='coerce'),
                                'value': values,
                            }).dropna(subset=['value'])
                            if not post_df.empty:
                                all_posts[str(col)] = post_df
                    except (ValueError, TypeError):
                        continue

            if all_posts:
                self._all_posts = all_posts
                self._available_posts = list(all_posts.keys())
                self._populate_data_table()
                self.btn_select.setEnabled(True)
                self.result_text.setText(
                    f'Загружено {len(all_posts)} постов из {path}')
            else:
                QMessageBox.warning(
                    self, 'Ошибка',
                    'Не удалось найти данные в файле.')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))

    def _select_analogs(self):
        """Выбор расчётного поста и аналогов через диалог."""
        if not self._all_posts:
            return

        post_names = list(self._all_posts.keys())
        n_posts = len(post_names)

        if n_posts < 2:
            QMessageBox.warning(
                self, 'Ошибка',
                'Нужно минимум 2 поста (расчётный + 1 аналог)')
            return

        # Простой диалог: показываем список постов
        # с чекбоксами для выбора расчётного и аналогов
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QListWidget

        dialog = QDialog(self)
        dialog.setWindowTitle('Выбор постов')
        dialog.setMinimumSize(400, 500)
        dlg_layout = QVBoxLayout(dialog)

        lbl_calc = QLabel('Расчётный пост (короткий ряд):')
        lbl_calc.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        dlg_layout.addWidget(lbl_calc)

        list_calc = QListWidget()
        list_calc.addItems(post_names)
        list_calc.setCurrentRow(0)
        dlg_layout.addWidget(list_calc)

        lbl_analogs = QLabel('Аналоги (отметьте галочками):')
        lbl_analogs.setFont(QFont('Segoe UI', 10, QFont.Weight.Bold))
        dlg_layout.addWidget(lbl_analogs)

        list_analogs = QListWidget()
        list_analogs.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection)
        for i, name in enumerate(post_names):
            item = QListWidget.ItemText.__class__  # dummy
            list_analogs.addItem(name)
        dlg_layout.addWidget(list_analogs)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(dialog.accept)
        btn_box.rejected.connect(dialog.reject)
        dlg_layout.addWidget(btn_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            calc_row = list_calc.currentRow()
            calc_name = post_names[calc_row]
            selected = [
                item.text() for item in list_analogs.selectedItems()
                if item.text() != calc_name]

            if not selected:
                QMessageBox.warning(
                    self, 'Ошибка',
                    'Выберите хотя бы один аналог')
                return

            # Строим Series для расчётного и аналогов
            calc_df = self._all_posts[calc_name]
            if 'year' in calc_df.columns:
                Q_calc = calc_df.set_index('year')['value']
            else:
                Q_calc = calc_df['value']

            self._analogs_data = {}
            for name in selected:
                df = self._all_posts[name]
                if 'year' in df.columns:
                    self._analogs_data[name] = df.set_index('year')['value']
                else:
                    self._analogs_data[name] = df['value']

            self._calc_series = Q_calc
            self._selected_analogs = selected
            self._excluded_analogs = set()

            self.result_text.setText(
                f'Расчётный пост: {calc_name}\n'
                f'Аналоги ({len(selected)}): {", ".join(selected)}\n\n'
                f'Короткий ряд: {len(Q_calc.dropna())} лет\n'
                f'Нажмите «Восстановить данные» для расчёта.')

            self.btn_restore.setEnabled(True)
            self._plot_analogs()

    def _plot_analogs(self):
        """Построение scatter-графиков связей для каждого аналога."""
        self.figure.clear()

        n = len(self._selected_analogs)
        if n == 0:
            self.canvas.draw()
            return

        cols = min(3, n)
        rows = (n + cols - 1) // cols

        for i, analog_name in enumerate(self._selected_analogs):
            ax = self.figure.add_subplot(rows, cols, i + 1)
            setup_axes_style(ax)

            Q_analog = self._analogs_data[analog_name]
            common = self._calc_series.dropna().index.intersection(
                Q_analog.dropna().index)

            if len(common) < 2:
                ax.set_title(f'{analog_name}\n(нет общих лет)',
                             fontsize=8)
                continue

            x = Q_analog.loc[common].values
            y = self._calc_series.loc[common].values

            ax.scatter(x, y, c=COLORS[0] if COLORS else '#1565C0',
                       s=30, alpha=0.7, zorder=3)

            # Линия связи
            fit = fit_analog_relationship(
                self._calc_series, Q_analog,
                use_single_solution=self.cb_single.isChecked())

            if fit.get('success'):
                x_range = np.linspace(x.min(), x.max(), 50)
                y_line = fit['k0'] + fit['k1'] * x_range
                ax.plot(x_range, y_line, 'r-', linewidth=1.5, alpha=0.8)

                r = fit['R']
                ax.set_title(
                    f'{analog_name}\n'
                    f'R={r:.3f} k1={fit["k1"]:.3f} n={fit["n_common"]}',
                    fontsize=8)
            else:
                ax.set_title(f'{analog_name}\n(недостаточно данных)',
                             fontsize=8)

            ax.set_xlabel('Qаналог', fontsize=7)
            ax.set_ylabel('Qрасч', fontsize=7)
            ax.tick_params(labelsize=6)

        self.figure.tight_layout()
        self.canvas.draw()

    def _restore(self):
        """Выполнение восстановления данных."""
        if not hasattr(self, '_calc_series') or not self._selected_analogs:
            QMessageBox.warning(
                self, 'Ошибка',
                'Сначала выберите расчётный пост и аналоги')
            return

        try:
            result = restore_short_series(
                Q_calc=self._calc_series,
                analogs=self._analogs_data,
                selected_analogs=self._selected_analogs,
                min_analogs=self.spin_min.value(),
                use_single_solution=self.cb_single.isChecked(),
                use_module_conversion=self.cb_module.isChecked(),
                excluded_analogs=list(self._excluded_analogs),
            )

            self._result = result
            self._fills_results_table(result)
            self._show_protocol(result)
            self.btn_save.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, 'Ошибка расчёта', str(e))

    def _fills_results_table(self, result: dict):
        """Заполнение таблицы результатов."""
        df = result.get('results', pd.DataFrame())
        if df.empty:
            return

        self.table_results.setRowCount(len(df))
        cols = ['Год', 'Q', 'Набл.', 'σ', 'δ%', 'N', 'Прим.']
        self.table_results.setColumnCount(len(cols))
        self.table_results.setHorizontalHeaderLabels(cols)

        for i, (_, row) in enumerate(df.iterrows()):
            self.table_results.setItem(
                i, 0, QTableWidgetItem(str(row['year'])))

            q_val = row['Q']
            q_item = QTableWidgetItem(
                f'{q_val:.4f}' if q_val != '' and pd.notna(q_val) else '—')
            if row.get('note', '') == 'Восстановлено':
                q_item.setBackground(QColor('#E8F5E9'))
            self.table_results.setItem(i, 1, q_item)

            obs_val = row['Q_observed']
            self.table_results.setItem(
                i, 2,
                QTableWidgetItem(
                    f'{obs_val:.4f}' if obs_val != '' and pd.notna(obs_val)
                    else '—'))

            self.table_results.setItem(
                i, 3,
                QTableWidgetItem(
                    f'{row["sigma"]:.4f}'
                    if row['sigma'] != '' and pd.notna(row['sigma'])
                    else '—'))

            self.table_results.setItem(
                i, 4,
                QTableWidgetItem(
                    f'{row["delta_pct"]:.1f}'
                    if row['delta_pct'] != '' and pd.notna(row['delta_pct'])
                    else '—'))

            self.table_results.setItem(
                i, 5,
                QTableWidgetItem(str(row['n_analogs']) if row['n_analogs'] != '' else '—'))

            self.table_results.setItem(
                i, 6, QTableWidgetItem(str(row.get('note', ''))))

        auto_resize_table(self.table_results)

    def _show_protocol(self, result: dict):
        """Отображение текстового протокола."""
        protocol = build_protocol(result)
        self.result_text.setText(protocol)

    def _save_protocol(self):
        """Сохранение протокола в текстовый файл."""
        if not self._result:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, 'Сохранить протокол', 'Продление_Short.txt',
            'Текстовые файлы (*.txt);;Все файлы (*)')
        if not path:
            return

        try:
            protocol = build_protocol(self._result)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(protocol)
            self.result_text.append(f'\n\nПротокол сохранён: {path}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', str(e))
