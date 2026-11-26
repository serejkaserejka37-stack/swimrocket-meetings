from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QComboBox, QSpinBox, QCheckBox, QLineEdit, QListWidget,
    QPushButton, QFileDialog, QGroupBox, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt


class SettingsDialog(QDialog):
    """Settings dialog for configuring recording and transcription options."""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Настройки SwimRocket")
        self.setMinimumSize(760, 600)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # General Tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)

        recording_group = QGroupBox("Запись")
        recording_form = QFormLayout(recording_group)

        self.min_recording_spin = QSpinBox()
        self.min_recording_spin.setRange(0, 300)
        self.min_recording_spin.setSuffix(" сек.")
        self.min_recording_spin.setSpecialValueText("Сохранять все записи")
        self.min_recording_spin.setToolTip(
            "Automatically discard recordings shorter than this duration.\n"
            "Set to 0 to keep all recordings regardless of length."
        )
        recording_form.addRow("Минимальная длина записи:", self.min_recording_spin)

        self.auto_record_cb = QCheckBox("Начинать запись при входе во встречу")
        self.auto_record_cb.setToolTip(
            "Automatically start recording when a checked app in the\n"
            "per-app picker becomes active (joins a call).\n"
            "Requires per-app capture mode on Windows 11."
        )
        recording_form.addRow(self.auto_record_cb)

        self.auto_record_threshold_spin = QSpinBox()
        self.auto_record_threshold_spin.setRange(0, 60)
        self.auto_record_threshold_spin.setSuffix(" сек.")
        self.auto_record_threshold_spin.setSpecialValueText("Начинать сразу")
        self.auto_record_threshold_spin.setToolTip(
            "Require sustained app activity for this many seconds before\n"
            "auto-recording actually starts. Prevents brief sounds (like\n"
            "a Teams message chime) from kicking off a recording that\n"
            "then silence-stops. Set to 0 to disable the threshold."
        )
        recording_form.addRow("Задержка автозаписи:", self.auto_record_threshold_spin)

        self.auto_transcribe_cb = QCheckBox("Расшифровывать после записи")
        self.auto_transcribe_cb.setToolTip(
            "When checked, TalkTrack runs Whisper on the recording as soon\n"
            "as it stops. When unchecked, transcripts must be kicked off\n"
            "manually from the Transcript tab. Auto-summary is skipped too."
        )
        recording_form.addRow(self.auto_transcribe_cb)

        self.silence_auto_stop_cb = QCheckBox("Останавливать запись после длительной тишины")
        self.silence_auto_stop_cb.setToolTip(
            "Automatically stop recording when the system/app audio\n"
            "has been silent for the configured duration.\n"
            "Only monitors remote audio, not your microphone."
        )
        recording_form.addRow(self.silence_auto_stop_cb)

        self.silence_duration_spin = QSpinBox()
        self.silence_duration_spin.setRange(5, 300)
        self.silence_duration_spin.setSuffix(" сек.")
        self.silence_duration_spin.setToolTip(
            "How many seconds of silence on the remote audio\n"
            "before auto-stopping the recording."
        )
        recording_form.addRow("Длительность тишины:", self.silence_duration_spin)

        self.mic_mute_on_start_cb = QCheckBox("Начинать запись с выключенным микрофоном")
        self.mic_mute_on_start_cb.setToolTip(
            "When checked, new recordings begin with the mic muted.\n"
            "Toggle mute anytime during recording via the Mute button.\n"
            "Applies to both mics when dual-mic mode is configured."
        )
        recording_form.addRow(self.mic_mute_on_start_cb)

        # Совместимость со старыми конфигами. Опция скрыта: сворачивание
        # всегда оставляет приложение в панели задач Windows.
        self.minimize_to_tray_cb = QCheckBox("")
        self.minimize_to_tray_cb.setVisible(False)

        general_layout.addWidget(recording_group)
        general_layout.addStretch()

        tabs.addTab(general_tab, "Основные")

        # Audio Tab
        audio_tab = QWidget()
        audio_layout = QVBoxLayout(audio_tab)

        audio_group = QGroupBox("Настройки аудио")
        audio_form = QFormLayout(audio_group)

        self.sample_rate_combo = QComboBox()
        self.sample_rate_combo.addItem("16000 Hz (recommended for speech)", 16000)
        self.sample_rate_combo.addItem("22050 Hz", 22050)
        self.sample_rate_combo.addItem("44100 Hz (CD quality)", 44100)
        self.sample_rate_combo.addItem("48000 Hz", 48000)
        audio_form.addRow("Частота дискретизации:", self.sample_rate_combo)

        self.channels_combo = QComboBox()
        self.channels_combo.addItem("Mono (recommended)", 1)
        self.channels_combo.addItem("Стерео", 2)
        audio_form.addRow("Каналы:", self.channels_combo)

        self.mic_count_combo = QComboBox()
        self.mic_count_combo.addItem("1 микрофон", 1)
        self.mic_count_combo.addItem("2 микрофона", 2)
        self.mic_count_combo.setToolTip(
            "Use 2 microphones to capture from both your main mic\n"
            "and headset mic simultaneously. Both are mixed into\n"
            "a single microphone track."
        )
        audio_form.addRow("Микрофонные входы:", self.mic_count_combo)

        audio_layout.addWidget(audio_group)

        # Hidden devices group
        hidden_group = QGroupBox("Скрытые устройства")
        hidden_layout = QVBoxLayout(hidden_group)

        hidden_help = QLabel(
            "Hide audio devices whose name contains any of these keywords.\n"
            "Matching devices won't appear in the mic or system audio dropdowns."
        )
        hidden_help.setWordWrap(True)
        hidden_help.setStyleSheet("color: #667085; font-size: 12px;")
        hidden_layout.addWidget(hidden_help)

        self.hidden_devices_list = QListWidget()
        self.hidden_devices_list.setMaximumHeight(100)
        hidden_layout.addWidget(self.hidden_devices_list)

        hidden_btn_row = QHBoxLayout()
        self.hidden_device_input = QLineEdit()
        self.hidden_device_input.setPlaceholderText("e.g. Voicemeeter, Virtual Cable")
        self.hidden_device_input.returnPressed.connect(self._add_hidden_device)
        hidden_btn_row.addWidget(self.hidden_device_input)

        add_btn = QPushButton("Добавить")
        add_btn.setFixedWidth(60)
        add_btn.clicked.connect(self._add_hidden_device)
        hidden_btn_row.addWidget(add_btn)

        remove_btn = QPushButton("Удалить")
        remove_btn.setFixedWidth(70)
        remove_btn.clicked.connect(self._remove_hidden_device)
        hidden_btn_row.addWidget(remove_btn)

        hidden_layout.addLayout(hidden_btn_row)
        audio_layout.addWidget(hidden_group)

        audio_layout.addStretch()

        tabs.addTab(audio_tab, "Аудио")

        # Output Tab
        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)

        output_group = QGroupBox("Сохранение записей")
        output_form = QFormLayout(output_group)

        dir_row = QHBoxLayout()
        self.output_dir_edit = QLineEdit()
        dir_row.addWidget(self.output_dir_edit)
        self.browse_btn = QPushButton("Выбрать…")
        self.browse_btn.clicked.connect(self._browse_output_dir)
        dir_row.addWidget(self.browse_btn)
        output_form.addRow("Папка для записей:", dir_row)

        self.format_combo = QComboBox()
        self.format_combo.addItem("WAV (без потерь)", "wav")
        self.format_combo.addItem("MP3 (сжатие, требуется FFmpeg)", "mp3")
        output_form.addRow("Формат файла:", self.format_combo)

        output_layout.addWidget(output_group)
        output_layout.addStretch()

        tabs.addTab(output_tab, "Файлы")

        # Transcription Tab
        transcription_tab = QWidget()
        transcription_layout = QVBoxLayout(transcription_tab)

        whisper_group = QGroupBox("Расшифровка Whisper")
        whisper_form = QFormLayout(whisper_group)

        self.model_combo = QComboBox()
        self.model_combo.addItem("tiny (самая быстрая, менее точная)", "tiny")
        self.model_combo.addItem("base (быстрая, хорошая точность)", "base")
        self.model_combo.addItem("small (сбалансированная)", "small")
        self.model_combo.addItem("medium (медленнее, точнее)", "medium")
        self.model_combo.addItem("large-v3 (самая медленная и точная)", "large-v3")
        self.model_combo.addItem("large-v3-turbo (быстрая, почти как large-v3)", "large-v3-turbo")
        whisper_form.addRow("Размер модели:", self.model_combo)

        self.device_combo = QComboBox()
        self.device_combo.addItem("CPU", "cpu")
        self.device_combo.addItem("CUDA (NVIDIA GPU)", "cuda")
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        whisper_form.addRow("Устройство обработки:", self.device_combo)

        self.gpu_status_label = QLabel("")
        self.gpu_status_label.setWordWrap(True)
        self.gpu_status_label.setOpenExternalLinks(True)
        self.gpu_status_label.setVisible(False)
        whisper_form.addRow("", self.gpu_status_label)

        self.language_edit = QLineEdit()
        self.language_edit.setPlaceholderText("автоопределение (оставьте пустым)")
        whisper_form.addRow("Язык:", self.language_edit)

        self.min_duration_spin = QSpinBox()
        self.min_duration_spin.setRange(0, 300)
        self.min_duration_spin.setSuffix(" сек.")
        self.min_duration_spin.setSpecialValueText("Всегда расшифровывать")
        self.min_duration_spin.setToolTip(
            "Skip auto-transcription for recordings shorter than this duration.\n"
            "Set to 0 to always auto-transcribe."
        )
        whisper_form.addRow("Минимальная длина для расшифровки:", self.min_duration_spin)

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 16)
        self.batch_size_spin.setSpecialValueText("1 (последовательно)")
        self.batch_size_spin.setToolTip(
            "1 (the default) is the classic sequential path and keeps cross-chunk\n"
            "context. Higher values decode VAD-chunked audio in parallel, which is\n"
            "faster on long recordings and especially on CUDA, but drops that\n"
            "context and uses more RAM."
        )
        whisper_form.addRow("Размер пакета:", self.batch_size_spin)

        transcription_layout.addWidget(whisper_group)

        # Diarization group
        diarization_group = QGroupBox("Разделение спикеров")
        diarization_form = QFormLayout(diarization_group)

        self.diarization_enabled = QCheckBox("Определять разных спикеров")
        diarization_form.addRow(self.diarization_enabled)

        self.hf_token_edit = QLineEdit()
        self.hf_token_edit.setPlaceholderText("hf_xxxxxxxxxxxx")
        self.hf_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        diarization_form.addRow("Токен HuggingFace:", self.hf_token_edit)

        token_help = QLabel(
            '<a href="https://huggingface.co/settings/tokens" '
            'style="color: #F1642E;">Получить токен</a> | '
            '<a href="https://huggingface.co/pyannote/speaker-diarization-community-1" '
            'style="color: #F1642E;">Принять условия модели</a>'
        )
        token_help.setOpenExternalLinks(True)
        diarization_form.addRow("", token_help)

        self.setup_wizard_btn = QPushButton("Мастер настройки…")
        self.setup_wizard_btn.setToolTip("Open the step-by-step diarization setup guide")
        self.setup_wizard_btn.clicked.connect(self._open_setup_wizard)
        diarization_form.addRow("", self.setup_wizard_btn)

        self.min_speakers_spin = QSpinBox()
        self.min_speakers_spin.setRange(0, 20)
        self.min_speakers_spin.setSpecialValueText("Авто")
        diarization_form.addRow("Минимум спикеров:", self.min_speakers_spin)

        self.max_speakers_spin = QSpinBox()
        self.max_speakers_spin.setRange(0, 20)
        self.max_speakers_spin.setSpecialValueText("Авто")
        diarization_form.addRow("Максимум спикеров:", self.max_speakers_spin)

        transcription_layout.addWidget(diarization_group)
        transcription_layout.addStretch()

        tabs.addTab(transcription_tab, "Расшифровка")

        # AI Assistant Tab
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)

        ai_group = QGroupBox("Поставщик AI")
        ai_form = QFormLayout(ai_group)

        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItem("Не использовать", "none")
        self.ai_provider_combo.addItem("Claude (Anthropic)", "claude")
        self.ai_provider_combo.addItem("OpenAI", "openai")
        self.ai_provider_combo.addItem("Grok (xAI)", "grok")
        self.ai_provider_combo.addItem("Gemini (Google)", "gemini")
        self.ai_provider_combo.addItem("Mistral", "mistral")
        self.ai_provider_combo.addItem("Groq (GroqCloud)", "groq")
        self.ai_provider_combo.addItem("Локальная модель", "local")
        self.ai_provider_combo.currentIndexChanged.connect(self._on_ai_provider_changed)
        ai_form.addRow("Поставщик:", self.ai_provider_combo)

        self.ai_package_label = QLabel("")
        self.ai_package_label.setWordWrap(True)
        self.ai_package_label.setVisible(False)
        ai_form.addRow("", self.ai_package_label)

        self.ai_api_key_label = QLabel("API-ключ:")
        self.ai_api_key = QLineEdit()
        self.ai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key.setPlaceholderText("Введите API-ключ…")
        self.ai_api_key.textChanged.connect(self._update_api_key_status)
        ai_form.addRow(self.ai_api_key_label, self.ai_api_key)

        self.ai_key_status = QLabel("")
        self.ai_key_status.setVisible(False)
        ai_form.addRow("", self.ai_key_status)

        self.ai_model = QComboBox()
        self.ai_model.setEditable(True)
        ai_form.addRow("Модель:", self.ai_model)

        self.ai_local_label = QLabel("Локальная модель:")
        self.ai_local_path = QLineEdit()
        self.ai_local_path.setPlaceholderText("Путь к GGUF-модели…")
        self.ai_local_browse = QPushButton("Выбрать…")
        self.ai_local_browse.clicked.connect(self._browse_local_model)
        local_row = QHBoxLayout()
        local_row.addWidget(self.ai_local_path)
        local_row.addWidget(self.ai_local_browse)
        ai_form.addRow(self.ai_local_label, local_row)

        self.ai_test_btn = QPushButton("Проверить подключение")
        self.ai_test_btn.clicked.connect(self._test_ai_connection)
        ai_form.addRow("", self.ai_test_btn)

        ai_layout.addWidget(ai_group)

        # Auto features group
        features_group = QGroupBox("Автоматические действия")
        features_form = QFormLayout(features_group)
        self.auto_summarize_cb = QCheckBox("Создавать сводку после расшифровки")
        features_form.addRow(self.auto_summarize_cb)
        ai_layout.addWidget(features_group)

        ai_layout.addStretch()
        tabs.addTab(ai_tab, "AI-помощник")

        # Серверная обработка SwimRocket. Пароли и SSH-ключи здесь не хранятся:
        # используется системный OpenSSH и ключи конкретного пользователя.
        remote_tab = QWidget()
        remote_layout = QVBoxLayout(remote_tab)
        remote_group = QGroupBox("SwimRocket — серверная обработка")
        remote_form = QFormLayout(remote_group)
        self.remote_server_url_edit = QLineEdit()
        remote_form.addRow("API-адрес:", self.remote_server_url_edit)
        self.remote_host_edit = QLineEdit()
        self.remote_host_edit.setPlaceholderText("user@host")
        remote_form.addRow("SSH-адрес (для владельца):", self.remote_host_edit)
        self.remote_directory_edit = QLineEdit()
        remote_form.addRow("Папка на сервере:", self.remote_directory_edit)
        self.remote_telegram_cb = QCheckBox("Отправлять сводку в Telegram")
        remote_form.addRow(self.remote_telegram_cb)
        self.remote_setup_btn = QPushButton("Открыть мастер подключения")
        self.remote_setup_btn.clicked.connect(self._open_onboarding)
        remote_form.addRow("", self.remote_setup_btn)
        remote_help = QLabel(
            "Для подключения коллег используется одноразовый код из бота. "
            "Obsidian и личные SSH-ключи в приложение не встраиваются."
        )
        remote_help.setWordWrap(True)
        remote_layout.addWidget(remote_group)
        remote_layout.addWidget(remote_help)
        remote_layout.addStretch()
        tabs.addTab(remote_tab, "Сервер")

        layout.setSpacing(12)
        for tab_layout in (general_layout, audio_layout, output_layout,
                           transcription_layout, ai_layout, remote_layout):
            tab_layout.setContentsMargins(16, 16, 16, 16)
            tab_layout.setSpacing(14)
        for form in self.findChildren(QFormLayout):
            form.setContentsMargins(14, 20, 14, 14)
            form.setHorizontalSpacing(18)
            form.setVerticalSpacing(11)
        tabs.setUsesScrollButtons(True)
        layout.addWidget(tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setMinimumSize(110, 38)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("Сохранить")
        ok_btn.setMinimumSize(110, 38)
        ok_btn.clicked.connect(self._save_and_close)
        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def _load_settings(self):
        # General
        min_rec = self.config.get("general", "min_recording_length")
        self.min_recording_spin.setValue(min_rec if min_rec else 0)
        self.auto_record_cb.setChecked(self.config.get("general", "auto_record"))
        self.auto_record_threshold_spin.setValue(
            self.config.get("general", "auto_record_threshold")
        )
        self.auto_transcribe_cb.setChecked(self.config.get("general", "auto_transcribe"))
        self.silence_auto_stop_cb.setChecked(self.config.get("general", "silence_auto_stop"))
        self.silence_duration_spin.setValue(self.config.get("general", "silence_duration"))
        self.mic_mute_on_start_cb.setChecked(self.config.get("audio", "mic_mute_on_start"))
        self.minimize_to_tray_cb.setChecked(self.config.get("general", "minimize_to_tray"))

        # Audio
        sr = self.config.get("audio", "sample_rate")
        idx = self.sample_rate_combo.findData(sr)
        if idx >= 0:
            self.sample_rate_combo.setCurrentIndex(idx)

        ch = self.config.get("audio", "channels")
        idx = self.channels_combo.findData(ch)
        if idx >= 0:
            self.channels_combo.setCurrentIndex(idx)

        mic_count = self.config.get("audio", "mic_count")
        idx = self.mic_count_combo.findData(mic_count)
        if idx >= 0:
            self.mic_count_combo.setCurrentIndex(idx)

        # Hidden devices
        hidden = self.config.get("audio", "hidden_devices") or []
        for pattern in hidden:
            self.hidden_devices_list.addItem(pattern)

        # Output
        self.output_dir_edit.setText(self.config.get("output", "directory"))

        fmt = self.config.get("output", "format")
        idx = self.format_combo.findData(fmt)
        if idx >= 0:
            self.format_combo.setCurrentIndex(idx)

        # Transcription
        model = self.config.get("transcription", "model_size")
        idx = self.model_combo.findData(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        device = self.config.get("transcription", "device")
        idx = self.device_combo.findData(device)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)

        lang = self.config.get("transcription", "language")
        if lang:
            self.language_edit.setText(lang)

        self._on_device_changed(self.device_combo.currentIndex())

        min_dur = self.config.get("transcription", "min_duration")
        self.min_duration_spin.setValue(min_dur if min_dur else 0)

        batch_size = self.config.get("transcription", "batch_size")
        self.batch_size_spin.setValue(batch_size if batch_size else 1)

        # Diarization
        self.diarization_enabled.setChecked(self.config.get("diarization", "enabled"))
        self.hf_token_edit.setText(self.config.get("diarization", "hf_token") or "")

        min_spk = self.config.get("diarization", "min_speakers")
        self.min_speakers_spin.setValue(min_spk if min_spk else 0)

        max_spk = self.config.get("diarization", "max_speakers")
        self.max_speakers_spin.setValue(max_spk if max_spk else 0)

        # AI — load per-provider settings cache
        self._current_provider = None
        self._provider_settings = dict(self.config.get("ai", "provider_settings") or {})

        # Migrate: if there's an existing api_key but no provider_settings entry,
        # seed the current provider's settings from the flat fields
        provider = self.config.get("ai", "provider")
        if provider != "none" and provider not in self._provider_settings:
            self._provider_settings[provider] = {
                "api_key": self.config.get("ai", "api_key") or "",
                "model": self.config.get("ai", "model") or "",
                "local_model_path": self.config.get("ai", "local_model_path") or "",
            }

        idx = self.ai_provider_combo.findData(provider)
        if idx >= 0:
            self.ai_provider_combo.setCurrentIndex(idx)
        self.auto_summarize_cb.setChecked(self.config.get("ai", "auto_summarize"))
        self._on_ai_provider_changed(self.ai_provider_combo.currentIndex())

        self.remote_server_url_edit.setText(self.config.get("remote", "server_url") or "")
        self.remote_host_edit.setText(self.config.get("remote", "host") or "")
        self.remote_directory_edit.setText(self.config.get("remote", "directory") or "")
        self.remote_telegram_cb.setChecked(bool(self.config.get("remote", "send_telegram")))

    def _save_and_close(self):
        self.config.set("general", "min_recording_length", self.min_recording_spin.value())
        self.config.set("general", "auto_record", self.auto_record_cb.isChecked())
        self.config.set(
            "general", "auto_record_threshold", self.auto_record_threshold_spin.value()
        )
        self.config.set("general", "auto_transcribe", self.auto_transcribe_cb.isChecked())
        self.config.set("general", "silence_auto_stop", self.silence_auto_stop_cb.isChecked())
        self.config.set("general", "silence_duration", self.silence_duration_spin.value())
        self.config.set("audio", "mic_mute_on_start", self.mic_mute_on_start_cb.isChecked())
        self.config.set("general", "minimize_to_tray", self.minimize_to_tray_cb.isChecked())

        self.config.set("audio", "sample_rate", self.sample_rate_combo.currentData())
        self.config.set("audio", "channels", self.channels_combo.currentData())
        self.config.set("audio", "mic_count", self.mic_count_combo.currentData())

        hidden = []
        for i in range(self.hidden_devices_list.count()):
            hidden.append(self.hidden_devices_list.item(i).text())
        self.config.set("audio", "hidden_devices", hidden)
        self.config.set("output", "directory", self.output_dir_edit.text())
        self.config.set("output", "format", self.format_combo.currentData())
        self.config.set("transcription", "model_size", self.model_combo.currentData())
        self.config.set("transcription", "device", self.device_combo.currentData())

        lang = self.language_edit.text().strip()
        self.config.set("transcription", "language", lang if lang else None)
        self.config.set("transcription", "min_duration", self.min_duration_spin.value())
        self.config.set("transcription", "batch_size", self.batch_size_spin.value())

        self.config.set("diarization", "enabled", self.diarization_enabled.isChecked())
        self.config.set("diarization", "hf_token", self.hf_token_edit.text().strip())

        min_spk = self.min_speakers_spin.value()
        self.config.set("diarization", "min_speakers", min_spk if min_spk > 0 else None)

        max_spk = self.max_speakers_spin.value()
        self.config.set("diarization", "max_speakers", max_spk if max_spk > 0 else None)

        # AI — install package if needed before saving
        provider_type = self.ai_provider_combo.currentData()
        if provider_type != "none":
            if not self._install_provider_package(provider_type):
                return  # User cancelled install, don't save

        # Save current provider's fields into the cache before persisting
        self._save_current_provider_settings()

        self.config.set("ai", "provider", provider_type)
        # Set the flat fields to the active provider's values (used at runtime)
        active = self._provider_settings.get(provider_type, {})
        self.config.set("ai", "api_key", active.get("api_key", ""))
        self.config.set("ai", "model", active.get("model", ""))
        self.config.set("ai", "local_model_path", active.get("local_model_path", ""))
        self.config.set("ai", "auto_summarize", self.auto_summarize_cb.isChecked())
        # Persist all provider settings so switching back restores them
        self.config.set("ai", "provider_settings", self._provider_settings)
        self.config.set("remote", "server_url", self.remote_server_url_edit.text().strip())
        self.config.set("remote", "host", self.remote_host_edit.text().strip())
        self.config.set("remote", "directory", self.remote_directory_edit.text().strip())
        self.config.set("remote", "send_telegram", self.remote_telegram_cb.isChecked())

        self.config.save()
        self.accept()

    def _open_onboarding(self):
        from app.ui.onboarding_wizard import OnboardingWizard
        wizard = OnboardingWizard(self.config, self)
        wizard.exec()

    def _open_setup_wizard(self):
        from app.ui.diarization_setup import DiarizationSetupWizard
        wizard = DiarizationSetupWizard(self.config, self)
        if wizard.exec():
            # Reload diarization settings after wizard saves
            self.diarization_enabled.setChecked(self.config.get("diarization", "enabled"))
            self.hf_token_edit.setText(self.config.get("diarization", "hf_token") or "")

    def _on_ai_provider_changed(self, index):
        # Save current provider's settings before switching
        self._save_current_provider_settings()

        provider = self.ai_provider_combo.currentData()
        self._current_provider = provider
        is_api = provider in ("claude", "openai", "grok", "gemini", "mistral", "groq")
        is_local = provider == "local"
        self.ai_api_key.setVisible(is_api)
        self.ai_api_key_label.setVisible(is_api)
        self.ai_local_path.setVisible(is_local)
        self.ai_local_browse.setVisible(is_local)
        self.ai_local_label.setVisible(is_local)
        self.ai_model.clear()
        if provider == "claude":
            self.ai_model.addItems(["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"])
        elif provider == "openai":
            self.ai_model.addItems(["gpt-4o", "gpt-4o-mini", "gpt-4.1"])
        elif provider == "grok":
            self.ai_model.addItems(["grok-3", "grok-3-mini", "grok-2"])
        elif provider == "gemini":
            self.ai_model.addItems(["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"])
        elif provider == "mistral":
            self.ai_model.addItems(["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"])
        elif provider == "groq":
            # Groq shut down llama-3.3-70b-versatile / llama-3.1-8b-instant on
            # 2026-08-16 (free + developer tier). Production text models only;
            # the combo is editable, so any newer ID can be typed in.
            self.ai_model.addItems([
                "openai/gpt-oss-120b",
                "openai/gpt-oss-20b",
                "qwen/qwen3.6-27b",
            ])
        elif provider == "local":
            self.ai_model.addItem("(set path below)")

        # Restore this provider's saved settings
        self._restore_provider_settings(provider)

        # Check if package is installed
        self._check_provider_package(provider)

    def _save_current_provider_settings(self):
        """Save the current provider's API key, model, and local path to the in-memory cache."""
        prev = getattr(self, "_current_provider", None)
        if not prev or prev == "none":
            return
        self._provider_settings[prev] = {
            "api_key": self.ai_api_key.text(),
            "model": self.ai_model.currentText(),
            "local_model_path": self.ai_local_path.text(),
        }

    def _restore_provider_settings(self, provider):
        """Restore a provider's saved API key, model, and local path."""
        saved = self._provider_settings.get(provider, {})
        self.ai_api_key.setText(saved.get("api_key", ""))
        self.ai_local_path.setText(saved.get("local_model_path", ""))
        saved_model = saved.get("model", "")
        if saved_model:
            idx = self.ai_model.findText(saved_model)
            if idx >= 0:
                self.ai_model.setCurrentIndex(idx)
            else:
                self.ai_model.setEditText(saved_model)
        self._update_api_key_status()

    def _update_api_key_status(self):
        """Show a status indicator for whether an API key is configured."""
        provider = self.ai_provider_combo.currentData()
        is_api = provider in ("claude", "openai", "grok", "gemini", "mistral", "groq")
        if not is_api:
            self.ai_key_status.setVisible(False)
            return
        if self.ai_api_key.text():
            masked = self.ai_api_key.text()[:4] + "..." + self.ai_api_key.text()[-4:]
            self.ai_key_status.setText(
                f'<span style="color: #34C759;">API key configured ({masked})</span>'
            )
        else:
            self.ai_key_status.setText(
                '<span style="color: #FDE676;">No API key set</span>'
            )
        self.ai_key_status.setVisible(True)

    def _on_device_changed(self, index):
        device = self.device_combo.currentData()
        if device != "cuda":
            self.gpu_status_label.setVisible(False)
            return

        from app.utils.dependency_checker import DependencyChecker
        info = DependencyChecker.detect_gpu_cuda()

        if info["torch_has_cuda"]:
            self.gpu_status_label.setText(
                f'<span style="color: #34C759;">&#x2705; {info["gpu_name"]} ready '
                f'(CUDA {info["cuda_version"]})</span>'
            )
            self.gpu_status_label.setVisible(True)
        elif info["has_nvidia_gpu"]:
            self.gpu_status_label.setText(
                f'<span style="color: #FDE676;">&#x26a0;&#xfe0f; {info["gpu_name"]} detected but '
                f'PyTorch is CPU-only.<br>'
                f'To enable GPU acceleration, run in your terminal:<br>'
                f'<code>pip install torch torchaudio --index-url '
                f'https://download.pytorch.org/whl/cu126</code><br>'
                f'Then restart TalkTrack. Until then, transcription will use CPU.</span>'
            )
            self.gpu_status_label.setVisible(True)
        else:
            self.gpu_status_label.setText(
                '<span style="color: #F1642E;">&#x274c; No NVIDIA GPU detected. '
                'CUDA requires an NVIDIA graphics card.</span>'
            )
            self.gpu_status_label.setVisible(True)

    def _check_provider_package(self, provider):
        """Show install status for the selected provider's package."""
        if provider == "none":
            self.ai_package_label.setVisible(False)
            return

        from app.utils.package_installer import is_package_installed, get_package_info
        info = get_package_info(provider)
        if info is None:
            self.ai_package_label.setVisible(False)
            return

        pip_package, display_name = info
        if is_package_installed(provider):
            self.ai_package_label.setText(
                f'<span style="color: #34C759;">{display_name} is installed.</span>'
            )
        else:
            self.ai_package_label.setText(
                f'<span style="color: #FDE676;">{display_name} is not installed. '
                f'It will be installed automatically when you test the connection or save.</span>'
            )
        self.ai_package_label.setVisible(True)

    def _install_provider_package(self, provider):
        """Install the required package for a provider. Returns True if ready."""
        from app.utils.package_installer import is_package_installed, get_package_info, install_package
        if is_package_installed(provider):
            return True

        info = get_package_info(provider)
        if info is None:
            return True

        pip_package, display_name = info
        reply = QMessageBox.question(
            self,
            "Установка необходимого пакета",
            f"The {display_name} package is required for this provider.\n\n"
            f"Package: {pip_package}\n\n"
            f"Install it now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False

        self.ai_package_label.setText(
            f'<span style="color: #F1642E;">Installing {display_name}...</span>'
        )
        self.ai_package_label.setVisible(True)
        QApplication.processEvents()

        success, output = install_package(pip_package)
        if success:
            self.ai_package_label.setText(
                f'<span style="color: #34C759;">{display_name} installed successfully.</span>'
            )
            return True
        else:
            QMessageBox.critical(
                self, "Ошибка установки",
                f"Failed to install {pip_package}:\n\n{output[:500]}"
            )
            self.ai_package_label.setText(
                f'<span style="color: #F1642E;">Installation failed.</span>'
            )
            return False

    def _browse_local_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл модели", "", "Файлы GGUF (*.gguf);;Все файлы (*)"
        )
        if path:
            self.ai_local_path.setText(path)

    def _test_ai_connection(self):
        provider_type = self.ai_provider_combo.currentData()
        if provider_type == "none":
            QMessageBox.information(self, "AI", "Поставщик не выбран.")
            return

        # Install package if needed
        if not self._install_provider_package(provider_type):
            return

        from app.ai.provider_factory import create_provider
        config = {
            "provider": provider_type,
            "api_key": self.ai_api_key.text(),
            "model": self.ai_model.currentText(),
            "local_model_path": self.ai_local_path.text(),
        }
        try:
            provider = create_provider(config)
            if provider is None:
                QMessageBox.information(self, "AI", "Поставщик не выбран.")
                return
            # Call complete() directly (not test_connection, which swallows
            # the exception) so the real auth/model error reaches the dialog.
            result = provider.complete("Say 'ok'.", "")
            if result:
                QMessageBox.information(self, "AI", "Подключение успешно!")
            else:
                QMessageBox.warning(self, "AI", "Ошибка подключения: пустой ответ.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка AI", str(e))

    def _add_hidden_device(self):
        text = self.hidden_device_input.text().strip()
        if not text:
            return
        # Avoid duplicates
        for i in range(self.hidden_devices_list.count()):
            if self.hidden_devices_list.item(i).text().lower() == text.lower():
                return
        self.hidden_devices_list.addItem(text)
        self.hidden_device_input.clear()

    def _remove_hidden_device(self):
        for item in self.hidden_devices_list.selectedItems():
            self.hidden_devices_list.takeItem(self.hidden_devices_list.row(item))

    def _browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Выберите папку для записей", self.output_dir_edit.text()
        )
        if directory:
            self.output_dir_edit.setText(directory)
