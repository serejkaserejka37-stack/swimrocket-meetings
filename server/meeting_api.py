"""HTTPS API для коллег: личные токены, загрузка записей и получение разбора."""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from user_registry import exchange_setup_code, user_for_token

BASE = Path(__file__).resolve().parent.parent
UPLOADS = BASE / "uploads"
JOBS = BASE / "jobs"
MAX_JSON = 128 * 1024
MAX_AUDIO = 2 * 1024 * 1024 * 1024
ARTIFACTS = {
    "result.json", "transcript.json", "transcript.md", "summary.md",
    "action_items.json", "obsidian_note.md", "status.json",
}


def valid_job_id(value):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{3,100}", value or ""))


class Handler(BaseHTTPRequestHandler):
    server_version = "SwimRocketMeetings/1.0"

    def log_message(self, fmt, *args):
        # Токены и содержимое запросов в журнал не пишем.
        print(f"API {self.client_address[0]}: {fmt % args}", flush=True)

    def _send_json(self, status, data):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _error(self, status, message):
        self._send_json(status, {"error": str(message)})

    def _user(self):
        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        return user_for_token(token)

    def _require_user(self):
        user = self._user()
        if not user:
            self._error(401, "Недействительный токен. Пройдите настройку заново.")
            return None
        return user

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > MAX_JSON:
            raise ValueError("Некорректный размер JSON-запроса")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("Ожидался JSON-объект")
        return data

    def _find_job(self, job_id, user, allow_upload=True):
        if not valid_job_id(job_id):
            raise ValueError("Некорректный идентификатор записи")
        for base in ([UPLOADS] if allow_upload else []) + [JOBS]:
            suffix = ".part" if base == UPLOADS else ""
            path = base / f"{job_id}{suffix}"
            if path.is_dir():
                request_path = path / "request.json"
                if not request_path.is_file():
                    continue
                request = json.loads(request_path.read_text(encoding="utf-8"))
                if request.get("owner_id") != user["user_id"]:
                    raise PermissionError("Нет доступа к этой записи")
                return path, request
        raise FileNotFoundError("Запись не найдена")

    def do_GET(self):
        try:
            if self.path == "/v1/health":
                self._send_json(200, {"ok": True, "service": "SwimRocket Встречи"})
                return
            if self.path.startswith("/v1/setup/") or self.path.startswith("/v1/jobs"):
                pass
            elif self.path == "/v1/me":
                user = self._require_user()
                if user:
                    self._send_json(200, {
                        "user_id": user["user_id"], "chat_id": user["chat_id"],
                        "display_name": user.get("display_name", ""),
                    })
                return
            else:
                self._error(404, "Маршрут не найден")
                return
            user = self._require_user()
            if not user:
                return
            parts = self.path.strip("/").split("/")
            if len(parts) == 3 and parts[:2] == ["v1", "jobs"]:
                path, _ = self._find_job(parts[2], user)
                status_path = path / "status.json"
                if status_path.is_file():
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                else:
                    status = {"state": "queued", "message": "Запись в очереди"}
                self._send_json(200, status)
                return
            if len(parts) == 4 and parts[:2] == ["v1", "jobs"]:
                name = parts[3]
                if name not in ARTIFACTS:
                    self._error(404, "Файл не найден")
                    return
                path, _ = self._find_job(parts[2], user)
                file_path = path / name
                if not file_path.is_file():
                    self._error(404, "Файл ещё не готов")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(file_path.stat().st_size))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with file_path.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        self.wfile.write(chunk)
                return
            self._error(404, "Маршрут не найден")
        except (ValueError, PermissionError, FileNotFoundError) as exc:
            self._error(403 if isinstance(exc, PermissionError) else 400, str(exc))
        except Exception as exc:
            self._error(500, f"Внутренняя ошибка: {exc}")

    def do_POST(self):
        try:
            if self.path == "/v1/setup/exchange":
                data = self._read_json()
                self._send_json(200, exchange_setup_code(data.get("code", "")))
                return
            user = self._require_user()
            if not user:
                return
            if self.path == "/v1/jobs":
                data = self._read_json()
                client_id = data.get("client_id") or data.get("id")
                if not valid_job_id(client_id):
                    raise ValueError("Некорректный идентификатор записи")
                job_id = f"{user['user_id']}_{client_id}"
                upload_dir = UPLOADS / f"{job_id}.part"
                upload_dir.mkdir(parents=True, exist_ok=True)
                request = dict(data)
                request.update({
                    "id": job_id,
                    "client_id": client_id,
                    "owner_id": user["user_id"],
                    "chat_id": int(user["chat_id"]),
                    "allow_obsidian": int(user["chat_id"]) == 678675695,
                    "allow_tasks": int(user["chat_id"]) == 678675695,
                    "send_telegram": True,
                    "audio": dict(data.get("audio") or {}),
                })
                (upload_dir / "request.json").write_text(
                    json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8",
                )
                self._send_json(200, {"job_id": job_id, "state": "uploading"})
                return
            parts = self.path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["v1", "jobs"] and parts[3] == "complete":
                path, request = self._find_job(parts[2], user)
                if not request.get("audio"):
                    raise ValueError("Сначала загрузите аудио")
                target = JOBS / parts[2]
                if not target.exists():
                    JOBS.mkdir(parents=True, exist_ok=True)
                    os.replace(path, target)
                self._send_json(200, {"job_id": parts[2], "state": "queued"})
                return
            self._error(404, "Маршрут не найден")
        except (ValueError, PermissionError, FileNotFoundError) as exc:
            self._error(403 if isinstance(exc, PermissionError) else 400, str(exc))
        except Exception as exc:
            self._error(500, f"Внутренняя ошибка: {exc}")

    def do_PUT(self):
        try:
            user = self._require_user()
            if not user:
                return
            parts = self.path.strip("/").split("/")
            if len(parts) != 5 or parts[:2] != ["v1", "jobs"] or parts[3] != "audio":
                self._error(404, "Маршрут не найден")
                return
            role = parts[4]
            if role not in ("mic", "system", "combined"):
                self._error(400, "Неизвестный аудиоканал")
                return
            path, request = self._find_job(parts[2], user)
            if path.parent != UPLOADS:
                raise ValueError("Загрузка уже завершена")
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length <= 44 or length > MAX_AUDIO:
                raise ValueError("Некорректный размер аудиофайла")
            target = path / f"{role}.wav"
            temp = path / f"{role}.uploading"
            remaining = length
            with temp.open("wb") as handle:
                while remaining:
                    chunk = self.rfile.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("Загрузка оборвалась")
                    handle.write(chunk)
                    remaining -= len(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, target)
            audio = dict(request.get("audio") or {})
            audio[role] = target.name
            request["audio"] = audio
            (path / "request.json").write_text(
                json.dumps(request, ensure_ascii=False, indent=2), encoding="utf-8",
            )
            self._send_json(200, {"ok": True, "role": role, "bytes": length})
        except (ValueError, PermissionError, FileNotFoundError) as exc:
            self._error(403 if isinstance(exc, PermissionError) else 400, str(exc))
        except Exception as exc:
            self._error(500, f"Внутренняя ошибка: {exc}")


def main():
    UPLOADS.mkdir(parents=True, exist_ok=True)
    JOBS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 8788), Handler)
    server.daemon_threads = True
    print("SwimRocket Meetings API: 127.0.0.1:8788", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
