"""About TalkTrack dialog."""

import webbrowser
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
)

BMAC_URL = "https://buymeacoffee.com/obscureaintsecure"
VERSION = "1.0.0"


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе SwimRocket")
        self.setFixedSize(400, 280)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("SwimRocket Встречи")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #242841;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel(f"Version {VERSION}")
        version.setStyleSheet("font-size: 13px; color: #667085;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(
            "AI-powered call recording, transcription, and speaker\n"
            "diarization for Windows. Free and offline."
        )
        desc.setStyleSheet("font-size: 12px; color: #FFEAA0;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        bmac_btn = QPushButton("Поддержать проект")
        bmac_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #F1642E; color: #FFFFFF; font-weight: bold;"
            "  padding: 10px 20px; border-radius: 6px; font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #f2d68a;"
            "}"
        )
        bmac_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bmac_btn.clicked.connect(lambda: webbrowser.open(BMAC_URL))

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(bmac_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)
