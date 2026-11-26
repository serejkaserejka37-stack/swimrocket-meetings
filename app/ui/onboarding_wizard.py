"""Мастер первичной настройки SwimRocket Встречи для нового пользователя."""
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QStackedWidget, QFrame, QApplication,
)

from app.api_client import ApiClient

BOT_URL = "https://t.me/swimrocket_meetings_bot"


class OnboardingWizard(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Настройка SwimRocket Встречи")
        self.setMinimumSize(620, 470)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "QDialog, QStackedWidget { background-color: #F3F6FB; }"
            "QFrame#glassPanel { background-color: rgba(255,255,255,225);"
            " border: 1px solid #D9E2EF; border-radius: 16px; }"
        )
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

        header = QHBoxLayout()
        logo = QLabel()
        logo_path = Path(__file__).parent.parent.parent / "resources" / "swimrocket-logo-light.png"
        if logo_path.exists():
            logo.setPixmap(QPixmap(str(logo_path)).scaled(
                145, 70, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        header.addWidget(logo)
        header.addStretch()
        self.step_label = QLabel("ШАГ 1 ИЗ 3")
        self.step_label.setObjectName("brandSubtitle")
        header.addWidget(self.step_label)
        root.addLayout(header)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self._add_welcome()
        self._add_bot_step()
        self._add_code_step()
        self._add_finish_step()

    def _page(self, title, text):
        page = QFrame()
        page.setObjectName("glassPanel")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)
        heading = QLabel(title)
        heading.setObjectName("wizardHeader")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet("color: #667085; font-size: 13px; line-height: 1.45;")
        layout.addWidget(body)
        self.pages.addWidget(page)
        return page, layout

    def _add_welcome(self):
        _, layout = self._page(
            "Добро пожаловать в SwimRocket Встречи",
            "Приложение само записывает Zoom и Яндекс Телемост, отправляет обработку "
            "на сервер и возвращает расшифровку, решения и задачи.\n\n"
            "Настройка займёт около двух минут. SSH, Obsidian и установка моделей "
            "на компьютер не нужны. Сначала свяжем приложение с вашим Telegram."
        )
        layout.addStretch()
        button = QPushButton("Начать настройку")
        button.setObjectName("recordButton")
        button.setMinimumHeight(44)
        button.clicked.connect(lambda: self._go(1))
        layout.addWidget(button)

    def _add_bot_step(self):
        _, layout = self._page(
            "Шаг 1. Нажмите Start в боте",
            "Откройте официального бота SwimRocket и нажмите Start. Бот пришлёт "
            "одноразовый код — он нужен только для связки с вашим личным чатом.\n\n"
            "Сводки будут приходить именно вам, а не в общий чат."
        )
        bot_button = QPushButton("Открыть @swimrocket_meetings_bot")
        bot_button.setMinimumHeight(42)
        bot_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(BOT_URL)))
        layout.addWidget(bot_button)
        layout.addStretch()
        next_button = QPushButton("Я нажал Start — продолжить")
        next_button.setObjectName("recordButton")
        next_button.setMinimumHeight(42)
        next_button.clicked.connect(lambda: self._go(2))
        layout.addWidget(next_button)

    def _add_code_step(self):
        _, layout = self._page(
            "Шаг 2. Введите код из бота",
            "Код имеет вид SR-XXXX-XXXX и действует 30 минут. После подключения "
            "приложение проверит доступ к серверу."
        )
        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("SR-XXXX-XXXX")
        self.code_input.setMinimumHeight(44)
        self.code_input.returnPressed.connect(self._connect)
        layout.addWidget(self.code_input)
        self.connect_status = QLabel("")
        self.connect_status.setWordWrap(True)
        layout.addWidget(self.connect_status)
        layout.addStretch()
        self.connect_button = QPushButton("Подключить приложение")
        self.connect_button.setObjectName("recordButton")
        self.connect_button.setMinimumHeight(44)
        self.connect_button.clicked.connect(self._connect)
        layout.addWidget(self.connect_button)

    def _add_finish_step(self):
        _, layout = self._page(
            "Шаг 3. Всё готово!",
            "Подключение настроено. Теперь при входе в Zoom или Телемост запись "
            "начнётся автоматически, а после встречи вы получите разбор в Telegram.\n\n"
            "Перед первой настоящей встречей рекомендуем сделать короткую тестовую "
            "запись и проверить микрофон и звук собеседников."
        )
        if sys.platform == "darwin":
            mac_help = QLabel(
                "На MacBook дополнительно разрешите доступ к микрофону. Для записи "
                "собеседников выберите виртуальное аудиоустройство BlackHole в "
                "источниках звука приложения."
            )
            mac_help.setWordWrap(True)
            mac_help.setStyleSheet("color: #F1642E; font-size: 12px;")
            layout.addWidget(mac_help)
        layout.addStretch()
        button = QPushButton("Перейти к приложению")
        button.setObjectName("recordButton")
        button.setMinimumHeight(44)
        button.clicked.connect(self.accept)
        layout.addWidget(button)

    def _go(self, index):
        self.pages.setCurrentIndex(index)
        self.step_label.setText(f"ШАГ {min(index + 1, 3)} ИЗ 3")
        if index == 2:
            self.code_input.setFocus()

    def _connect(self):
        code = self.code_input.text().strip().upper()
        if not code.startswith("SR-") or len(code) < 8:
            self.connect_status.setText("Введите код из сообщения бота в формате SR-XXXX-XXXX.")
            self.connect_status.setStyleSheet("color: #F1642E;")
            return
        self.connect_button.setEnabled(False)
        self.connect_status.setText("Проверяю код и подключение к серверу…")
        self.connect_status.setStyleSheet("color: #667085;")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            base_url = self.config.get("remote", "server_url")
            result = ApiClient.exchange_code(base_url, code)
            self.config.set("remote", "api_token", result["token"])
            self.config.set("remote", "chat_id", str(result["chat_id"]))
            self.config.set("remote", "allow_obsidian", False)
            self.config.set("remote", "allow_tasks", False)
            self.config.set("remote", "setup_complete", True)
            ApiClient(base_url, result["token"]).me()
        except Exception as exc:
            self.config.set("remote", "api_token", "")
            self.config.set("remote", "setup_complete", False)
            self.connect_status.setText(str(exc))
            self.connect_status.setStyleSheet("color: #F1642E;")
            self.connect_button.setEnabled(True)
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._go(3)
