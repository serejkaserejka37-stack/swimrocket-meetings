import json
import sys
import threading
import types
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))

from app.api_client import ApiClient


def test_colleague_full_api_flow_and_job_isolation(tmp_path, monkeypatch):
    fake_fcntl = types.SimpleNamespace(LOCK_EX=1, flock=lambda *args: None)
    monkeypatch.setitem(sys.modules, "fcntl", fake_fcntl)
    import user_registry
    import meeting_api

    monkeypatch.setattr(user_registry, "USERS_DIR", tmp_path / "users")
    monkeypatch.setattr(user_registry, "PENDING_FILE", tmp_path / "users" / "pending.json")
    monkeypatch.setattr(user_registry, "TOKENS_FILE", tmp_path / "users" / "tokens.json")
    monkeypatch.setattr(user_registry, "LOCK_FILE", tmp_path / "users" / ".lock")
    monkeypatch.setattr(meeting_api, "UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(meeting_api, "JOBS", tmp_path / "jobs")

    server = meeting_api.ThreadingHTTPServer(("127.0.0.1", 0), meeting_api.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        code = user_registry.create_setup_code(111222, "Тестовый коллега")
        exchanged = ApiClient.exchange_code(base, code)
        assert exchanged["chat_id"] == 111222
        client = ApiClient(base, exchanged["token"])
        assert client.me()["display_name"] == "Тестовый коллега"

        created = client.create_job({
            "client_id": "recording_test",
            "name": "Тестовая встреча",
            "participants": "Коллега",
            "started_at": "2026-11-26T20:00:00",
            "audio": {},
        })
        job_id = created["job_id"]
        wav = tmp_path / "mic.wav"
        wav.write_bytes(b"RIFF" + b"0" * 100)
        client.upload_audio(job_id, "mic", wav)
        client.complete_job(job_id)
        job_dir = tmp_path / "jobs" / job_id
        request = json.loads((job_dir / "request.json").read_text(encoding="utf-8"))
        assert request["allow_obsidian"] is False
        assert request["allow_tasks"] is False
        assert request["chat_id"] == 111222

        (job_dir / "status.json").write_text(json.dumps({"state": "done", "message": "Готово"}), encoding="utf-8")
        result = {"id": job_id, "state": "done", "artifacts": ["summary.md"]}
        (job_dir / "result.json").write_text(json.dumps(result), encoding="utf-8")
        (job_dir / "summary.md").write_text("Тестовая сводка", encoding="utf-8")
        assert client.status(job_id)["state"] == "done"
        target = tmp_path / "downloaded.md"
        client.download(job_id, "summary.md", target)
        assert target.read_text(encoding="utf-8") == "Тестовая сводка"

        other_code = user_registry.create_setup_code(999888, "Другой пользователь")
        other = ApiClient(base, ApiClient.exchange_code(base, other_code)["token"])
        with pytest.raises(RuntimeError, match="Нет доступа"):
            other.status(job_id)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
