import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from server import meeting_bot_listener as listener


def _job(root, name, chat_id, message_ids, mtime):
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "request.json").write_text(json.dumps({"chat_id": chat_id}), encoding="utf-8")
    (directory / "result.json").write_text(json.dumps({
        "telegram_status": f"OK: message_ids: {message_ids}",
    }), encoding="utf-8")
    import os
    os.utime(directory / "result.json", (mtime, mtime))
    return directory


def test_feedback_phrases_are_recognized():
    assert listener.is_reanalysis_request("картина не полная")
    assert listener.is_reanalysis_request("Фидбек: мало задач")
    assert listener.is_reanalysis_request("не нравится анализ")
    assert not listener.is_reanalysis_request("фидбек: это была Алёна")


def test_job_is_selected_by_reply_and_latest_for_same_chat(tmp_path, monkeypatch):
    monkeypatch.setattr(listener, "JOBS", str(tmp_path))
    first = _job(tmp_path, "job1", 678675695, [61, 62], 100)
    second = _job(tmp_path, "job2", 678675695, [63, 64], 200)
    other = _job(tmp_path, "job3", 111222, [65], 300)
    assert listener.find_reanalysis_job({
        "chat": {"id": 678675695},
        "reply_to_message": {"message_id": 61},
    }) == "job1"
    assert listener.find_reanalysis_job({"chat": {"id": 678675695}}) == "job2"
    assert listener.find_reanalysis_job({"chat": {"id": 111222}}) == "job3"


def test_reanalysis_falls_back_to_available_model(tmp_path, monkeypatch):
    _job(tmp_path, "job1", 678675695, [61], 100)
    monkeypatch.setattr(listener, "JOBS", str(tmp_path))
    monkeypatch.setattr(listener, "REANALYZE", "reanalyze.py")
    monkeypatch.setattr(listener, "APPLY_REANALYSIS", "apply.py")
    messages = []
    monkeypatch.setattr(listener, "say_to", lambda chat_id, text: messages.append(text))
    calls = []

    class Completed:
        def __init__(self, code):
            self.returncode = code
            self.stdout = ""
            self.stderr = "503 Service Unavailable"

    def run(args, **kwargs):
        calls.append(args)
        return Completed(1 if "3.8" in args[-1] else 0)

    monkeypatch.setattr(listener.subprocess, "run", run)
    listener.handle_reanalysis({
        "chat": {"id": 678675695},
        "reply_to_message": {"message_id": 61},
    })
    assert calls[0][-1] == "gemini-3.8-flash"
    assert calls[1][-1] == "gemini-3.5-flash"
    assert calls[2] == [listener.PY, "apply.py", str(tmp_path / "job1")]
    assert any("уточнённый разбор" in message for message in messages)
