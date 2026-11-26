"""Передача записей на сервер SwimRocket и получение готового разбора.

На ноутбуке не загружаются Whisper, PyTorch или LLM. Используются только
системные OpenSSH ssh/scp; токены и пароли в приложении не хранятся.
"""
import json
import os
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from app.utils.atomic_io import atomic_write_json, atomic_write_text
from app.api_client import ApiClient


class RemoteProcessingWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, session, config, parent=None):
        super().__init__(parent)
        self.session = dict(session)
        self.config = config
        self._stop_requested = False
        self._api_job_id = None

    def stop(self):
        self._stop_requested = True

    @property
    def api_mode(self):
        return self.config.get("remote", "mode") == "api"

    @property
    def api_client(self):
        return ApiClient(
            self.config.get("remote", "server_url"),
            self.config.get("remote", "api_token"),
        )

    @property
    def api_job_id(self):
        if self._api_job_id:
            return self._api_job_id
        request_path = Path(self.session["directory"]) / "remote_request.json"
        if request_path.is_file():
            try:
                data = json.loads(request_path.read_text(encoding="utf-8"))
                self._api_job_id = data.get("server_job_id")
            except (OSError, json.JSONDecodeError):
                pass
        return self._api_job_id

    @api_job_id.setter
    def api_job_id(self, value):
        self._api_job_id = value

    @property
    def host(self):
        return self.config.get("remote", "host")

    @property
    def base(self):
        return self.config.get("remote", "directory").rstrip("/")

    @property
    def job_id(self):
        value = str(self.session.get("id") or "")
        if not value or not all(c.isalnum() or c in "_-" for c in value):
            raise ValueError("Некорректный идентификатор записи")
        return value

    @property
    def job_dir(self):
        return f"{self.base}/jobs/{self.job_id}"

    def _ssh_args(self):
        return [
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=20",
            "-o", "ServerAliveInterval=15",
            "-o", "ServerAliveCountMax=3",
            "-o", "StrictHostKeyChecking=accept-new",
        ]

    def _run(self, args, timeout=120, check=True):
        if self._stop_requested:
            raise RuntimeError("Операция остановлена пользователем")
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if check and proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "команда завершилась с ошибкой").strip()
            raise RuntimeError(message[-1500:])
        return proc

    def _ssh(self, command, timeout=120, check=True):
        return self._run(
            ["ssh", *self._ssh_args(), self.host, command],
            timeout=timeout,
            check=check,
        )

    def _scp(self, source, target, timeout=7200):
        return self._run(
            ["scp", *self._ssh_args(), str(source), target],
            timeout=timeout,
        )

    def _download(self, remote_name, local_path, timeout=300):
        quoted = shlex.quote(f"{self.job_dir}/{remote_name}")
        return self._run(
            ["scp", *self._ssh_args(), f"{self.host}:{quoted}", str(local_path)],
            timeout=timeout,
        )

    def _remote_status(self):
        path = shlex.quote(f"{self.job_dir}/status.json")
        proc = self._ssh(f"cat {path}", timeout=45, check=False)
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError:
            return {"state": "unknown", "message": "Сервер вернул некорректный статус"}

    def _save_status(self, state, message, **extra):
        payload = {
            "state": state,
            "message": message,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            **extra,
        }
        directory = Path(self.session["directory"])
        try:
            atomic_write_json(directory / "remote_status.json", payload, indent=2,
                              ensure_ascii=False)
        except OSError:
            pass
        self.progress.emit(message)

    def _request_data(self, audio_map):
        directory = Path(self.session["directory"])
        notes_path = directory / "notes.txt"
        notes = ""
        if notes_path.exists():
            try:
                notes = notes_path.read_text(encoding="utf-8")
            except OSError:
                pass
        started = self.session.get("started_at") or datetime.now().isoformat()
        name = self.session.get("name") or self.session.get("title")
        if not name:
            try:
                stamp = datetime.fromisoformat(started).strftime("%d.%m.%Y %H:%M")
            except (TypeError, ValueError):
                stamp = self.job_id
            name = f"Встреча {stamp}"
        return {
            "id": self.job_id,
            "name": name,
            "participants": self.session.get("participants", ""),
            "started_at": started,
            "stopped_at": self.session.get("stopped_at"),
            "duration": self.session.get("duration", 0),
            "capture_mode": self.session.get("capture_mode", ""),
            "audio": audio_map,
            "notes": notes,
            "language": self.config.get("transcription", "language") or "ru",
            "send_telegram": bool(self.config.get("remote", "send_telegram")),
            "chat_id": self.config.get("remote", "chat_id") or "678675695",
            "allow_obsidian": bool(self.config.get("remote", "allow_obsidian")),
            "allow_tasks": bool(self.config.get("remote", "allow_tasks")),
        }

    def _upload(self):
        directory = Path(self.session["directory"])
        audio_files = self.session.get("audio_files") or {}
        audio_map = {}
        roles = [role for role in ("mic", "system") if audio_files.get(role)]
        if not roles:
            roles = ["combined"]
        for role in roles:
            source = audio_files.get(role)
            if source and Path(source).is_file() and Path(source).stat().st_size > 44:
                suffix = Path(source).suffix.lower()
                if suffix not in (".wav", ".mp3"):
                    continue
                audio_map[role] = f"{role}{suffix}"
        if not audio_map:
            raise RuntimeError("В папке записи нет аудиофайлов для отправки")

        request_path = directory / "remote_request.json"
        atomic_write_json(request_path, self._request_data(audio_map), indent=2,
                          ensure_ascii=False)

        self._ssh(
            f"mkdir -p {shlex.quote(self.base + '/uploads')} "
            f"{shlex.quote(self.base + '/jobs')}"
        )
        existing = self._ssh(f"test -d {shlex.quote(self.job_dir)}", check=False)
        if existing.returncode == 0:
            self._save_status("queued", "Запись уже на сервере — продолжаю отслеживание")
            return

        upload_dir = f"{self.base}/uploads/{self.job_id}.part"
        quoted_upload = shlex.quote(upload_dir)
        self._ssh(f"rm -rf {quoted_upload} && mkdir -p {quoted_upload}")
        try:
            self._save_status("uploading", "Отправка записи на сервер…")
            self._scp(request_path, f"{self.host}:{upload_dir}/request.json")
            for role, remote_name in audio_map.items():
                self._save_status("uploading", f"Отправка аудио: {role}…")
                self._scp(audio_files[role], f"{self.host}:{upload_dir}/{remote_name}")
            self._ssh(f"mv {quoted_upload} {shlex.quote(self.job_dir)}")
        except Exception:
            # Неполная загрузка остаётся в uploads и не попадает в очередь.
            raise
        self._save_status("queued", "Запись загружена — ожидает обработки на сервере")

    def _api_upload(self):
        directory = Path(self.session["directory"])
        audio_files = self.session.get("audio_files") or {}
        audio_map = {}
        roles = [role for role in ("mic", "system") if audio_files.get(role)]
        if not roles:
            roles = ["combined"]
        for role in roles:
            source = audio_files.get(role)
            if source and Path(source).is_file() and Path(source).stat().st_size > 44:
                audio_map[role] = f"{role}.wav"
        if not audio_map:
            raise RuntimeError("В папке записи нет аудиофайлов для отправки")

        client = self.api_client
        request_data = self._request_data(audio_map)
        request_data["client_id"] = request_data.pop("id")
        if self.api_job_id:
            request_data["server_job_id"] = self.api_job_id
        if not self.api_job_id:
            response = client.create_job(request_data)
            self.api_job_id = response["job_id"]
            request_data["server_job_id"] = self.api_job_id
        atomic_write_json(directory / "remote_request.json", request_data,
                          indent=2, ensure_ascii=False)
        for role in audio_map:
            self._save_status("uploading", f"Отправка аудио: {role}…")
            client.upload_audio(self.api_job_id, role, audio_files[role])
        client.complete_job(self.api_job_id)
        self._save_status("queued", "Запись загружена — ожидает обработки на сервере")

    def _api_remote_status(self):
        if not self.api_job_id:
            return None
        try:
            return self.api_client.status(self.api_job_id)
        except RuntimeError as exc:
            if "не найдена" in str(exc).lower():
                return None
            raise

    def _api_download_results(self):
        directory = Path(self.session["directory"])
        client = self.api_client
        client.download(self.api_job_id, "result.json", directory / "result.json")
        result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        for name in result.get("artifacts") or []:
            if Path(name).name == name:
                client.download(self.api_job_id, name, directory / name)
        return result

    def _run_api(self):
        try:
            status = self._api_remote_status()
            if not status or status.get("state") not in ("done", "error"):
                self._api_upload()
            deadline = time.monotonic() + 12 * 60 * 60
            last_message = None
            while not self._stop_requested and time.monotonic() < deadline:
                status = self._api_remote_status()
                if status:
                    state = status.get("state", "unknown")
                    message = status.get("message") or state
                    if message != last_message:
                        self._save_status(state, message)
                        last_message = message
                    if state == "error":
                        raise RuntimeError(status.get("error") or message)
                    if state == "done":
                        self._save_status("downloading", "Скачиваю расшифровку и разбор…")
                        result = self._api_download_results()
                        self._save_status("done", "Готово: расшифровка и разбор сохранены")
                        self.finished.emit({
                            "session": self.session,
                            "result": result,
                            "directory": str(Path(self.session["directory"])),
                        })
                        return
                time.sleep(5)
            if self._stop_requested:
                raise RuntimeError("Отслеживание остановлено; обработка на сервере продолжится")
            raise RuntimeError("Время ожидания истекло; запись сохранена на сервере")
        except Exception as exc:
            message = str(exc)
            self._save_status("error", f"Ошибка серверной обработки: {message}")
            self.error.emit(message)

    def _download_results(self):
        directory = Path(self.session["directory"])
        result_path = directory / "result.json"
        self._download("result.json", result_path)
        result = json.loads(result_path.read_text(encoding="utf-8"))
        artifacts = result.get("artifacts") or [
            "transcript.json", "transcript.md", "summary.md",
            "action_items.json", "obsidian_note.md",
        ]
        for name in artifacts:
            if Path(name).name != name:
                continue
            self._download(name, directory / name)
        return result

    def run(self):
        if self.api_mode:
            self._run_api()
            return
        try:
            status = self._remote_status()
            if not status or status.get("state") not in ("done", "error"):
                self._upload()
            deadline = time.monotonic() + 12 * 60 * 60
            last_message = None
            while not self._stop_requested and time.monotonic() < deadline:
                status = self._remote_status()
                if status:
                    state = status.get("state", "unknown")
                    message = status.get("message") or state
                    if message != last_message:
                        self._save_status(state, message)
                        last_message = message
                    if state == "error":
                        raise RuntimeError(status.get("error") or message)
                    if state == "done":
                        self._save_status("downloading", "Скачиваю расшифровку и разбор…")
                        result = self._download_results()
                        self._save_status("done", "Готово: расшифровка и разбор сохранены")
                        self.finished.emit({
                            "session": self.session,
                            "result": result,
                            "directory": str(Path(self.session["directory"])),
                        })
                        return
                else:
                    message = "Запись в очереди — сервер скоро начнёт обработку"
                    if message != last_message:
                        self._save_status("queued", message)
                        last_message = message
                time.sleep(10)
            if self._stop_requested:
                raise RuntimeError("Отслеживание остановлено; обработка на сервере продолжится")
            raise RuntimeError("Время ожидания истекло; запись сохранена на сервере")
        except Exception as exc:
            message = str(exc)
            self._save_status("error", f"Ошибка серверной обработки: {message}")
            self.error.emit(message)
