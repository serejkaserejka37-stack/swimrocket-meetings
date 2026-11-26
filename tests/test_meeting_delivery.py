import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "tests"))

from server import meeting_worker, telegram_sender, meeting_bot_listener as listener
from test_swimrocket_meetings import _analysis, _job, _transcribe


def test_telegram_has_two_independent_job_buttons():
    markup = telegram_sender.build_keyboard("both", "meeting_123")
    rows = markup["inline_keyboard"]
    assert len(rows) == 2
    assert rows[0][0]["callback_data"] == "add_tasks:meeting_123"
    assert rows[1][0]["callback_data"] == "obsidian:meeting_123"
    assert rows[0][0]["text"] != rows[1][0]["text"]


def test_obsidian_is_not_published_automatically(tmp_path, monkeypatch):
    job = _job(tmp_path)
    request_path = job / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["send_telegram"] = True
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")

    def forbidden_vault(*args):
        raise AssertionError("Obsidian нельзя вызывать до кнопки")

    monkeypatch.setattr(meeting_worker, "save_to_vault", forbidden_vault)
    monkeypatch.setattr(
        meeting_worker, "send_telegram",
        lambda *args, **kwargs: "OK: message_ids=[200]",
    )
    result = meeting_worker.process_job(
        job, transcribe_fn=_transcribe, llm_fn=_analysis, publish=True,
    )
    assert result["state"] == "done"
    assert result["obsidian_status"] == "pending"
    assert result["obsidian_path"] == ""
    assert result["obsidian_synced"] is False


def _delivery_job(root, job_id, title):
    directory = root / job_id
    directory.mkdir(parents=True)
    result = {
        "id": job_id, "title": title, "state": "done",
        "obsidian_path": "", "obsidian_synced": False,
        "obsidian_status": "pending",
    }
    request = {"id": job_id, "name": title, "started_at": "2026-11-26T19:00:00"}
    (directory / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    (directory / "request.json").write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    (directory / "obsidian_note.md").write_text(f"# {title}\n", encoding="utf-8")
    (directory / "summary.md").write_text(
        f"🏊 {title}\n\n📋 ЗАДАЧИ С ВСТРЕЧИ:\n"
        "• Вера — Подготовить план — завтра\n\n❓ Открытые вопросы:\n— Нет\n",
        encoding="utf-8",
    )
    return directory


def test_obsidian_button_publishes_only_selected_job_once(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    first = _delivery_job(jobs, "job1", "Первая встреча")
    second = _delivery_job(jobs, "job2", "Конфиденциальная встреча")
    monkeypatch.setattr(listener, "JOBS", str(jobs))
    monkeypatch.setattr(listener, "BASE", str(tmp_path))
    monkeypatch.setattr(listener, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(listener, "MEETING_SERVER", str(ROOT / "server"))
    messages, buttons, published = [], [], []
    monkeypatch.setattr(listener, "say", messages.append)
    monkeypatch.setattr(listener, "update_buttons", lambda *args, **kwargs: buttons.append(kwargs))

    def fake_vault(note, request, title):
        published.append(title)
        return f"/vault/{title}.md", True

    import meeting_worker as listener_worker
    monkeypatch.setattr(listener_worker, "save_to_vault", fake_vault)
    msg = {"message_id": 55}
    listener.publish_obsidian("job1", msg)
    listener.publish_obsidian("job1", msg)

    assert published == ["Первая встреча"]
    first_result = json.loads((first / "result.json").read_text(encoding="utf-8"))
    second_result = json.loads((second / "result.json").read_text(encoding="utf-8"))
    assert first_result["obsidian_status"] == "published"
    assert first_result["obsidian_synced"] is True
    assert second_result["obsidian_status"] == "pending"
    assert second_result["obsidian_synced"] is False
    assert buttons[0]["obsidian_done"] is True
    assert buttons[0]["tasks_done"] is False
    assert any("уже опубликована" in message for message in messages)


def test_button_updates_preserve_other_action(monkeypatch):
    calls = []
    monkeypatch.setattr(listener, "api", lambda method, payload, timeout=30: calls.append(payload))
    msg = {"message_id": 77}
    listener.update_buttons(msg, "job1", tasks_done=True, obsidian_done=False)
    listener.update_buttons(msg, "job1", tasks_done=False, obsidian_done=True)
    first_rows = calls[0]["reply_markup"]["inline_keyboard"]
    second_rows = calls[1]["reply_markup"]["inline_keyboard"]
    assert first_rows[0][0]["callback_data"] == "noop"
    assert first_rows[1][0]["callback_data"] == "obsidian:job1"
    assert second_rows[0][0]["callback_data"] == "add_tasks:job1"
    assert second_rows[1][0]["callback_data"] == "noop"


def test_add_tasks_uses_selected_job_and_keeps_obsidian_button(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    directory = _delivery_job(jobs, "job1", "Встреча по продукту")
    monkeypatch.setattr(listener, "JOBS", str(jobs))
    monkeypatch.setattr(listener, "BASE", str(tmp_path))
    monkeypatch.setattr(listener, "STATE_FILE", str(tmp_path / "state.json"))
    monkeypatch.setattr(listener, "ADD_TASKS", str(tmp_path / "add_tasks.py"))
    monkeypatch.setattr(listener, "push_tasks_to_vault", lambda *args: True)
    buttons = []
    monkeypatch.setattr(listener, "update_buttons", lambda *args, **kwargs: buttons.append(kwargs))
    monkeypatch.setattr(listener, "say", lambda text: None)

    class Completed:
        returncode = 0
        stdout = "Внесено: 1"

    monkeypatch.setattr(listener.subprocess, "run", lambda *args, **kwargs: Completed())
    listener.handle_command({"message_id": 88}, "job1")
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    assert state["entered_for"] == "job:job1"
    assert buttons[0]["tasks_done"] is True
    assert buttons[0]["obsidian_done"] is False
    assert not (directory / "_tasks.json").exists()
