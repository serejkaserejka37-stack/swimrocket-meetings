# -*- coding: utf-8 -*-
"""Серверный отправитель сводок встреч в Telegram.

Живёт на сервере: /root/SwimRocket/meeting_summaries/send_summary.py
Вызов: send_summary.py <chat_id> <путь> [button|obsidian|both] [job_id]
Кнопки независимы и привязаны к конкретной встрече:
- «Внести задачи» — add_tasks:<job_id>;
- «Отправить в Obsidian» — obsidian:<job_id>.
Режим button сохранён для обратной совместимости.
"""
import os
import re
import sys
import time

import requests
from dotenv import load_dotenv

MAX_LEN = 700  # безопасный размер части


def build_keyboard(mode="both", job_id=""):
    if job_id and not re.fullmatch(r"[A-Za-z0-9_-]+", job_id):
        raise ValueError("Некорректный идентификатор встречи")
    suffix = f":{job_id}" if job_id else ""
    rows = []
    if mode in ("button", "both"):
        rows.append([{
            "text": "📥 Внести задачи в задачники",
            "callback_data": f"add_tasks{suffix}",
        }])
    if mode in ("obsidian", "both"):
        rows.append([{
            "text": "📝 Отправить в Obsidian",
            "callback_data": f"obsidian{suffix}" if job_id else "obsidian",
        }])
    return {"inline_keyboard": rows} if rows else None


def split_text(text):
    """Режем по строкам, не разрывая строки посередине."""
    parts, cur = [], ""
    for line in text.split("\n"):
        if cur and len(cur) + len(line) + 1 > MAX_LEN:
            parts.append(cur)
            cur = ""
        cur = (cur + "\n" + line) if cur else line
    if cur.strip():
        parts.append(cur)
    return parts


def send(token, chat_id, text, markup=None):
    """Отправка с повторами и проверкой message_id:
    ok=true без result.message_id считаем сбоем и повторяем."""
    payload = {"chat_id": chat_id, "text": text}
    if markup:
        payload["reply_markup"] = markup
    last_err = None
    for attempt in range(4):
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
                timeout=30,
            )
            data = resp.json()
        except requests.RequestException as exc:
            last_err = f"нет соединения ({type(exc).__name__})"
            time.sleep(5 * (attempt + 1))
            continue
        if data.get("ok") and (data.get("result") or {}).get("message_id"):
            return data["result"]["message_id"]
        if data.get("ok"):
            last_err = "ok=true без message_id — сообщение не зарегистрировано"
            time.sleep(5 * (attempt + 1))
            continue
        desc = str(data.get("description", data)).replace(token, "***")
        if data.get("error_code") == 429:
            last_err = f"Telegram API: {desc}"
            time.sleep(10)
            continue
        raise RuntimeError(f"Telegram API отказал: {desc}")
    raise RuntimeError(f"не удалось отправить после 4 попыток: {last_err}")


def load_token():
    token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              ".bot_token")
    if os.path.exists(token_file):
        with open(token_file, encoding="utf-8") as f:
            token = f.read().strip()
            if token:
                return token
    load_dotenv("/root/SwimRocket/.env")
    return os.getenv("TELEGRAM_BOT_TOKEN")


def main():
    chat_id, path = sys.argv[1], sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else ""
    job_id = sys.argv[4] if len(sys.argv) > 4 else ""
    keyboard = build_keyboard(mode, job_id) if mode else None
    token = load_token()
    if not token:
        sys.exit("Нет токена: ни .bot_token, ни TELEGRAM_BOT_TOKEN в /root/SwimRocket/.env")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    parts = split_text(text)
    ids = []
    for i, part in enumerate(parts):
        markup = keyboard if i == len(parts) - 1 else None
        ids.append(send(token, chat_id, part, markup))
        time.sleep(1)
    print(f"OK: {os.path.basename(path)} -> chat {chat_id} "
          f"(частей: {len(ids)}, message_ids: {ids})")


if __name__ == "__main__":
    main()
