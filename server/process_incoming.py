# -*- coding: utf-8 -*-
"""Последовательно обрабатывает очередь встреч под глобальной блокировкой."""
import fcntl
import json
import os
import sys
import traceback
from pathlib import Path

from meeting_worker import (
    atomic_json, atomic_text, process_job, retry_telegram, update_status,
)

BASE = Path(__file__).resolve().parent.parent
JOBS = BASE / "jobs"
LOCK = BASE / ".processor.lock"
LOG = BASE / "processor.log"


def log(message):
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def job_state(job):
    status_path = job / "status.json"
    if not status_path.exists():
        return "queued"
    try:
        return json.loads(status_path.read_text(encoding="utf-8")).get("state") or "queued"
    except (json.JSONDecodeError, OSError):
        return "queued"


def ready_jobs():
    if not JOBS.is_dir():
        return []
    result = []
    for job in sorted(JOBS.iterdir()):
        if not job.is_dir() or not (job / "request.json").is_file():
            continue
        state = job_state(job)
        # processing подхватывается после перезапуска сервера. telegram_error
        # означает, что готовы все файлы и нужно повторить только доставку.
        if state in ("queued", "processing", "telegram_error"):
            result.append(job)
    return result


def retry_telegram_only(job):
    try:
        result = retry_telegram(job)
        log(f"{result.get('id')}: Telegram доставлен после повтора")
    except Exception as exc:
        message = str(exc)[-1500:]
        try:
            result_path = job / "result.json"
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result["state"] = "telegram_error"
            result["telegram_status"] = "error"
            result["telegram_error"] = message
            atomic_json(result_path, result)
            update_status(
                job, "telegram_error",
                "Разбор сохранён; повторю отправку в Telegram без повторной расшифровки",
                error=message, obsidian_synced=result.get("obsidian_synced", False),
                telegram_sent=False,
            )
        except Exception:
            pass
        log(f"{job.name}: TELEGRAM RETRY ERROR {message}")


def main():
    BASE.mkdir(parents=True, exist_ok=True)
    JOBS.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        for job in ready_jobs():
            if job_state(job) == "telegram_error":
                retry_telegram_only(job)
                continue
            try:
                result = process_job(job)
                if result.get("state") == "telegram_error":
                    log(f"{result.get('id')}: разбор сохранён, ожидает повтора Telegram")
                else:
                    log(f"{result.get('id')}: done; Obsidian={result.get('obsidian_path')}")
            except Exception as exc:
                message = str(exc)[-1500:]
                try:
                    update_status(job, "error", "Ошибка обработки записи", error=message)
                except Exception:
                    pass
                log(f"{job.name}: ERROR {message}\n{traceback.format_exc()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
