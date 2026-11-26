"""Снимки русских настроек и светлого диалога выхода."""
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main_window import MainWindow
from app.ui.settings_dialog import SettingsDialog

app = QApplication([])
app.setStyleSheet((ROOT / "resources" / "swimrocket-theme.qss").read_text(encoding="utf-8"))
window = MainWindow()
settings = SettingsDialog(window.config, window)
settings.show()


def capture_settings():
    settings.grab().save(str(ROOT / "tests" / "ui_settings_ru.png"))
    print("SETTINGS_TITLE", settings.windowTitle(), flush=True)
    settings.close()
    QTimer.singleShot(400, show_exit)


def show_exit():
    QTimer.singleShot(1200, capture_exit)
    result = window._confirm_exit()
    print("EXIT_CANCEL_RESULT", result, flush=True)
    assert result is False
    window._really_quit = True
    window.close()
    app.quit()


def capture_exit():
    dialog = QApplication.activeModalWidget()
    assert isinstance(dialog, QDialog)
    dialog.grab().save(str(ROOT / "tests" / "ui_exit_ru.png"))
    for button in dialog.findChildren(QPushButton):
        if button.text() == "Отмена":
            button.click()
            return
    raise RuntimeError("Кнопка «Отмена» не найдена")


QTimer.singleShot(3500, capture_settings)
sys.exit(app.exec())
