"""Дополнительный перевод панелей, меню и системных сообщений."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app" / "ui"
TEXT = {
    "About TalkTrack": "О программе SwimRocket",
    "TalkTrack": "SwimRocket Встречи",
    "Buy Me a Coffee": "Поддержать проект",
    "Close": "Закрыть",
    "Ask about this recording...": "Спросить об этой записи…",
    "Send": "Отправить",
    "Create a HuggingFace account": "Создайте аккаунт HuggingFace",
    "Open HuggingFace": "Открыть HuggingFace",
    "Accept the model license": "Примите лицензию модели",
    "Accept License": "Принять лицензию",
    "Create an access token": "Создайте токен доступа",
    "Open Token Settings": "Открыть настройки токенов",
    "Paste your token below": "Вставьте токен ниже",
    "Enable speaker diarization": "Определять разных спикеров",
    "Skip": "Пропустить",
    "Semantic search": "Семантический поиск",
    "Text search (click for semantic)": "Текстовый поиск (нажмите для семантического)",
    "This segment has been edited": "Этот фрагмент был изменён",
    "Edit Text": "Изменить текст",
    "Undo": "Отменить",
    "Redo": "Повторить",
    "Revert to Original": "Вернуть исходный текст",
    "Install Required Package": "Установка необходимого пакета",
    "Installation Failed": "Ошибка установки",
    "Select Model File": "Выберите файл модели",
    "GGUF Files (*.gguf);;All Files (*)": "Файлы GGUF (*.gguf);;Все файлы (*)",
    "No provider selected.": "Поставщик не выбран.",
    "Connection successful!": "Подключение успешно!",
    "Connection failed: empty response.": "Ошибка подключения: пустой ответ.",
    "AI Error": "Ошибка AI",
    "Select Output Directory": "Выберите папку для записей",
    "Enter name...": "Введите имя…",
    "Find...": "Найти…",
    "Replace...": "Заменить…",
    "Case sensitive": "Учитывать регистр",
    "Use regex": "Использовать регулярное выражение",
    "Replace": "Заменить",
    "No matches": "Совпадений нет",
    "Export Transcript": "Экспорт расшифровки",
    "Record": "Запись",
    "TalkTrack is still running": "SwimRocket Встречи продолжает работать",
    "MIC MUTED": "МИКРОФОН ВЫКЛ.",
    "Mic": "Мик",
    "Sys": "Сис",
    "MIC": "МИК",
    "SYS": "СИС",
    "Stereo": "Стерео",
}
for path in ROOT.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in TEXT.items():
        updated = updated.replace(f'"{old}"', f'"{new}"')
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print(path.relative_to(ROOT))
