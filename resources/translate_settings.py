"""Русские подписи вкладки настроек SwimRocket."""
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "app" / "ui" / "settings_dialog.py"
text = path.read_text(encoding="utf-8")
translations = {
    "General": "Основные",
    "Audio": "Аудио",
    "Output": "Файлы",
    "Transcription": "Расшифровка",
    "AI Assistant": "AI-помощник",
    "Recording": "Запись",
    "Audio Settings": "Настройки аудио",
    "Output Settings": "Сохранение записей",
    "Whisper Transcription": "Расшифровка Whisper",
    "Speaker Diarization": "Разделение спикеров",
    "AI Provider": "Поставщик AI",
    "Automatic Features": "Автоматические действия",
    "Min recording length:": "Минимальная длина записи:",
    "Auto-record when selected app starts a call": "Начинать запись при входе во встречу",
    "Auto-record threshold:": "Задержка автозаписи:",
    "Automatically transcribe after recording": "Расшифровывать после записи",
    "Auto-stop recording after sustained silence": "Останавливать запись после длительной тишины",
    "Silence duration:": "Длительность тишины:",
    "Start recordings with microphone muted": "Начинать запись с выключенным микрофоном",
    "When minimized, hide to system tray": "При сворачивании скрывать в системный трей",
    "Sample Rate:": "Частота дискретизации:",
    "Channels:": "Каналы:",
    "Microphone inputs:": "Микрофонные входы:",
    "Hidden Devices": "Скрытые устройства",
    "Add": "Добавить",
    "Remove": "Удалить",
    "Browse...": "Выбрать…",
    "Output Directory:": "Папка для записей:",
    "Output Format:": "Формат файла:",
    "WAV (lossless)": "WAV (без потерь)",
    "MP3 (compressed, requires FFmpeg)": "MP3 (сжатие, требуется FFmpeg)",
    "Model Size:": "Размер модели:",
    "Compute Device:": "Устройство обработки:",
    "Language:": "Язык:",
    "Min duration to auto-transcribe:": "Минимальная длина для расшифровки:",
    "Batch size:": "Размер пакета:",
    "Enable speaker diarization": "Определять разных спикеров",
    "HuggingFace Token:": "Токен HuggingFace:",
    "Setup Wizard...": "Мастер настройки…",
    "Min Speakers:": "Минимум спикеров:",
    "Max Speakers:": "Максимум спикеров:",
    "Provider:": "Поставщик:",
    "API Key:": "API-ключ:",
    "Model:": "Модель:",
    "Local Model:": "Локальная модель:",
    "Test Connection": "Проверить подключение",
    "Generate summary after transcription": "Создавать сводку после расшифровки",
    " seconds": " сек.",
    "Keep all recordings": "Сохранять все записи",
    "Start immediately": "Начинать сразу",
    "Always transcribe": "Всегда расшифровывать",
    "1 (sequential / classic)": "1 (последовательно)",
    "Auto": "Авто",
    "auto-detect (leave empty)": "автоопределение (оставьте пустым)",
    "Enter API key...": "Введите API-ключ…",
    "Path to GGUF model file...": "Путь к GGUF-модели…",
    "None (disabled)": "Не использовать",
    "Local Model": "Локальная модель",
    "tiny (fastest, least accurate)": "tiny (самая быстрая, менее точная)",
    "base (fast, good accuracy)": "base (быстрая, хорошая точность)",
    "small (balanced)": "small (сбалансированная)",
    "medium (slower, better accuracy)": "medium (медленнее, точнее)",
    "large-v3 (slowest, best accuracy)": "large-v3 (самая медленная и точная)",
    "large-v3-turbo (near large-v3 accuracy, much faster)": "large-v3-turbo (быстрая, почти как large-v3)",
    "1 microphone": "1 микрофон",
    "2 microphones": "2 микрофона",
}
for old, new in translations.items():
    text = text.replace(f'"{old}"', f'"{new}"')
text = text.replace("Get token", "Получить токен")
text = text.replace("Accept model terms", "Принять условия модели")
text = text.replace(
    "Hide audio devices whose name contains any of these keywords.\\n"
    "Matching devices won't appear in the mic or system audio dropdowns.",
    "Скрывать аудиоустройства, в названии которых есть эти слова.\\n"
    "Они не появятся в списках микрофонов и системного звука.",
)
path.write_text(text, encoding="utf-8")
print(path)
