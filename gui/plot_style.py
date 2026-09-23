"""
gui/plot_style.py
Единая design-система для приложения HydroSphere.

Содержит:
- Палитру цветов
- QSS-стили для всех виджетов
- Утилиты для таблиц
- Фабрику иконок
"""

import os

from matplotlib import rcParams
from PyQt6.QtCore import QEvent, QObject, QSize
from PyQt6.QtGui import QAction, QFont, QIcon
from PyQt6.QtWidgets import QHeaderView, QPushButton, QTableWidget, QToolBar

# ============================================================
# ЦВЕТОВАЯ ПАЛИТРА (Material Design Blue)
# ============================================================

COLORS = {
    "primary": "#1565C0",
    "primary_dark": "#0D47A1",
    "primary_light": "#42A5F5",
    "primary_bg": "#E3F2FD",
    "primary_border": "#90CAF9",

    "secondary": "#C62828",
    "secondary_light": "#EF5350",

    "accent": "#2E7D32",
    "accent_light": "#66BB6A",

    "warm": "#FF6600",
    "orange": "#FF9800",
    "purple": "#6A1B9A",
    "teal": "#00838F",
    "pink": "#880E4F",

    "surface": "#FAFAFA",
    "surface_variant": "#F5F5F5",
    "background": "#FFFFFF",

    "text_primary": "#212121",
    "text_secondary": "#757575",
    "text_disabled": "#BDBDBD",

    "border": "#E0E0E0",
    "border_strong": "#BDBDBD",
    "divider": "#EEEEEE",

    "sidebar_bg": "#1A237E",
    "sidebar_item": "#C5CAE9",
    "sidebar_selected": "#3F51B5",
    "sidebar_hover": "#283593",
    "sidebar_accent": "#FFD54F",

    "button_bg": "#1565C0",
    "button_hover": "#1976D2",
    "button_pressed": "#0D47A1",
    "button_danger": "#C62828",
    "button_success": "#2E7D32",
    "button_warning": "#F57F17",

    "table_header_bg": "#E3F2FD",
    "table_header_text": "#1565C0",
    "table_selection": "#BBDEFB",

    "success": "#4CAF50",
    "warning": "#FF9800",
    "error": "#F44336",
    "info": "#2196F3",
}

RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")


# ============================================================
# ИКОНКИ
# ============================================================

def get_icon(name: str) -> QIcon:
    """Получить иконку по имени файла из resources/."""
    path = os.path.join(RESOURCES_DIR, f"icon_{name}.svg")
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()


def get_logo_icon() -> QIcon:
    """Получить иконку приложения."""
    for name in ["logo.png", "logo.svg", "icon.ico"]:
        path = os.path.join(RESOURCES_DIR, name)
        if os.path.exists(path) and os.path.getsize(path) > 100:
            return QIcon(path)
    root_icon = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.ico")
    if os.path.exists(root_icon):
        return QIcon(root_icon)
    return QIcon()


def setup_button_icon(button: QPushButton, icon_name: str, text: str = ""):
    """Настроить кнопку с иконкой и текстом."""
    icon = get_icon(icon_name)
    if not icon.isNull():
        button.setIcon(icon)
        button.setIconSize(QSize(16, 16))
    if text:
        button.setText(text)


def create_toolbar_action(toolbar: QToolBar, icon_name: str, text: str,
                         tooltip: str = "", shortcut: str = "",
                         callback=None) -> QAction:
    """Создать action для тулбара."""
    icon = get_icon(icon_name)
    action = QAction(icon, text)
    if tooltip:
        action.setToolTip(tooltip)
    if shortcut:
        action.setShortcut(shortcut)
    if callback:
        action.triggered.connect(callback)
    toolbar.addAction(action)
    return action


# ============================================================
# QSS — ЕДИНЫЙ СТИЛЬ ПРИЛОЖЕНИЯ
# ============================================================

def build_stylesheet() -> str:
    """Построить единый QSS для всего приложения."""
    arrow_path = os.path.join(RESOURCES_DIR, "arrow_down.svg").replace("\\", "/")

    return f"""
    /* === ГЛОБАЛЬНЫЕ === */
    QWidget {{
        font-family: 'Segoe UI', 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif;
        font-size: 11px;
        color: {COLORS['text_primary']};
    }}

    /* === КНОПКИ === */
    QPushButton {{
        background-color: {COLORS['button_bg']};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 18px;
        font-weight: 600;
        font-size: 11px;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background-color: {COLORS['button_hover']};
    }}
    QPushButton:pressed {{
        background-color: {COLORS['button_pressed']};
    }}
    QPushButton:disabled {{
        background-color: {COLORS['border']};
        color: {COLORS['text_disabled']};
    }}
    QPushButton[class="danger"] {{
        background-color: {COLORS['button_danger']};
    }}
    QPushButton[class="success"] {{
        background-color: {COLORS['button_success']};
    }}
    QPushButton[class="warning"] {{
        background-color: {COLORS['button_warning']};
    }}
    QPushButton[class="flat"] {{
        background-color: transparent;
        color: {COLORS['primary']};
        border: 1px solid {COLORS['primary']};
    }}
    QPushButton[class="flat"]:hover {{
        background-color: {COLORS['primary_bg']};
    }}

    /* === ИНПУТЫ === */
    QLineEdit, QDoubleSpinBox, QSpinBox {{
        background-color: {COLORS['background']};
        border: 1px solid {COLORS['border_strong']};
        border-radius: 6px;
        padding: 6px 10px;
        color: {COLORS['text_primary']};
        selection-background-color: {COLORS['primary']};
        min-height: 18px;
    }}
    QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
        border: 2px solid {COLORS['primary']};
        background-color: {COLORS['background']};
    }}
    QPlainTextEdit, QTextEdit {{
        background-color: {COLORS['background']};
        border: 1px solid {COLORS['border_strong']};
        border-radius: 6px;
        color: {COLORS['text_primary']};
        padding: 6px;
        font-family: 'Consolas', 'SF Mono', monospace;
    }}
    QPlainTextEdit:focus, QTextEdit:focus {{
        border: 2px solid {COLORS['primary']};
    }}

    /* === ТАБЛИЦЫ === */
    QTableWidget {{
        gridline-color: {COLORS['border']};
        background-color: {COLORS['background']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        selection-background-color: {COLORS['table_selection']};
        alternate-background-color: {COLORS['surface']};
    }}
    QTableWidget::item {{
        padding: 4px 8px;
    }}
    QHeaderView::section {{
        background-color: {COLORS['table_header_bg']};
        border: none;
        border-bottom: 2px solid {COLORS['primary']};
        border-right: 1px solid {COLORS['border']};
        padding: 6px 8px;
        font-weight: 700;
        color: {COLORS['table_header_text']};
        font-size: 11px;
    }}
    QHeaderView::section:horizontal:hover {{
        background-color: {COLORS['primary_light']};
        color: white;
    }}

    /* === КОМБОБОКС === */
    QComboBox {{
        background-color: {COLORS['background']};
        border: 2px solid {COLORS['primary']};
        border-radius: 6px;
        padding: 6px 28px 6px 10px;
        color: {COLORS['text_primary']};
        font-weight: 600;
        min-height: 18px;
    }}
    QComboBox:focus {{
        border: 2px solid {COLORS['primary_dark']};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 28px;
    }}
    QComboBox::down-arrow {{
        image: url({arrow_path});
        width: 14px;
        height: 14px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS['background']};
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        selection-background-color: {COLORS['primary_bg']};
        selection-color: {COLORS['primary_dark']};
        padding: 4px;
    }}

    /* === ГРУППЫ === */
    QGroupBox {{
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        margin-top: 14px;
        padding: 18px 12px 12px 12px;
        font-weight: 700;
        font-size: 11px;
        color: {COLORS['text_primary']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 14px;
        padding: 0 8px;
        color: {COLORS['primary']};
        font-size: 11px;
    }}

    /* === ТАБЫ === */
    QTabWidget::pane {{
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        background-color: {COLORS['background']};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 16px;
        margin-right: 2px;
        font-weight: 600;
        color: {COLORS['text_secondary']};
    }}
    QTabBar::tab:selected {{
        background-color: {COLORS['background']};
        color: {COLORS['primary']};
        border-bottom: 2px solid {COLORS['primary']};
        font-weight: 700;
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {COLORS['primary_bg']};
        color: {COLORS['primary']};
    }}

    /* === СТАТУС-БАР === */
    QStatusBar {{
        background-color: {COLORS['surface']};
        border-top: 1px solid {COLORS['border']};
        color: {COLORS['text_secondary']};
        font-size: 10px;
        padding: 2px 8px;
    }}

    /* === СКРОЛЛБАРЫ === */
    QScrollBar:vertical {{
        background-color: {COLORS['surface']};
        width: 10px;
        border-radius: 5px;
        margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background-color: {COLORS['border_strong']};
        border-radius: 5px;
        min-height: 30px;
    }}
    QScrollBar::handle:vertical:hover {{
        background-color: {COLORS['primary_light']};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    QScrollBar:horizontal {{
        background-color: {COLORS['surface']};
        height: 10px;
        border-radius: 5px;
        margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background-color: {COLORS['border_strong']};
        border-radius: 5px;
        min-width: 30px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background-color: {COLORS['primary_light']};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* === МЕНЮ === */
    QMenu {{
        background-color: {COLORS['background']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 4px;
    }}
    QMenu::item {{
        padding: 6px 24px 6px 12px;
        border-radius: 4px;
    }}
    QMenu::item:selected {{
        background-color: {COLORS['primary_bg']};
        color: {COLORS['primary']};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {COLORS['divider']};
        margin: 4px 8px;
    }}

    /* === TOOLTIP === */
    QToolTip {{
        background-color: {COLORS['text_primary']};
        color: white;
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 10px;
    }}

    /* === SPLITTER === */
    QSplitter::handle {{
        background-color: {COLORS['border']};
    }}
    QSplitter::handle:horizontal {{
        width: 2px;
    }}
    QSplitter::handle:vertical {{
        height: 2px;
    }}

    /* === САЙДБАР НАВИГАЦИИ === */
    QListWidget#sidebar {{
        background-color: {COLORS['sidebar_bg']};
        border: none;
        border-radius: 0;
        padding: 4px 0;
        font-size: 11px;
        font-weight: 600;
        outline: none;
    }}
    QListWidget#sidebar::item {{
        color: {COLORS['sidebar_item']};
        padding: 10px 16px;
        border-left: 3px solid transparent;
        border-radius: 0;
        margin: 1px 0;
    }}
    QListWidget#sidebar::item:selected {{
        background-color: {COLORS['sidebar_selected']};
        color: white;
        border-left: 3px solid {COLORS['sidebar_accent']};
    }}
    QListWidget#sidebar::item:hover:!selected {{
        background-color: {COLORS['sidebar_hover']};
        color: white;
    }}

    /* === ПРОГРЕСС === */
    QProgressBar {{
        border: 1px solid {COLORS['border']};
        border-radius: 4px;
        text-align: center;
        background-color: {COLORS['surface']};
        height: 18px;
    }}
    QProgressBar::chunk {{
        background-color: {COLORS['primary']};
        border-radius: 3px;
    }}

    /* === LABEL С ЗАГОЛОВКОМ === */
    QLabel#page_title {{
        font-size: 16px;
        font-weight: 700;
        color: {COLORS['text_primary']};
        padding: 8px 0;
    }}
    QLabel#section_title {{
        font-size: 12px;
        font-weight: 700;
        color: {COLORS['primary']};
        padding: 4px 0;
    }}
    """


# ============================================================
# ШРИФТЫ
# ============================================================

FONT_DEFAULT = QFont("Segoe UI", 10)
FONT_MONO = QFont("Consolas", 10)
FONT_TITLE = QFont("Segoe UI", 14, QFont.Weight.Bold)
FONT_SECTION = QFont("Segoe UI", 11, QFont.Weight.Bold)
FONT_SMALL = QFont("Segoe UI", 9)


# ============================================================
# УТИЛИТЫ ДЛЯ ТАБЛИЦ
# ============================================================

def auto_resize_table(table: QTableWidget):
    """Автоматически подстроить ширину колонок."""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)
    table.verticalHeader().setDefaultSectionSize(30)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)


class AutoResizeTableFilter(QObject):
    """QEvent-фильтр: при Show автоматически подстраивает колонки."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            from PyQt6.QtWidgets import QTableWidget as _QTW
            for child in obj.findChildren(_QTW):
                auto_resize_table(child)
        return False


# ============================================================
# MATPLOTLIB СТИЛЬ
# ============================================================

def apply_global_style():
    """Применить единый стиль matplotlib для всех графиков."""
    rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "#FAFAFA",
        "axes.edgecolor": "#BDBDBD",
        "axes.grid": True,
        "grid.color": "#E0E0E0",
        "grid.alpha": 0.5,
        "grid.linewidth": 0.5,
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "legend.framealpha": 0.95,
        "legend.edgecolor": "#E0E0E0",
        "legend.fancybox": True,
        "lines.antialiased": True,
        "lines.solid_capstyle": "round",
        "lines.solid_joinstyle": "round",
        "lines.linewidth": 2.0,
        "lines.markersize": 6,
        "lines.markeredgewidth": 1.0,
        "axes.linewidth": 1.0,
        "patch.linewidth": 1.0,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "xtick.minor.width": 0.5,
        "ytick.minor.width": 0.5,
        "figure.dpi": 96,
    })


def setup_axes_style(ax, title=None, xlabel=None, ylabel=None):
    """Применить единый стиль к осям."""
    if title:
        ax.set_title(title, pad=12, fontweight="bold", fontsize=13)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, alpha=0.3, linestyle="--", color="#E0E0E0")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#BDBDBD")
    ax.spines["bottom"].set_color("#BDBDBD")
    ax.tick_params(colors="#424242", which="both", labelsize=9)


def add_info_box(ax, text, loc="lower right", fontsize=8):
    """Добавить информационную рамку на график."""
    props = dict(boxstyle="round,pad=0.6", facecolor="#E3F2FD", alpha=0.95,
                 edgecolor="#90CAF9", linewidth=0.5)
    x = 0.98 if "right" in loc else 0.02
    ha = "right" if "right" in loc else "left"
    ax.text(x, 0.02, text, transform=ax.transAxes,
            fontsize=fontsize, verticalalignment="bottom",
            horizontalalignment=ha, bbox=props, family="monospace")


# ============================================================
# P2.4 — расширенная визуализация (fan / histogram / tornado)
# Математики нет: только отрисовка. Без новых зависимостей.
# ============================================================

def draw_histogram_quantiles(ax, samples, summary, title="Выход — Monte Carlo"):
    """Гистограмма выборки с линиями p5 / p50 / p95.

    Args:
        ax: matplotlib Axes.
        samples: sequence of floats (MC output).
        summary: dict with keys p5, p50, p95 (and optionally mean).
        title: axes title.
    """
    import numpy as np  # local: keeps plot_style import light for non-plot paths

    data = np.asarray(list(samples), dtype=float)
    if data.size == 0:
        ax.set_title(title, fontsize=10)
        return
    bins = min(40, max(10, data.size // 25))
    ax.hist(data, bins=bins, color="#1565C0", alpha=0.75)
    for key, color in (("p5", "#C62828"), ("p50", "#2E7D32"), ("p95", "#E65100")):
        if key in summary and summary[key] is not None:
            ax.axvline(
                summary[key], color=color, linestyle="--", linewidth=1.4, label=key
            )
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("y", fontsize=9)
    ax.set_ylabel("Частота", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.4)


def draw_tornado_hbars(ax, names, swings, title="Tornado — чувствительность"):
    """Горизонтальные полосы tornado: most sensitive at the top.

    Args:
        ax: matplotlib Axes.
        names: parameter names (ordered most→least sensitive preferred).
        swings: |Δ output| magnitudes, same order as names.
        title: axes title.
    """
    labels = list(names)
    values = [float(v) for v in swings]
    if not labels:
        ax.set_title(title, fontsize=10)
        return
    y_pos = list(range(len(labels)))[::-1]
    ax.barh(y_pos, values, color="#1565C0", alpha=0.85, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("|Δ output|", fontsize=9)
    ax.set_title(title, fontsize=10)
    ax.grid(True, axis="x", linestyle=":", alpha=0.4)


def draw_fan_chart(ax, x, median, p_low, p_high, *, title="Fan-chart", label="p5–p95"):
    """Ленточный (fan) график: медиана + заливка между percentile-полосами.

    Args:
        ax: matplotlib Axes.
        x: x-coordinates (years or index).
        median: central line values.
        p_low: lower band (e.g. p5).
        p_high: upper band (e.g. p95).
        title: axes title.
        label: legend label for the band.
    """
    xs = list(x)
    if not xs:
        ax.set_title(title, fontsize=10)
        return
    med = [float(v) for v in median]
    lo = [float(v) for v in p_low]
    hi = [float(v) for v in p_high]
    ax.fill_between(xs, lo, hi, color="#90CAF9", alpha=0.55, label=label)
    ax.plot(xs, med, color="#0D47A1", linewidth=1.8, label="медиана")
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("x", fontsize=9)
    ax.set_ylabel("y", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True, linestyle=":", alpha=0.4)


# Инициализация
apply_global_style()
