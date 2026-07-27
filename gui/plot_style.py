"""
gui/plot_style.py
Единый стиль для всех графиков приложения ГидроСтатистика 2026.
"""

import matplotlib
from matplotlib import rcParams
from PyQt6.QtWidgets import QTableWidget, QHeaderView
from PyQt6.QtCore import QEvent, QObject


COLORS = {
    "primary": "#1565C0",
    "secondary": "#C62828",
    "accent": "#2E7D32",
    "warm": "#FF6600",
    "purple": "#6A1B9A",
    "teal": "#00838F",
    "light_blue": "#42A5F5",
    "orange": "#FF9800",
    "pink": "#880E4F",
    "grey": "#757575",
}

LINESTYLES = {
    "solid": "-",
    "dashed": "--",
    "dashdot": "-.",
    "dotted": ":",
}

MARKERS = {
    "circle": "o",
    "square": "s",
    "triangle": "^",
    "diamond": "D",
    "cross": "x",
    "plus": "+",
}


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
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "legend.framealpha": 0.9,
        "legend.edgecolor": "#BDBDBD",
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
    })


def setup_axes_style(ax, title=None, xlabel=None, ylabel=None):
    """Применить единый стиль к осям."""
    if title:
        ax.set_title(title, pad=10)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.4, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#BDBDBD")
    ax.spines["bottom"].set_color("#BDBDBD")
    ax.tick_params(colors="#424242", which="both")


def add_info_box(ax, text, loc="lower right", fontsize=8):
    """Добавить информационную рамку на график."""
    props = dict(boxstyle="round,pad=0.5", facecolor="#E3F2FD", alpha=0.9, edgecolor="#90CAF9")
    ax.text(
        0.98, 0.02, text, transform=ax.transAxes,
        fontsize=fontsize, verticalalignment="bottom", horizontalalignment="right",
        bbox=props, family="monospace"
    )


def auto_resize_table(table):
    """Автоматически подстроить ширину колонок под содержимое и заголовки."""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)
    table.verticalHeader().setDefaultSectionSize(28)


class AutoResizeTableFilter(QObject):
    """QEvent-фильтр: при Show автоматически подстраивает колонки всех QTableWidget-ов."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Show:
            from PyQt6.QtWidgets import QTableWidget as _QTW
            for child in obj.findChildren(_QTW):
                auto_resize_table(child)
        return False


apply_global_style()
