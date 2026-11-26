"""Координация автоматического старта и остановки записи встреч."""
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.utils.meeting_detector import MeetingDetector


class MeetingMonitor(QObject):
    auto_start_requested = pyqtSignal(str)
    auto_stop_requested = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.detector = MeetingDetector(
            start_delay=int(config.get("general", "auto_record_threshold")),
            stop_delay=10,
        )
        self.tracking = False
        self.audio_since = None
        self.missing_since = None
        self.last_label = ""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)

    def start(self):
        self.timer.start(2000)
        QTimer.singleShot(100, self.poll)

    def stop(self):
        self.timer.stop()

    def poll(self):
        if not self.config.get("general", "auto_record"):
            return
        current = self.detector.poll()
        now = time.monotonic()
        label = current["label"] or self.last_label or "встреча"
        if current["label"]:
            self.last_label = current["label"]

        if not self.tracking:
            # Окно конференции достаточно для старта: в начале встречи звук
            # может отсутствовать, а ждать речь и пропустить её нельзя.
            if current["present"]:
                if self.audio_since is None:
                    self.audio_since = now
                    self.status_changed.emit(f"Обнаружена встреча: {label}. Начинаю запись…")
                if now - self.audio_since >= self.detector.start_delay:
                    self.tracking = True
                    self.missing_since = None
                    self.status_changed.emit(f"Идёт запись: {label}")
                    self.auto_start_requested.emit(label)
            else:
                self.audio_since = None
            return

        self.audio_since = None
        if current["present"]:
            self.missing_since = None
            return
        if self.missing_since is None:
            self.missing_since = now
            self.status_changed.emit(f"Встреча {label} завершена? Проверяю…")
        elif now - self.missing_since >= self.detector.stop_delay:
            self.tracking = False
            self.missing_since = None
            self.auto_stop_requested.emit(label)
            self.status_changed.emit("Встреча завершена — сохраняю запись")
