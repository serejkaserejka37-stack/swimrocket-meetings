"""Визуальная проверка Light Glass в двух размерах и состоянии паузы."""
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main_window import MainWindow
from app.recording.recorder import RecordingState

app = QApplication([])
app.setStyleSheet((ROOT / "resources" / "swimrocket-theme.qss").read_text(encoding="utf-8"))
window = MainWindow()
window.show()


def check_buttons():
    window.recording_controls.set_state(RecordingState.PAUSED)
    app.processEvents()
    buttons = (
        window.recording_controls.record_btn,
        window.recording_controls.pause_btn,
        window.recording_controls.stop_btn,
        window.recording_controls.mute_btn,
        window.recording_controls.test_mic_btn,
    )
    for button in buttons:
        needed = button.fontMetrics().horizontalAdvance(button.text()) + 22
        print(f"BUTTON {button.text()}: width={button.width()} needed={needed}", flush=True)
        assert button.width() >= needed, f"Текст не помещается: {button.text()}"
    window.grab().save(str(ROOT / "tests" / "ui_glass_large.png"))


def check_minimum():
    window.resize(1000, 700)
    window.recording_controls.set_state(RecordingState.PAUSED)
    QTimer.singleShot(1400, capture_minimum)


def capture_minimum():
    window.grab().save(str(ROOT / "tests" / "ui_glass_minimum.png"))
    print("LAYOUT_OK", flush=True)
    window._really_quit = True
    window.close()
    app.quit()


QTimer.singleShot(3500, check_buttons)
QTimer.singleShot(5000, check_minimum)
sys.exit(app.exec())
