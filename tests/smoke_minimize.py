"""Три цикла сворачивания в трей и восстановления с контрольным снимком."""
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main_window import MainWindow

app = QApplication([])
app.setStyleSheet((ROOT / "resources" / "swimrocket-theme.qss").read_text(encoding="utf-8"))
window = MainWindow()
window.meeting_monitor.stop()
window.tray.is_supported = lambda: True
window.show()
cycle = 0


def minimize():
    global cycle
    cycle += 1
    print(f"MINIMIZE {cycle}", flush=True)
    window.showMinimized()
    QTimer.singleShot(700, restore)


def restore():
    print(f"RESTORE {cycle}: hidden={not window.isVisible()}", flush=True)
    assert window.isVisible(), "Окно исчезло из панели задач"
    window._restore_from_tray()
    QTimer.singleShot(1000, check)


def check():
    print(
        f"CHECK {cycle}: visible={window.isVisible()} minimized={window.isMinimized()} "
        f"size={window.width()}x{window.height()}", flush=True,
    )
    assert window.isVisible(), "Окно осталось скрытым"
    assert not window.isMinimized(), "Окно осталось свёрнутым"
    assert window.width() >= 1000 and window.height() >= 700, "Размер потерян"
    window.grab().save(str(ROOT / "tests" / f"ui_restore_{cycle}.png"))
    if cycle < 3:
        QTimer.singleShot(400, minimize)
    else:
        window._really_quit = True
        window.close()
        app.quit()


QTimer.singleShot(3000, minimize)
sys.exit(app.exec())
