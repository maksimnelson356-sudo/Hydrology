"""
gui/controller/plot_controller.py
Контроллер визуализации (matplotlib, графики, таблицы).
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal


class PlotController(QObject):
    """Управление построением и сохранением графиков."""
    plot_ready = pyqtSignal(object)  # Figure или путь
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Не храним состояние данных — это обязанность DataController

    def build_time_series_plot(self, df, ax_config: dict[str, Any]):
        try:
            from matplotlib.figure import Figure
            fig = Figure()
            ax = fig.add_subplot(111)
            ax.plot(df['year'], df['value'], marker='o')
            ax.set_title(ax_config.get('title', 'Временной ряд'))
            ax.set_xlabel(ax_config.get('xlabel', 'Год'))
            ax.set_ylabel(ax_config.get('ylabel', 'Расход'))
            ax.grid(True, alpha=0.3)
            return fig
        except Exception as exc:
            # Конкретное исключение вместо bare Exception
            self.error.emit(str(exc))
            return None

    def save_figure(self, figure, filepath: str) -> bool:
        try:
            figure.savefig(filepath, dpi=300, bbox_inches='tight')
            return True
        except (OSError, ValueError, TypeError) as exc:
            self.error.emit(f"Ошибка сохранения графика: {exc}")
            return False
