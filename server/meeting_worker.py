# -*- coding: utf-8 -*-
"""Серверная расшифровка и разбор одной встречи SwimRocket.

Тяжёлая модель загружается только здесь. Один процесс обрабатывает одну
запись; глобальную последовательность обеспечивает process_incoming.py.
"""
import datetime as dt
import json
import os
import re
import subprocess
import urllib.request
import wave
from pathlib import Path

BASE = Path(__file__).resolve().parent
SUMMARY_DIR = Path("/root/SwimRocket/meeting_summaries")
VAULT = Path("/root/SwimRocket/vault")
MEETINGS_DIR = VAULT / "70 Встречи"
MODEL_NAME = os.environ.get("SWIMROCKET_WHISPER_MODEL", "small")
MSK = dt.timezone(dt.timedelta(hours=3))
_MODEL = None


def atomic_text(path, text):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_json(path, data):
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def update_status(job_dir, state, message, **extra):
    payload = {
        "state": state,
        "message": message,
        "updated_at": dt.datetime.now(MSK).isoformat(timespec="seconds"),
        **extra,
    }
    atomic_json(Path(job_dir) / "status.json", payload)


def safe_name(value):
    value = re.sub(r'[\\/:*?"<>|\r\n]+', "-", str(value or "Встреча")).strip(" .")
    return value[:140] or "Встреча"


def format_time(seconds):
    seconds = max(0, int(seconds or 0))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_model():
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel(
            MODEL_NAME,
            device="cpu",
            compute_type="int8",
            cpu_threads=max(1, min(4, os.cpu_count() or 1)),
        )
    return _MODEL


def load_wav(path):
    """Читает PCM WAV без PyAV: свежие версии av несовместимы с faster-whisper."""
    import numpy as np

    with wave.open(str(path), "rb") as source:
        rate = source.getframerate()
        channels = source.getnchannels()
        width = source.getsampwidth()
        frames = source.readframes(source.getnframes())
    if width != 2:
        raise RuntimeError("Поддерживается PCM WAV 16 бит; выберите WAV в настройках")
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if rate != 16000:
        target_length = int(len(audio) * 16000 / rate)
        old_positions = np.arange(len(audio), dtype=np.float64)
        new_positions = np.linspace(0, len(audio) - 1, target_length)
        audio = np.interp(new_positions, old_positions, audio).astype(np.float32)
    return np.ascontiguousarray(audio, dtype=np.float32)


def transcribe_file(path, language="ru"):
    segments, info = get_model().transcribe(
        load_wav(path),
        language=language or "ru",
        beam_size=1,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
    )
    result = []
    for segment in segments:
        text = segment.text.strip()
        if text:
            result.append({
                "start": round(float(segment.start), 3),
                "end": round(float(segment.end), 3),
                "text": text,
            })
    return {
        "segments": result,
        "language": getattr(info, "language", language or "ru"),
        "duration": float(getattr(info, "duration", 0) or 0),
    }


def merge_channels(channel_results):
    labels = {"mic": "Сергей", "system": "Собеседники", "combined": "Участники"}
    segments = []
    language = "ru"
    duration = 0.0
    for role, result in channel_results.items():
        language = result.get("language") or language
        duration = max(duration, float(result.get("duration") or 0))
        for item in result.get("segments", []):
            segments.append({
                "start": item["start"],
                "end": item["end"],
                "text": item["text"],
                "speaker": labels.get(role, role),
                "confidence": 0.0,
            })
    segments.sort(key=lambda x: (x["start"], x["end"], x["speaker"]))
    # Если микрофон услышал динамики, один и тот же текст может появиться
    # в двух каналах с небольшой задержкой. Дубль в пределах двух секунд
    # оставляем за системным каналом независимо от порядка распознавания.
    unique = []
    seen = {}
    for segment in segments:
        normalized = re.sub(r"\W+", " ", segment["text"].casefold()).strip()
        if len(normalized) < 15:
            unique.append(segment)
            continue
        duplicate = None
        for index in reversed(seen.get(normalized, [])):
            previous = unique[index]
            if abs(float(segment["start"]) - float(previous["start"])) <= 2.0:
                duplicate = index
                break
        if duplicate is not None:
            if segment["speaker"] == "Собеседники":
                unique[duplicate] = segment
            continue
        seen.setdefault(normalized, []).append(len(unique))
        unique.append(segment)
    return {"segments": unique, "language": language, "duration": duration}


def transcript_markdown(title, started_at, transcript):
    lines = [f"# {title} — расшифровка", "", f"Дата: {started_at}", ""]
    for segment in transcript.get("segments", []):
        lines.append(
            f"[{format_time(segment['start'])}] **{segment.get('speaker') or 'Участник'}:** "
            f"{segment['text']}"
        )
    if not transcript.get("segments"):
        lines.append("Речь не распознана. Проверьте исходную запись и выбранные аудиоканалы.")
    return "\n".join(lines) + "\n"


def _env_value(name):
    value = os.environ.get(name)
    if value:
        return value
    try:
        with open("/root/SwimRocket/.env", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def gemini_complete(prompt):
    key = _env_value("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Не настроен GEMINI_API_KEY")
    model = _env_value("GEMINI_MODEL") or "gemini-3.5-flash-lite"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 8000,
            "responseMimeType": "application/json",
        },
    }).encode()
    request = urllib.request.Request(url, data=body, headers={
        "x-goog-api-key": key,
        "content-type": "application/json",
    })
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.loads(response.read())
    parts = []
    for candidate in data.get("candidates", []):
        parts.extend((candidate.get("content") or {}).get("parts") or [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        reason = data.get("promptFeedback") or "пустой ответ Gemini"
        raise RuntimeError(f"Gemini не вернул разбор: {reason}")
    return text


def llm_complete(prompt):
    provider = (_env_value("SWIMROCKET_LLM_PROVIDER") or "anthropic").strip().lower()
    if provider == "gemini":
        return gemini_complete(prompt)
    if provider != "anthropic":
        raise RuntimeError(f"Неизвестный LLM-провайдер: {provider}")
    relay_url = _env_value("ANTHROPIC_RELAY_URL")
    relay_token = _env_value("ANTHROPIC_RELAY_TOKEN")
    if relay_url and relay_token:
        url = relay_url
        headers = {"X-Relay-Token": relay_token, "content-type": "application/json"}
    else:
        key = _env_value("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Не настроен серверный доступ к языковой модели")
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    body = json.dumps({
        "model": "claude-haiku-4-5",
        "max_tokens": 5000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    request = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(request, timeout=180) as response:
        data = json.loads(response.read())
    return "".join(block.get("text", "") for block in data.get("content", []))


def parse_json_object(raw):
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                continue
    raise ValueError("Языковая модель не вернула корректный JSON")


def analyze_meeting(request, transcript_text):
    prompt = f"""Ты — помощник руководителя школы плавания SwimRocket. Разбери встречу строго по расшифровке. Не выдумывай решения, людей, задачи или сроки. Учитывай список участников и заметки. Если ответственный или срок прямо не названы — оставь пустую строку. Задачи формулируй как конкретное действие с проверяемым результатом.

Название, указанное пользователем: {request.get('name', '')}
Участники, указанные пользователем: {request.get('participants', '')}
Заметки пользователя: {request.get('notes', '')}

Расшифровка:
{transcript_text[:180000]}

Верни СТРОГО один JSON-объект без markdown:
{{
  "title": "короткое точное название встречи",
  "participants": ["имена или роли реальных участников"],
  "key_points": ["ключевой тезис"],
  "decisions": ["принятое решение"],
  "tasks": [{{"task": "действие", "assignee": "ответственный", "deadline": "срок как прозвучал", "result": "ожидаемый результат", "priority": "Средний"}}],
  "open_questions": ["незакрытый вопрос"]
}}
Если какого-то раздела нет, верни для него пустой список."""
    return parse_json_object(llm_complete(prompt))


def _strings(value):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def normalize_analysis(value, request):
    value = value if isinstance(value, dict) else {}
    tasks = []
    for item in value.get("tasks") or []:
        if isinstance(item, str):
            item = {"task": item}
        if not isinstance(item, dict) or not str(item.get("task", "")).strip():
            continue
        tasks.append({
            "task": str(item.get("task", "")).strip(),
            "assignee": str(item.get("assignee", "")).strip(),
            "deadline": str(item.get("deadline", "")).strip(),
            "result": str(item.get("result", "")).strip(),
            "priority": str(item.get("priority", "")).strip() or "Средний",
            "comment": f"встреча: {request.get('name', '')}",
            "completed": False,
        })
    return {
        "title": str(value.get("title") or request.get("name") or "Встреча").strip(),
        "participants": _strings(value.get("participants")),
        "key_points": _strings(value.get("key_points")),
        "decisions": _strings(value.get("decisions")),
        "tasks": tasks,
        "open_questions": _strings(value.get("open_questions")),
    }


def started_msk(request):
    """Naive datetime ноутбука уже московское, а не серверное UTC."""
    try:
        value = dt.datetime.fromisoformat(request.get("started_at", ""))
        if value.tzinfo is None:
            value = value.replace(tzinfo=MSK)
        return value.astimezone(MSK)
    except (ValueError, TypeError):
        return dt.datetime.now(MSK)


def build_summary(analysis, request):
    date = started_msk(request).strftime("%d.%m.%Y")
    participants = analysis.get("participants") or ([request["participants"]] if request.get("participants") else [])
    lines = [f"🏊 {analysis['title']}, {date}", ""]
    lines.append("👥 Участники: " + (", ".join(participants) if participants else "не указаны"))
    for heading, key in (("💡 Ключевые тезисы:", "key_points"), ("📌 Решения:", "decisions")):
        lines.extend(["", heading])
        values = analysis.get(key) or []
        lines.extend([f"— {item}" for item in values] or ["— Не выделены"])
    lines.extend(["", "📋 ЗАДАЧИ С ВСТРЕЧИ:"])
    tasks = analysis.get("tasks") or []
    if tasks:
        for task in tasks:
            lines.append(
                f"• {task.get('assignee') or 'не назначен'} — {task['task']} — "
                f"{task.get('deadline') or 'срок не назван'}"
            )
    else:
        lines.append("• Задачи не выделены")
    lines.extend(["", "❓ Открытые вопросы:"])
    questions = analysis.get("open_questions") or []
    lines.extend([f"— {item}" for item in questions] or ["— Нет"])
    if tasks:
        lines.extend(["", "Чтобы внести задачи в задачники, нажмите кнопку ниже."])
    if request.get("allow_obsidian", True):
        lines.extend(["", "🔒 В Obsidian встреча попадёт только после вашего подтверждения."])
    return "\n".join(lines) + "\n"


def build_obsidian_note(analysis, request, summary, transcript_md):
    title = analysis["title"]
    front = {
        "type": "meeting",
        "date": request.get("started_at", ""),
        "participants": analysis.get("participants") or [],
        "source": "SwimRocket Встречи",
        "session_id": request.get("id", ""),
    }
    lines = ["---"]
    for key, value in front.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend([
        "---", "", f"# {title}", "", summary, "", "---", "", transcript_md,
    ])
    return "\n".join(lines)


def save_to_vault(note, request, title):
    MEETINGS_DIR.mkdir(parents=True, exist_ok=True)
    prefix = started_msk(request).strftime("%Y-%m-%d %H-%M")
    path = MEETINGS_DIR / f"{prefix} {safe_name(title)}.md"
    atomic_text(path, note)
    synced = False
    if (VAULT / ".git").is_dir():
        subprocess.run(["git", "-C", str(VAULT), "pull", "--rebase", "--autostash"],
                       capture_output=True, timeout=90)
        subprocess.run(["git", "-C", str(VAULT), "add", str(path.relative_to(VAULT))],
                       capture_output=True, timeout=30)
        commit = subprocess.run(
            ["git", "-C", str(VAULT), "commit", "-m", f"Встреча: {title}"],
            capture_output=True, timeout=60,
        )
        if commit.returncode == 0:
            push = subprocess.run(["git", "-C", str(VAULT), "push"],
                                  capture_output=True, timeout=90)
            synced = push.returncode == 0
    return str(path), synced


def send_telegram(summary_path, with_button=True, with_obsidian=True, chat_id="678675695"):
    command = [
        "/root/SwimRocket/venv/bin/python",
        str(SUMMARY_DIR / "send_summary.py"),
        str(chat_id),
        str(summary_path),
    ]
    mode = "both" if with_button and with_obsidian else (
        "button" if with_button else "obsidian" if with_obsidian else ""
    )
    if mode:
        command.extend([mode, Path(summary_path).parent.name])
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        error = (result.stderr or result.stdout or "неизвестная ошибка").strip()
        raise RuntimeError(error[-1200:])
    if "OK:" not in (result.stdout or "") or "message_ids" not in result.stdout:
        raise RuntimeError("Отправитель не подтвердил регистрацию сообщения")
    return result.stdout.strip()


def retry_telegram(job_dir):
    """Повторно отправляет готовую сводку, не запуская Whisper или LLM."""
    job_dir = Path(job_dir)
    result = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
    summary_path = job_dir / "summary.md"
    if not summary_path.is_file():
        raise RuntimeError("Готовая сводка для повторной отправки не найдена")
    tasks = json.loads((job_dir / "action_items.json").read_text(encoding="utf-8"))
    request = json.loads((job_dir / "request.json").read_text(encoding="utf-8"))
    result["telegram_status"] = send_telegram(
        summary_path,
        with_button=bool(tasks) and request.get("allow_tasks", True),
        with_obsidian=(request.get("allow_obsidian", True)
                       and not result.get("obsidian_synced", False)),
        chat_id=request.get("chat_id", "678675695"),
    )
    result["state"] = "done"
    result.pop("telegram_error", None)
    atomic_json(job_dir / "result.json", result)
    update_status(job_dir, "done", "Готово: расшифровка и разбор сохранены",
                  obsidian_synced=result.get("obsidian_synced", False), telegram_sent=True)
    return result


def process_job(job_dir, transcribe_fn=None, llm_fn=None, publish=True):
    job_dir = Path(job_dir)
    request = json.loads((job_dir / "request.json").read_text(encoding="utf-8"))
    update_status(job_dir, "processing", "Распознаю речь на сервере…")
    transcribe_fn = transcribe_fn or transcribe_file
    channel_results = {}
    audio_request = request.get("audio") or {}
    if audio_request.get("mic") or audio_request.get("system"):
        audio_request.pop("combined", None)
    for role, name in audio_request.items():
        if role not in ("mic", "system", "combined") or Path(name).name != name:
            continue
        path = job_dir / name
        if not path.is_file() or path.stat().st_size <= 44:
            raise RuntimeError(f"Аудиофайл {name} отсутствует или повреждён")
        update_status(job_dir, "processing", f"Распознаю канал: {role}…")
        channel_results[role] = transcribe_fn(path, request.get("language", "ru"))
    if not channel_results:
        raise RuntimeError("В задании нет доступных аудиоканалов")

    transcript = merge_channels(channel_results)
    atomic_json(job_dir / "transcript.json", transcript)
    plain_lines = [
        f"[{format_time(s['start'])}] {s.get('speaker') or 'Участник'}: {s['text']}"
        for s in transcript["segments"]
    ]
    transcript_text = "\n".join(plain_lines)
    transcript_md = transcript_markdown(request.get("name", "Встреча"),
                                        request.get("started_at", ""), transcript)
    atomic_text(job_dir / "transcript.md", transcript_md)

    update_status(job_dir, "processing", "Формирую тезисы, решения и задачи…")
    llm_error = None
    try:
        analyzer = llm_fn or (lambda req, text: analyze_meeting(req, text))
        analysis = normalize_analysis(analyzer(request, transcript_text), request)
    except Exception as exc:
        llm_error = str(exc)
        analysis = normalize_analysis({"title": request.get("name")}, request)
    summary = build_summary(analysis, request)
    if llm_error:
        summary += "\n⚠️ Автоматический разбор не выполнен; расшифровка сохранена полностью.\n"
    atomic_text(job_dir / "summary.md", summary)
    atomic_json(job_dir / "action_items.json", analysis["tasks"])

    note = build_obsidian_note(analysis, request, summary, transcript_md)
    atomic_text(job_dir / "obsidian_note.md", note)
    result = {
        "id": request.get("id"),
        "title": analysis["title"],
        "state": "processing",
        "obsidian_path": "",
        "obsidian_synced": False,
        "obsidian_status": "pending",
        "telegram_status": "disabled",
        "llm_error": llm_error,
        "artifacts": ["transcript.json", "transcript.md", "summary.md",
                      "action_items.json", "obsidian_note.md"],
    }
    if publish:
        # В общий Obsidian встреча попадает только после отдельной кнопки.
        # Здесь подготавливаем приватный результат и отправляем сводку.
        atomic_json(job_dir / "result.json", result)
        if request.get("send_telegram", True):
            update_status(job_dir, "processing", "Отправляю сводку в Telegram и проверяю доставку…")
            try:
                result["telegram_status"] = send_telegram(
                    job_dir / "summary.md",
                    with_button=bool(analysis["tasks"]) and request.get("allow_tasks", True),
                    with_obsidian=request.get("allow_obsidian", True),
                    chat_id=request.get("chat_id", "678675695"),
                )
            except Exception as exc:
                result["state"] = "telegram_error"
                result["telegram_status"] = "error"
                result["telegram_error"] = str(exc)[-1500:]
                atomic_json(job_dir / "result.json", result)
                update_status(
                    job_dir, "telegram_error",
                    "Разбор сохранён; повторю отправку в Telegram без повторной расшифровки",
                    error=result["telegram_error"], obsidian_synced=result["obsidian_synced"],
                    telegram_sent=False,
                )
                return result

    result["state"] = "done"
    atomic_json(job_dir / "result.json", result)
    telegram_sent = result["telegram_status"] not in ("disabled", "error")
    update_status(job_dir, "done", "Готово: расшифровка и разбор сохранены",
                  obsidian_synced=result["obsidian_synced"], telegram_sent=telegram_sent)
    return result
