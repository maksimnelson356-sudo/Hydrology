"""
gui/controller/__init__.py
Контроллеры для разделения логики main_window.py
"""

from .data_controller import DataController
from .plot_controller import PlotController
from .widget_factory import create_work_widget

__all__ = ['DataController', 'PlotController', 'create_work_widget']
