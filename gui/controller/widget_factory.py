"""
gui/controller/widget_factory.py
Фабрика для создания виджетов работы (work1..work10, short).
Устраняет дублирование кода в widget_work*.py
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget


class BaseWorkWidget(QWidget):
    """Базовый класс для всех виджетов работы (work1..work10, short)."""
    calculation_done = pyqtSignal(dict)  # Результат расчёта

    def __init__(self, parent=None, title: str = "Работа", calc_type: str = "generic"):
        super().__init__(parent)
        self.calc_type = calc_type
        self._data = None
        self._setup_ui(title)

    def _setup_ui(self, title: str):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))

        self.btn_calculate = QPushButton("Рассчитать")
        self.btn_calculate.clicked.connect(self._on_calculate)
        layout.addWidget(self.btn_calculate)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        self.setLayout(layout)

    def set_data(self, data):
        """Установить входные данные для расчёта."""
        self._data = data

    def _on_calculate(self):
        """Переопределять в наследниках для конкретного расчёта."""
        if self._data is None:
            self.result_text.setPlainText("Данные не загружены")
            return
        # Базовая реализация — заглушка
        self.result_text.setPlainText(f"Расчёт {self.calc_type} не реализован")
        self.calculation_done.emit({"status": "not_implemented"})

    def show_result(self, text: str):
        self.result_text.setPlainText(text)


def create_work_widget(work_num: int, parent=None, **kwargs):
    """Фабричный метод для создания виджета по номеру."""
    # Импорт внутри функции для избежания циклических зависимостей
    if work_num == 1:
        from gui.widget_work1 import Work1Widget
        return Work1Widget(parent, **kwargs)
    elif work_num == 2:
        from gui.widget_work2 import Work2Widget
        return Work2Widget(parent, **kwargs)
    elif work_num == 3:
        from gui.widget_work3 import Work3Widget
        return Work3Widget(parent, **kwargs)
    elif work_num == 4:
        from gui.widget_work4 import Work4Widget
        return Work4Widget(parent, **kwargs)
    elif work_num == 5:
        from gui.widget_work5 import Work5Widget
        return Work5Widget(parent, **kwargs)
    elif work_num == 6:
        from gui.widget_work6 import Work6Widget
        return Work6Widget(parent, **kwargs)
    elif work_num == 7:
        from gui.widget_work7 import Work7Widget
        return Work7Widget(parent, **kwargs)
    elif work_num == 8:
        from gui.widget_work8 import Work8Widget
        return Work8Widget(parent, **kwargs)
    elif work_num == 9:
        from gui.widget_work9 import Work9Widget
        return Work9Widget(parent, **kwargs)
    elif work_num == 10:
        from gui.widget_work10 import Work10Widget
        return Work10Widget(parent, **kwargs)
    else:
        return BaseWorkWidget(parent, title=f"Работа {work_num}", calc_type=f"work{work_num}")
