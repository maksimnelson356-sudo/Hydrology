"""
gui/workers/thread_example.py
Пример использования QThread для тяжёлых расчётов.
Этот файл демонстрирует, как CalculationWorker подключается к GUI.
"""

from PyQt6.QtCore import QThread, pyqtSignal


class ExampleWorker(QThread):
    result = pyqtSignal(dict)
    progress = pyqtSignal(int, str)
    error = pyqtSignal(str)

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data

    def run(self):
        try:
            self.progress.emit(10, "Начало расчёта...")
            # Здесь выполняется тяжёлый расчёт
            result = {"status": "done", "data": self.data}
            self.progress.emit(100, "Готово")
            self.result.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
