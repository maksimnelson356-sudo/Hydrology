"""
gui/tabs/tab_data.py
Вкладка «Данные и статистика» — UI вынесен из main_window.setup_data_tab.

Виджеты доступны как атрибуты (combo_post, table, btn_*), чтобы main_window
сохранял существующие ссылки. Действия передаются сигналами.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from gui.plot_style import auto_resize_table

HINT_STYLE = (
    "color: #666; font-style: italic; padding: 8px; background: #f0f0f0; border-radius: 4px;"
)
LOAD_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; font-weight: bold; "
    "padding: 10px; font-size: 13px; border-radius: 6px; }"
    "QPushButton:hover { background-color: #0D47A1; }"
)
MANUAL_STYLE = (
    "QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 6px; }"
)
ADD_POST_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; font-weight: bold; padding: 6px; }"
)


class TabData(QWidget):
    """Раздел «Данные и статистика»: загрузка, пост, операции над рядом, статистика."""

    load_requested = pyqtSignal()
    manual_input_requested = pyqtSignal()
    add_post_requested = pyqtSignal()
    post_changed = pyqtSignal(str)
    fill_requested = pyqtSignal()
    fill_corr_requested = pyqtSignal()
    homogeneity_requested = pyqtSignal()
    outliers_requested = pyqtSignal()
    quality_requested = pyqtSignal()
    composite_break_requested = pyqtSignal()
    clear_composite_requested = pyqtSignal()
    quantiles_requested = pyqtSignal()
    gts_curve_requested = pyqtSignal()
    composite_auto_requested = pyqtSignal()
    extend_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        hint = QLabel("Данные загружаются через меню или вводятся вручную")
        hint.setStyleSheet(HINT_STYLE)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn_load_file = QPushButton("📂 Загрузить данные из файла (Excel)")
        btn_load_file.setStyleSheet(LOAD_STYLE)
        btn_load_file.clicked.connect(self.load_requested)
        layout.addWidget(btn_load_file)

        btn_manual = QPushButton("✏ Ввести данные вручную")
        btn_manual.setStyleSheet(MANUAL_STYLE)
        btn_manual.clicked.connect(self.manual_input_requested)

        btn_add_post = QPushButton("➕ Добавить пост (ещё один файл)")
        btn_add_post.setStyleSheet(ADD_POST_STYLE)
        btn_add_post.clicked.connect(self.add_post_requested)

        btn_row_top = QHBoxLayout()
        btn_row_top.addWidget(btn_manual)
        btn_row_top.addWidget(btn_add_post)
        layout.addLayout(btn_row_top)

        post_layout = QHBoxLayout()
        lbl_post = QLabel("Пост:")
        lbl_post.setStyleSheet("font-weight: bold; font-size: 14px; color: #1565C0;")
        post_layout.addWidget(lbl_post)
        self.combo_post = QComboBox()
        self.combo_post.setMinimumWidth(160)
        self.combo_post.currentTextChanged.connect(self.post_changed)
        post_layout.addWidget(self.combo_post)
        post_layout.addStretch()

        self.btn_fill = QPushButton("Восстановить пропуски (простое)")
        self.btn_fill.clicked.connect(self.fill_requested)
        self.btn_fill.setEnabled(False)

        self.btn_fill_corr = QPushButton("Восстановить пропуски (по корреляции)")
        self.btn_fill_corr.clicked.connect(self.fill_corr_requested)
        self.btn_fill_corr.setEnabled(False)

        self.btn_homogeneity = QPushButton("Проверить однородность ряда")
        self.btn_homogeneity.clicked.connect(self.homogeneity_requested)
        self.btn_homogeneity.setEnabled(False)

        self.btn_outliers = QPushButton("Найти выдающиеся значения")
        self.btn_outliers.clicked.connect(self.outliers_requested)
        self.btn_outliers.setEnabled(False)

        self.btn_quality = QPushButton("Качество данных и рекомендации")
        self.btn_quality.clicked.connect(self.quality_requested)
        self.btn_quality.setEnabled(False)

        self.btn_composite = QPushButton("Составная кривая (указать год разрыва)")
        self.btn_composite.clicked.connect(self.composite_break_requested)
        self.btn_composite.setEnabled(False)

        self.btn_clear_break = QPushButton("Сбросить составную кривую")
        self.btn_clear_break.clicked.connect(self.clear_composite_requested)
        self.btn_clear_break.setEnabled(False)

        self.btn_quantiles = QPushButton("Расчётные расходы (Q заданной обеспеченности)")
        self.btn_quantiles.clicked.connect(self.quantiles_requested)
        self.btn_quantiles.setEnabled(False)

        self.btn_gts_curve = QPushButton("Кривая с точками ГТС")
        self.btn_gts_curve.clicked.connect(self.gts_curve_requested)
        self.btn_gts_curve.setEnabled(False)

        self.btn_composite_auto = QPushButton("Составная кривая (авто)")
        self.btn_composite_auto.clicked.connect(self.composite_auto_requested)
        self.btn_composite_auto.setEnabled(False)

        self.btn_extend = QPushButton("Удлинить ряд по аналогу")
        self.btn_extend.clicked.connect(self.extend_requested)
        self.btn_extend.setEnabled(False)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        auto_resize_table(self.table)

        data_splitter = QSplitter(Qt.Orientation.Vertical)
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.addLayout(post_layout)
        top_layout.addWidget(self.btn_fill)
        top_layout.addWidget(self.btn_fill_corr)
        top_layout.addWidget(self.btn_homogeneity)
        top_layout.addWidget(self.btn_outliers)
        top_layout.addWidget(self.btn_composite)
        top_layout.addWidget(self.btn_clear_break)
        top_layout.addWidget(self.btn_quantiles)
        top_layout.addWidget(self.btn_gts_curve)
        top_layout.addWidget(self.btn_composite_auto)
        top_layout.addWidget(self.btn_extend)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.addWidget(QLabel("Статистика:"))
        bottom_layout.addWidget(self.table)

        data_splitter.addWidget(top_widget)
        data_splitter.addWidget(bottom_widget)
        data_splitter.setStretchFactor(0, 1)
        data_splitter.setStretchFactor(1, 2)
        data_splitter.setSizes([400, 600])

        layout.addWidget(data_splitter)


__all__ = ["TabData"]
