"""Перевод оставшихся видимых элементов интерфейса SwimRocket."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app"
TRANSLATIONS = {
    "Untitled Recording": "Запись без названия",
    "Rename": "Переименовать",
    "Save": "Сохранить",
    "Duration:": "Длительность:",
    "Mic Gain:": "Усиление микрофона:",
    "System Audio:": "Системный звук:",
    "Microphone 2:": "Микрофон 2:",
    "(None - don't record microphone)": "(Не записывать микрофон)",
    "(None - don't record second mic)": "(Не записывать второй микрофон)",
    "(None - don't record system audio)": "(Не записывать системный звук)",
    "(No system audio)": "(Без системного звука)",
    "(No apps selected)": "(Приложения не выбраны)",
    "No audio apps detected": "Активные аудиоприложения не найдены",
    "Search recordings...": "Поиск записей…",
    "Open Folder": "Открыть папку",
    "View / Transcribe": "Открыть / Расшифровать",
    "Play Audio": "Воспроизвести аудио",
    "Delete Recording": "Удалить запись",
    "Delete Recordings": "Удалить записи",
    "Delete {count} Recordings": "Удалить записи: {count}",
    "This cannot be undone.": "Действие нельзя отменить.",
    "Error": "Ошибка",
    "Failed to delete:": "Не удалось удалить:",
    "Copy": "Копировать",
    "Regenerate": "Сформировать заново",
    "Generate Summary": "Сформировать итоги",
    "Generating summary...": "Формирую итоги встречи…",
    "No summary generated yet.": "Итоги встречи ещё не сформированы.",
    "Summary generation failed.": "Не удалось сформировать итоги.",
    "Optional: instructions for regeneration (e.g. \"use John instead of SPEAKER_00\")": "Необязательно: уточнение для новой обработки (например, имена участников)",
    "No action items extracted yet.": "Задачи ещё не выделены.",
    "Extract Action Items": "Выделить задачи",
    "Extracting action items...": "Выделяю задачи…",
    "Action item extraction failed.": "Не удалось выделить задачи.",
    "Call Notes": "Заметки по встрече",
    "+ Timestamp": "+ Время",
    "Insert current timestamp": "Вставить текущее время",
    "Type your call notes here...": "Введите заметки по встрече…",
    "Use the Timestamp button to mark important moments.": "Кнопка «Время» отмечает важные моменты.",
    "Transcript will appear here after recording and transcription...": "Расшифровка появится после записи и обработки…",
    "▶ Play All": "▶ Слушать всё",
    "Recording...": "Идёт запись…",
    "Microphone muted": "Микрофон выключен",
    "Cancelling...": "Отменяю…",
    "Recording deleted.": "Запись удалена.",
    "System Status": "Состояние системы",
    "Speaker Diarization Setup": "Настройка разделения спикеров",
    "Save && Enable": "Сохранить и включить",
    "TalkTrack — Recording": "SwimRocket — идёт запись",
    "TalkTrack — Paused": "SwimRocket — пауза",
    "Pause": "Пауза",
    "Resume": "Продолжить",
    "Stop": "Стоп",
    "Quit": "Выход",
    "Show SwimRocket Встречи": "Показать SwimRocket Встречи",
}
for path in ROOT.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    updated = text
    for old, new in TRANSLATIONS.items():
        updated = updated.replace(f'"{old}"', f'"{new}"')
    if path.name == "recording_header.py":
        updated = updated.replace('return f"{h}h {m}m {s}s"', 'return f"{h} ч {m} мин {s} с"')
        updated = updated.replace('return f"{m}m {s}s"', 'return f"{m} мин {s} с"')
        updated = updated.replace('return f"{s}s"', 'return f"{s} с"')
        updated = updated.replace('parts.append(f"{speaker_count} speaker{\'s\' if speaker_count != 1 else \'\'}")',
                                  'parts.append(f"Спикеров: {speaker_count}")')
        updated = updated.replace("self.rename_btn.setFixedWidth(70)", "self.rename_btn.setFixedWidth(125)")
    if path.name == "recordings_list.py":
        updated = updated.replace('f"Delete \\"{name}\\" and all its files?\\n\\nThis cannot be undone.',
                                  'f"Удалить \\"{name}\\" и все файлы?\\n\\nДействие нельзя отменить.')
        updated = updated.replace('f"Delete {count} recording{\'s\' if count > 1 else \'\'} and all their files?\\n\\n"',
                                  'f"Удалить записи ({count}) и все их файлы?\\n\\n"')
    if path.name == "tray_icon.py":
        updated = updated.replace('return f"TalkTrack \\u2014 Recording {_format_elapsed(elapsed_seconds)}"',
                                  'return f"SwimRocket \\u2014 запись {_format_elapsed(elapsed_seconds)}"')
        updated = updated.replace('return f"TalkTrack \\u2014 Paused {_format_elapsed(elapsed_seconds)}"',
                                  'return f"SwimRocket \\u2014 пауза {_format_elapsed(elapsed_seconds)}"')
    if updated != text:
        path.write_text(updated, encoding="utf-8")
        print(path.relative_to(ROOT))
