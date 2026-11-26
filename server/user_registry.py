"""Одноразовые коды настройки и токены пользователей SwimRocket."""
import datetime as dt
import fcntl
import hashlib
import json
import os
import secrets
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
USERS_DIR = BASE / "users"
PENDING_FILE = USERS_DIR / "pending.json"
TOKENS_FILE = USERS_DIR / "tokens.json"
LOCK_FILE = USERS_DIR / ".registry.lock"
CODE_TTL_SECONDS = 30 * 60


def _now():
    return int(dt.datetime.now(dt.timezone.utc).timestamp())


def _read(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default or {}


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _locked_update(path, callback):
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        data = _read(path)
        result = callback(data)
        _write(path, data)
        return result


def create_setup_code(chat_id, display_name=""):
    code = "SR-" + secrets.token_hex(2).upper() + "-" + secrets.token_hex(2).upper()
    created = _now()

    def add(data):
        # Удаляем истёкшие коды и предыдущие коды этого пользователя.
        for key in list(data):
            item = data[key]
            if created - int(item.get("created_at", 0)) > CODE_TTL_SECONDS or item.get("chat_id") == chat_id:
                data.pop(key, None)
        data[code] = {
            "chat_id": int(chat_id), "display_name": str(display_name or "")[:120],
            "created_at": created,
        }

    _locked_update(PENDING_FILE, add)
    return code


def exchange_setup_code(code):
    normalized = (code or "").strip().upper()
    created = _now()
    token = "srmt_" + secrets.token_urlsafe(24)
    user_id = "u" + secrets.token_hex(4)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    def take_pending(data):
        item = data.get(normalized)
        if not item:
            raise ValueError("Код не найден. Нажмите Start в боте ещё раз.")
        if created - int(item.get("created_at", 0)) > CODE_TTL_SECONDS:
            data.pop(normalized, None)
            raise ValueError("Срок действия кода истёк. Получите новый код в боте.")
        data.pop(normalized)
        return item

    pending = _locked_update(PENDING_FILE, take_pending)

    def add_user(data):
        data[token_hash] = {
            "user_id": user_id,
            "chat_id": int(pending["chat_id"]),
            "display_name": pending.get("display_name", ""),
            "created_at": created,
        }

    _locked_update(TOKENS_FILE, add_user)
    return {"token": token, "user_id": user_id, "chat_id": pending["chat_id"]}


def user_for_token(token):
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return _read(TOKENS_FILE).get(token_hash)
