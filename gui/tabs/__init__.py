"""
gui/tabs/__init__.py
Разделы (панели) главного окна, вынесенные из main_window.py.
"""

from .tab_geo import TabGeo
from .tab_monte_carlo import TabMonteCarlo
from .tab_project import ProjectTab

__all__ = ["ProjectTab", "TabGeo", "TabMonteCarlo"]
