"""
gui/update_dialog.py
Диалог обновлений HydroSphere.

Показывает:
- Результат проверки обновлений
- changelog новой версии
- Прогресс скачивания и установки
"""

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from gui.plot_style import COLORS, get_icon
from version import VERSION_STRING


class UpdateWorker(QThread):
    """Фоновый поток для проверки/скачивания обновлений."""
    progress = pyqtSignal(float, str)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, checker, mode="check", info=None):
        super().__init__()
        self.checker = checker
        self.mode = mode
        self.info = info

    def run(self):
        self.checker.set_progress_callback(self._on_progress)
        try:
            if self.mode == "check":
                result = self.checker.check_for_updates(force=True)
                self.finished.emit(result)
            elif self.mode == "download":
                path = self.checker.download_update(self.info)
                self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))

    def _on_progress(self, percent, message):
        self.progress.emit(percent, message)


class UpdateDialog(QDialog):
    """Диалог обновлений."""

    def __init__(self, parent=None, checker=None, update_info=None):
        super().__init__(parent)
        self.checker = checker
        self.update_info = update_info
        self.worker = None
        self._downloaded_path = None
        self._setup_ui()

        if update_info:
            self._show_update_info(update_info)

    def _setup_ui(self):
        self.setWindowTitle("Обновление HydroSphere")
        self.setMinimumSize(500, 450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # Заголовок
        title_layout = QHBoxLayout()
        icon_label = QLabel()
        icon = get_icon("info")
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(32, 32))
        title_label = QLabel("Обновление HydroSphere")
        title_label.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['primary']};")
        title_layout.addWidget(icon_label)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # Разделитель
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(line)

        # Информация
        self.info_label = QLabel("Проверка обновлений...")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"font-size: 11px; color: {COLORS['text_secondary']};")
        layout.addWidget(self.info_label)

        # Changelog
        self.changelog_text = QTextEdit()
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setMaximumHeight(180)
        self.changelog_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', monospace;
                font-size: 10px;
            }}
        """)
        layout.addWidget(self.changelog_text)

        # Прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Статус
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size: 10px; color: {COLORS['text_secondary']};")
        layout.addWidget(self.status_label)

        # Чекбокс "Больше не напоминать"
        self.skip_checkbox = QCheckBox("Больше не напоминать об этой версии")
        self.skip_checkbox.setVisible(False)
        layout.addWidget(self.skip_checkbox)

        # Кнопки
        btn_layout = QHBoxLayout()

        self.btn_check = QPushButton("Проверить сейчас")
        self.btn_check.clicked.connect(self._on_check)
        btn_layout.addWidget(self.btn_check)

        self.btn_download = QPushButton("Скачать и установить")
        self.btn_download.setStyleSheet(f"background-color: {COLORS['button_success']};")
        self.btn_download.clicked.connect(self._on_download)
        self.btn_download.setVisible(False)
        btn_layout.addWidget(self.btn_download)

        self.btn_skip = QPushButton("Пропустить")
        self.btn_skip.clicked.connect(self._on_skip)
        self.btn_skip.setVisible(False)
        btn_layout.addWidget(self.btn_skip)

        self.btn_close = QPushButton("Закрыть")
        self.btn_close.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def _show_update_info(self, info):
        """Показать информацию об обновлении."""
        self.info_label.setText(
            f"Доступна новая версия <b>{info.version}</b> "
            f"(текущая: {VERSION_STRING})"
        )
        self.changelog_text.setPlainText(info.changelog or "(нет описания)")
        self.btn_check.setVisible(False)
        self.btn_download.setVisible(True)
        self.btn_skip.setVisible(True)
        self.skip_checkbox.setVisible(True)

    def _on_check(self):
        """Запустить проверку обновлений."""
        self.btn_check.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Проверка...")

        self.worker = UpdateWorker(self.checker, mode="check")
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_check_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_download(self):
        """Скачать и установить обновление."""
        if not self.update_info:
            return

        self.btn_download.setEnabled(False)
        self.btn_skip.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Скачивание...")

        self.worker = UpdateWorker(self.checker, mode="download", info=self.update_info)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_download_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_progress(self, percent, message):
        self.progress_bar.setValue(int(percent))
        self.status_label.setText(message)

    def _on_check_done(self, result):
        self.btn_check.setEnabled(True)
        self.progress_bar.setVisible(False)

        if result:
            self._show_update_info(result)
        else:
            self.status_label.setText("Обновлений нет. Уже последняя версия.")
            self.btn_check.setVisible(True)

    def _on_download_done(self, path):
        self.btn_download.setEnabled(True)
        self.progress_bar.setVisible(False)

        if path:
            self._downloaded_path = path
            self.status_label.setText("Установщик скачан. Запустить установку?")
            self.btn_download.setText("Установить")
            self.btn_download.clicked.disconnect()
            self.btn_download.clicked.connect(self._on_install)
            self.btn_download.setEnabled(True)
        else:
            self.status_label.setText("Ошибка скачивания")

    def _on_install(self):
        """Запустить установщик."""
        if self._downloaded_path and self._downloaded_path.exists():
            if self.checker.install_update(self._downloaded_path):
                self.close()

    def _on_skip(self):
        """Пропустить эту версию."""
        if self.update_info:
            self.checker.skip_version(self.update_info.version)
        self.close()

    def _on_error(self, msg):
        self.btn_check.setEnabled(True)
        self.btn_download.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Ошибка: {msg}")
