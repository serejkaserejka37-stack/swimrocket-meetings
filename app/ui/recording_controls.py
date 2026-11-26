from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from app.recording.recorder import RecordingState


class RecordingControls(QWidget):
    """Recording control buttons and timer — compact two-row layout.

    Row 1: [● Rec] [⏸ Pause] [■ Stop] [🎤 Mute]
    Row 2: ● 00:12:34
    """

    record_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    mute_clicked = pyqtSignal()
    # Emitted when the user toggles the Test Mic button. True = enable live
    # mic monitor (no recording); False = disable. Off by default every launch.
    test_mic_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._muted = False
        self._blink_state = True
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._toggle_indicator)
        self.set_state(RecordingState.IDLE)

    def _setup_ui(self):
        from PyQt6.QtWidgets import QSizePolicy

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(8)

        # Три основные кнопки всегда помещаются в узкую колонку.
        primary_row = QHBoxLayout()
        primary_row.setSpacing(8)

        self.record_btn = QPushButton("● Запись")
        self.record_btn.setObjectName("recordButton")
        self.record_btn.clicked.connect(self.record_clicked.emit)
        primary_row.addWidget(self.record_btn, 1)

        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.setObjectName("pauseButton")
        self.pause_btn.clicked.connect(self.pause_clicked.emit)
        primary_row.addWidget(self.pause_btn, 1)

        self.stop_btn = QPushButton("■ Стоп")
        self.stop_btn.setObjectName("stopButton")
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        primary_row.addWidget(self.stop_btn, 1)
        layout.addLayout(primary_row)

        # Дополнительные действия вынесены во второй ряд, без обрезания текста.
        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(8)
        self.mute_btn = QPushButton("Микрофон")
        self.mute_btn.setObjectName("muteButton")
        self.mute_btn.setToolTip("Выключить микрофон, продолжив запись собеседников")
        self.mute_btn.clicked.connect(self.mute_clicked.emit)
        secondary_row.addWidget(self.mute_btn, 1)

        self.test_mic_btn = QPushButton("Тест звука")
        self.test_mic_btn.setObjectName("testMicButton")
        self.test_mic_btn.setCheckable(True)
        self.test_mic_btn.setToolTip("Проверить микрофон и системный звук без записи")
        self.test_mic_btn.toggled.connect(self._update_test_mic_style)
        self.test_mic_btn.toggled.connect(self.test_mic_toggled.emit)
        secondary_row.addWidget(self.test_mic_btn, 1)
        layout.addLayout(secondary_row)

        for button in (self.record_btn, self.pause_btn, self.stop_btn,
                       self.mute_btn, self.test_mic_btn):
            button.setMinimumHeight(38)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        status_row = QHBoxLayout()
        status_row.setSpacing(7)
        self.recording_indicator = QLabel("")
        self.recording_indicator.setObjectName("recordingIndicator")
        self.recording_indicator.setFixedWidth(14)
        self.recording_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_row.addWidget(self.recording_indicator)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerLabel")
        status_row.addWidget(self.timer_label)
        status_row.addStretch()
        layout.addLayout(status_row)

    def set_state(self, state):
        if state == RecordingState.IDLE:
            self.record_btn.setEnabled(True)
            self.record_btn.setText("● Запись")
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("Пауза")
            self.stop_btn.setEnabled(False)
            self.mute_btn.setEnabled(False)
            self.set_muted(False)
            self.test_mic_btn.setEnabled(True)
            self.recording_indicator.setText("")
            self._blink_timer.stop()
        elif state == RecordingState.RECORDING:
            self.record_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("Пауза")
            self.stop_btn.setEnabled(True)
            self.mute_btn.setEnabled(True)
            self.test_mic_btn.setEnabled(False)
            self._blink_timer.start(500)
        elif state == RecordingState.PAUSED:
            self.record_btn.setEnabled(False)
            self.pause_btn.setEnabled(True)
            self.pause_btn.setText("Продолжить")
            self.stop_btn.setEnabled(True)
            self.mute_btn.setEnabled(True)
            self.test_mic_btn.setEnabled(False)
            self.recording_indicator.setText("Ⅱ")
            self._blink_timer.stop()
        elif state == RecordingState.STOPPING:
            self.record_btn.setEnabled(False)
            self.pause_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            self.mute_btn.setEnabled(False)
            self.test_mic_btn.setEnabled(False)
            self.recording_indicator.setText("")
            self._blink_timer.stop()

    def update_time(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        self.timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _update_test_mic_style(self, checked):
        if checked:
            self.test_mic_btn.setText("Проверка…")
            self.test_mic_btn.setStyleSheet(
                "QPushButton#testMicButton { "
                "background-color: #34C759; color: #FFFFFF; "
                "border: 1px solid #34C759; font-weight: bold; }"
            )
        else:
            self.test_mic_btn.setText("Тест звука")
            self.test_mic_btn.setStyleSheet("")

    def clear_test_mic(self):
        self.test_mic_btn.blockSignals(True)
        self.test_mic_btn.setChecked(False)
        self.test_mic_btn.blockSignals(False)
        self._update_test_mic_style(False)

    def set_muted(self, muted):
        self._muted = bool(muted)
        if self._muted:
            self.mute_btn.setText("Микрофон выкл.")
            self.mute_btn.setStyleSheet(
                "QPushButton#muteButton { "
                "background-color: #F1642E; color: #FFFFFF; "
                "border: 1px solid #F1642E; font-weight: bold; }"
            )
        else:
            self.mute_btn.setText("Микрофон")
            self.mute_btn.setStyleSheet("")

    def _toggle_indicator(self):
        self._blink_state = not self._blink_state
        self.recording_indicator.setText("\u25cf" if self._blink_state else "")

    def reset_timer(self):
        self.timer_label.setText("00:00:00")
