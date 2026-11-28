# -*- coding: utf-8 -*-
"""Постоянный слушатель @swimrocket_meetings_bot (демон под systemd).

Команды (только из рабочего чата CHAT_ID):
- текст «внеси задачи»;
- inline-кнопка под сводкой (callback_data="add_tasks").

Реакция: задачи последней сводки из этой папки вносятся в
Google-задачники (add_tasks_server.py), в чат уходит подтверждение,
кнопка под сводкой меняется на «✅ Задачи внесены».
Повторное внесение блокируется listener_state.json (entered_for).

Offset хранится в updates_offset.txt (общий с poll_commands.py).
"""
import datetime as dt
import json
import os
import re
import subprocess
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
OFFSET_FILE = os.path.join(BASE, "updates_offset.txt")
STATE_FILE = os.path.join(BASE, "listener_state.json")
ADD_TASKS = os.path.join(BASE, "add_tasks_server.py")
PY = "/root/SwimRocket/venv/bin/python"
VAULT = "/root/SwimRocket/vault"
VAULT_TASKS = os.path.join(VAULT, "40 Операционка", "Задачи со встреч.md")
CHAT_ID = 678675695
KEYWORD = "внеси задачи"
FEEDBACK_PREFIX = "фидбек"
FEEDBACK_FILE = os.path.join(VAULT, "40 Операционка",
                             "Обратная связь по разборам.md")
MSK = dt.timezone(dt.timedelta(hours=3))
JOBS = "/root/SwimRocket/meeting_processor/jobs"
MEETING_SERVER = "/root/SwimRocket/meeting_processor/server"
REANALYZE = os.path.join(MEETING_SERVER, "reanalyze_job.py")
APPLY_REANALYSIS = os.path.join(MEETING_SERVER, "apply_reanalysis.py")
REANALYSIS_TRIGGERS = (
    "картина не полная", "неполная картина", "неполный разбор", "мало задач",
    "не нравится анализ", "плохой разбор", "слабый разбор", "не полный анализ",
)
TOKEN = None


def api(method, payload=None, timeout=40):
    global TOKEN
    if TOKEN is None:
        with open(os.path.join(BASE, ".bot_token"), encoding="utf-8") as f:
            TOKEN = f.read().strip()
    url = "https://api.telegram.org/bot" + TOKEN + "/" + method
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def say(text):
    say_to(CHAT_ID, text)


def say_to(chat_id, text):
    try:
        api("sendMessage", {"chat_id": int(chat_id), "text": text}, timeout=30)
    except Exception:
        pass


def handle_start(message):
    """Выдаёт одноразовый код связки приложения с личным чатом."""
    import sys
    if MEETING_SERVER not in sys.path:
        sys.path.insert(0, MEETING_SERVER)
    from user_registry import create_setup_code
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    name = " ".join(part for part in (user.get("first_name"), user.get("last_name")) if part)
    code = create_setup_code(chat["id"], name)
    say_to(chat["id"],
           "Добро пожаловать в SwimRocket Встречи!\n\n"
           f"Ваш одноразовый код настройки: `{code}`\n\n"
           "1. Откройте приложение SwimRocket Встречи.\n"
           "2. В мастере настройки введите этот код.\n"
           "3. Дождитесь подтверждения подключения.\n\n"
           "Код действует 30 минут. После настройки сводки ваших встреч "
           "будут приходить именно в этот чат.")


def parse_deadline(when, today):
    w = (when or "").strip().lower()
    if not w or any(k in w for k in ("без срока", "не назван", "не указан")):
        return None
    m = re.search(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?", w)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else today.year
        if y < 100:
            y += 2000
        try:
            return dt.date(y, mo, d).strftime("%d.%m.%Y")
        except ValueError:
            return None
    days_to_sun = (6 - today.weekday()) % 7
    if "следующ" in w and "недел" in w:
        return (today + dt.timedelta(days=days_to_sun + 7)).strftime("%d.%m.%Y")
    if any(k in w for k in ("эта неделя", "этой неделе", "конец недели",
                            "конца недели", "воскресень")):
        return (today + dt.timedelta(days=days_to_sun)).strftime("%d.%m.%Y")
    m = re.search(r"(\d+)\s*дн", w)
    if m:
        return (today + dt.timedelta(days=int(m.group(1)))).strftime("%d.%m.%Y")
    if "завтра" in w:
        return (today + dt.timedelta(days=1)).strftime("%d.%m.%Y")
    return None


def looks_like_deadline(text):
    t = text.lower()
    return any(k in t for k in ("срок", "недел", "дн", "встреч", "воскресень",
                                "завтра")) or bool(re.search(r"\d{1,2}\.\d{1,2}", t))


def parse_tasks(path):
    today = dt.datetime.now(MSK).date()
    with open(path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"📋[^\n]*\n(.*?)(?:\n\s*\n|\n❓|$)", text, re.S)
    if not m:
        return []
    stem = os.path.basename(path)[:-3]
    tasks = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith(("•", "-")):
            continue
        body = line.lstrip("•- ").strip()
        parts = [p.strip() for p in body.split(" — ")]
        if len(parts) < 2:
            continue
        who = parts[0]
        if len(parts) >= 3 and looks_like_deadline(parts[-1]):
            what = " — ".join(parts[1:-1])
            deadline = parse_deadline(parts[-1], today)
        else:
            what = " — ".join(parts[1:])
            deadline = None
        assignee = "не назначен" if "не назначен" in who.lower() else who
        t = {"task": what, "assignee": assignee, "comment": "встреча: " + stem}
        if deadline:
            t["deadline"] = deadline
        tasks.append(t)
    return tasks


def latest_summary():
    files = []
    for f in os.listdir(BASE):
        if not f.endswith(".md"):
            continue
        if f.startswith(("_reply", "test_", "ping")):
            continue
        files.append(f)
    if not files:
        return None
    files.sort(key=lambda f: os.path.getmtime(os.path.join(BASE, f)),
               reverse=True)
    return files[0]


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(s):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False)


def job_path(job_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", job_id or ""):
        raise ValueError("Некорректный идентификатор встречи")
    path = os.path.join(JOBS, job_id)
    if not os.path.isdir(path):
        raise FileNotFoundError("Встреча не найдена")
    return path


def update_buttons(msg, job_id=None, tasks_done=False,
                   obsidian_done=False, obsidian_available=True):
    rows = []
    suffix = f":{job_id}" if job_id else ""
    rows.append([{
        "text": "✅ Задачи внесены" if tasks_done else "📥 Внести задачи в задачники",
        "callback_data": "noop" if tasks_done else f"add_tasks{suffix}",
    }])
    if job_id and obsidian_available:
        rows.append([{
            "text": "✅ В Obsidian" if obsidian_done else "📝 Отправить в Obsidian",
            "callback_data": "noop" if obsidian_done else f"obsidian:{job_id}",
        }])
    try:
        api("editMessageReplyMarkup", {
            "chat_id": CHAT_ID,
            "message_id": msg["message_id"],
            "reply_markup": {"inline_keyboard": rows},
        }, timeout=30)
    except Exception:
        pass


def mark_button_done(msg):
    update_buttons(msg, tasks_done=True)


def push_tasks_to_vault(tasks, stem):
    """Добавляет задачи в '40 Операционка/Задачи со встреч.md' в копии
    хранилища на сервере и пушит в vault.git. Локальная копия Obsidian
    подтянет изменения при следующем pull. Дубли (та же задача и тот же
    ответственный) пропускаются."""
    try:
        if not os.path.isdir(VAULT):
            return False
        subprocess.run(["git", "-C", VAULT, "pull", "--rebase",
                        "--autostash"], capture_output=True, timeout=60)
        header = "# Задачи со встреч"
        try:
            with open(VAULT_TASKS, encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            content = header + "\n"
        existing = content.lower()
        lines = []
        for t in tasks:
            # защита от дублей: задача с таким текстом и ответственным
            # уже есть в файле (разбор мог записать её раньше)
            key = t["task"].strip().lower()[:40]
            who = t["assignee"].strip().lower()
            if key and key in existing and who in existing:
                continue
            line = f"- [ ] {t['task']} — {t['assignee']}"
            if t.get("deadline"):
                line += f", {t['deadline']}"
            line += f" · {stem}"
            lines.append(line)
        if not lines:
            return True  # всё уже записано — не ошибка
        block = "\n".join(lines) + "\n"
        if content.startswith(header):
            content = header + "\n" + block + content[len(header):].lstrip("\n")
            if not content.endswith("\n"):
                content += "\n"
        else:
            content = header + "\n" + block + "\n" + content
        with open(VAULT_TASKS, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.run(["git", "-C", VAULT, "add",
                        "40 Операционка/Задачи со встреч.md"],
                       capture_output=True, timeout=60)
        subprocess.run(["git", "-C", VAULT, "commit", "-m",
                        f"Задачи со встречи: {stem}"],
                       capture_output=True, timeout=60)
        r = subprocess.run(["git", "-C", VAULT, "push"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def save_feedback(text):
    """Сохраняет обратную связь Сергея по качеству разбора в
    '40 Операционка/Обратная связь по разборам.md' и пушит в vault.git.
    Кими читает этот файл при следующих разборах и учитывает замечания."""
    try:
        if not os.path.isdir(VAULT):
            return False
        subprocess.run(["git", "-C", VAULT, "pull", "--rebase",
                        "--autostash"], capture_output=True, timeout=60)
        header = "# Обратная связь по разборам"
        try:
            with open(FEEDBACK_FILE, encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            content = header + "\n"
        stamp = dt.datetime.now(MSK).strftime("%d.%m.%Y %H:%M")
        entry = f"\n## {stamp}\n\n{text.strip()}\n"
        if not content.endswith("\n"):
            content += "\n"
        content += entry
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        subprocess.run(["git", "-C", VAULT, "add",
                        "40 Операционка/Обратная связь по разборам.md"],
                       capture_output=True, timeout=60)
        subprocess.run(["git", "-C", VAULT, "commit", "-m",
                        f"Фидбек по разбору {stamp}"],
                       capture_output=True, timeout=60)
        r = subprocess.run(["git", "-C", VAULT, "push"],
                           capture_output=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def handle_command(msg=None, job_id=None):
    state = load_state()
    result = {}
    if job_id:
        directory = job_path(job_id)
        summary_path = os.path.join(directory, "summary.md")
        state_key = f"job:{job_id}"
        with open(os.path.join(directory, "result.json"), encoding="utf-8") as f:
            result = json.load(f)
        stem = result.get("title") or job_id
    else:
        name = latest_summary()
        if not name:
            say("Команда получена, но сводок на сервере нет — нечего вносить.")
            return
        summary_path = os.path.join(BASE, name)
        state_key = name
        stem = name[:-3]
    if not os.path.isfile(summary_path):
        say("Сводка этой встречи не найдена.")
        return
    obsidian_done = bool(result.get("obsidian_synced"))
    if state.get("entered_for") == state_key:
        say(f"Задачи встречи «{stem}» уже внесены ✅")
        if msg:
            update_buttons(msg, job_id, tasks_done=True, obsidian_done=obsidian_done)
        return
    tasks = parse_tasks(summary_path)
    if not tasks:
        say(f"В сводке «{stem}» не распознал задачи — передай Кими.")
        return
    tmp = os.path.join(BASE, f"_tasks_{job_id or 'latest'}.json")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    r = subprocess.run([PY, ADD_TASKS, tmp], capture_output=True, text=True,
                       timeout=300)
    try:
        os.remove(tmp)
    except OSError:
        pass
    if r.returncode != 0:
        say("⚠️ Не удалось внести задачи (ошибка add_tasks) — передай Кими.")
        return
    lines = [l for l in (r.stdout or "").splitlines() if l.startswith("Внесено")]
    state["entered_for"] = state_key
    save_state(state)
    vault_ok = push_tasks_to_vault(tasks, stem)
    reply = (f"✅ Задачи встречи «{stem}» внесены ({len(tasks)} шт.):\n"
             + "\n".join(lines))
    if vault_ok:
        reply += "\n📝 Также записаны в Obsidian (Задачи со встреч.md)"
    else:
        reply += "\n⚠️ В Obsidian записать не удалось — передай Кими"
    say(reply)
    if msg:
        update_buttons(msg, job_id, tasks_done=True, obsidian_done=obsidian_done)


def publish_obsidian(job_id, msg=None):
    try:
        directory = job_path(job_id)
        result_path = os.path.join(directory, "result.json")
        with open(result_path, encoding="utf-8") as f:
            result = json.load(f)
        title = result.get("title") or job_id
        state = load_state()
        tasks_done = state.get("entered_for") == f"job:{job_id}"
        if result.get("obsidian_synced"):
            say(f"Встреча «{title}» уже опубликована в Obsidian ✅")
            if msg:
                update_buttons(msg, job_id, tasks_done=tasks_done, obsidian_done=True)
            return
        with open(os.path.join(directory, "request.json"), encoding="utf-8") as f:
            request = json.load(f)
        with open(os.path.join(directory, "obsidian_note.md"), encoding="utf-8") as f:
            note = f.read()
        import sys
        if MEETING_SERVER not in sys.path:
            sys.path.insert(0, MEETING_SERVER)
        from meeting_worker import atomic_json, save_to_vault
        obsidian_path, synced = save_to_vault(note, request, title)
        result["obsidian_path"] = obsidian_path
        result["obsidian_synced"] = bool(synced)
        result["obsidian_status"] = "published" if synced else "error"
        atomic_json(result_path, result)
        if not synced:
            say("⚠️ Не удалось синхронизировать заметку с Obsidian. Можно повторить кнопкой.")
            return
        say(f"✅ Встреча «{title}» отправлена в Obsidian")
        if msg:
            update_buttons(msg, job_id, tasks_done=tasks_done, obsidian_done=True)
    except Exception as exc:
        say(f"⚠️ Не удалось отправить встречу в Obsidian: {str(exc)[:300]}")


def is_reanalysis_request(text):
    body = (text or "").lower()
    if body.startswith(FEEDBACK_PREFIX):
        body = body[len(FEEDBACK_PREFIX):]
    return any(trigger in body for trigger in REANALYSIS_TRIGGERS)


def find_reanalysis_job(message):
    chat_id = (message.get("chat") or {}).get("id")
    reply = message.get("reply_to_message") or {}
    reply_id = reply.get("message_id")
    candidates = []
    if not os.path.isdir(JOBS):
        return None
    for directory in os.listdir(JOBS):
        job_dir = os.path.join(JOBS, directory)
        request_path = os.path.join(job_dir, "request.json")
        result_path = os.path.join(job_dir, "result.json")
        if not os.path.isfile(request_path) or not os.path.isfile(result_path):
            continue
        try:
            with open(request_path, encoding="utf-8") as f:
                request = json.load(f)
            if int(request.get("chat_id", 0)) != int(chat_id):
                continue
            if reply_id:
                with open(result_path, encoding="utf-8") as f:
                    result = json.load(f)
                if str(reply_id) not in str(result.get("telegram_status", "")):
                    continue
            candidates.append((os.path.getmtime(result_path), directory))
        except Exception:
            continue
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def handle_reanalysis(message):
    chat_id = (message.get("chat") or {}).get("id")
    job_id = find_reanalysis_job(message)
    if not job_id:
        say_to(chat_id, "Не нашёл встречу для уточнения. Ответьте на сообщение с разбором.")
        return
    say_to(chat_id, "Понял, делаю более подробный разбор этой встречи. Это займёт несколько минут.")
    job_dir = os.path.join(JOBS, job_id)
    success = False
    for model in ("gemini-3.8-flash", "gemini-3.5-flash"):
        try:
            result = subprocess.run(
                [PY, REANALYZE, job_dir, model],
                capture_output=True, text=True, timeout=900,
            )
            if result.returncode == 0:
                success = True
                break
            error = (result.stderr or result.stdout or "ошибка модели")[-1500:]
        except Exception as exc:
            error = str(exc)[:1500]
        with open(os.path.join(job_dir, "reanalysis_error.log", ), "a", encoding="utf-8") as handle:
            handle.write(f"{model}: {error}\n")
    if not success:
        say_to(chat_id, "⚠️ Не удалось повторить разбор. Попробуйте позже — исходная версия сохранена.")
        return
    result = subprocess.run([PY, APPLY_REANALYSIS, job_dir],
                            capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        say_to(chat_id, "⚠️ Разбор готов, но не удалось отправить его. Исходная версия сохранена.")
        return
    say_to(chat_id, "✅ Отправил уточнённый разбор с большим количеством деталей и задач.")


def main():
    offset = 0
    if os.path.exists(OFFSET_FILE):
        try:
            offset = int(open(OFFSET_FILE).read().strip() or "0")
        except ValueError:
            offset = 0
    while True:
        try:
            q = "getUpdates?timeout=25&limit=50"
            if offset:
                q += "&offset=" + str(offset)
            upd = api(q)
            for u in upd.get("result", []):
                if u.get("update_id") is not None:
                    offset = u["update_id"] + 1
                m = u.get("message")
                cq = u.get("callback_query")
                if m:
                    chat_id = (m.get("chat") or {}).get("id")
                    text = (m.get("text") or "").strip()
                    low = text.lower()
                    if low in ("/start", "start") or low.startswith("/start@"):
                        handle_start(m)
                    elif is_reanalysis_request(low):
                        handle_reanalysis(m)
                    elif chat_id == CHAT_ID and KEYWORD in low:
                        handle_command()
                    elif chat_id == CHAT_ID and low.startswith(FEEDBACK_PREFIX):
                        body = text[len(FEEDBACK_PREFIX):].lstrip(" :.-").strip()
                        if body and save_feedback(body):
                            say("📝 Фидбек сохранён — Кими учтёт его при "
                                "следующих разборах.")
                        elif body:
                            say("⚠️ Не удалось сохранить фидбек — передай Кими.")
                        else:
                            say("Напиши фидбек после слова «фидбек», например: "
                                "«фидбек: это была Алёна, а не Алина»")
                elif cq and ((cq.get("message") or {}).get("chat") or {}
                             ).get("id") == CHAT_ID:
                    try:
                        api("answerCallbackQuery",
                            {"callback_query_id": cq["id"]}, timeout=30)
                    except Exception:
                        pass
                    data = cq.get("data") or ""
                    if data == "add_tasks":
                        handle_command(cq.get("message"))
                    elif data.startswith("add_tasks:"):
                        handle_command(cq.get("message"), data.split(":", 1)[1])
                    elif data.startswith("obsidian:"):
                        publish_obsidian(data.split(":", 1)[1], cq.get("message"))
            with open(OFFSET_FILE, "w") as f:
                f.write(str(offset))
        except Exception:
            time.sleep(10)


if __name__ == "__main__":
    main()
