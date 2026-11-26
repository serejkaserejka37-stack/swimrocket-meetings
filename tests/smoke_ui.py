"""Одноразовый cold-start UI без запуска тяжёлых моделей."""
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main_window import MainWindow

app = QApplication([])
style = ROOT / "resources" / "swimrocket-theme.qss"
if style.exists():
    app.setStyleSheet(style.read_text(encoding="utf-8"))
window = MainWindow()
window.show()


def finish():
    window.grab().save(str(ROOT / "tests" / "ui_smoke.png"))
    print("TITLE:", window.windowTitle(), flush=True)
    print("STATUS:", window.status_label.text(), flush=True)
    window._really_quit = True
    window.close()
    app.quit()


QTimer.singleShot(4000, finish)
sys.exit(app.exec())
