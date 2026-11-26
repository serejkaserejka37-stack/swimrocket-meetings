import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))

from app.utils.meeting_detector import detect_meeting
from server import meeting_worker


def test_zoom_audio_starts_detection():
    result = detect_meeting({10}, [], {10: "Zoom.exe"})
    assert result["audio_active"] is True
    assert result["label"] == "Zoom"


def test_regular_browser_audio_is_not_a_meeting():
    result = detect_meeting({20}, [(20, "YouTube — видео")], {20: "chrome.exe"})
    assert result["audio_active"] is False
    assert result["present"] is False


def test_telemost_window_keeps_meeting_alive_without_audio():
    result = detect_meeting(set(), [(20, "Встреча — Яндекс Телемост")], {20: "chrome.exe"})
    assert result["audio_active"] is False
    assert result["present"] is True
    assert result["label"] == "Яндекс Телемост"


def test_telemost_desktop_audio_is_detected():
    result = detect_meeting({30}, [], {30: "YandexTelemost.exe"})
    assert result["audio_active"] is True


def _job(tmp_path):
    job = tmp_path / "job"
    job.mkdir()
    (job / "mic.wav").write_bytes(b"RIFF" + b"0" * 100)
    (job / "system.wav").write_bytes(b"RIFF" + b"0" * 100)
    request = {
        "id": "20261126_120000",
        "name": "Планёрка",
        "participants": "Сергей, Вера",
        "started_at": "2026-11-26T12:00:00+03:00",
        "audio": {"mic": "mic.wav", "system": "system.wav"},
        "language": "ru",
        "send_telegram": False,
        "notes": "",
    }
    (job / "request.json").write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    return job


def _transcribe(path, language):
    if path.name == "mic.wav":
        segments = [{"start": 2.0, "end": 3.0, "text": "Сергей говорит"}]
    else:
        segments = [{"start": 1.0, "end": 2.0, "text": "Вера говорит"}]
    return {"segments": segments, "language": "ru", "duration": 3.0}


def _analysis(request, text):
    return {
        "title": "Планёрка по продукту",
        "participants": ["Сергей", "Вера"],
        "key_points": ["Обсудили запуск"],
        "decisions": ["Запускаем пилот"],
        "tasks": [{"task": "Подготовить план", "assignee": "Вера", "deadline": "завтра"}],
        "open_questions": ["Когда проверить результат?"],
    }


def test_server_job_creates_all_results_without_local_models(tmp_path):
    job = _job(tmp_path)
    result = meeting_worker.process_job(
        job, transcribe_fn=_transcribe, llm_fn=_analysis, publish=False,
    )
    transcript = json.loads((job / "transcript.json").read_text(encoding="utf-8"))
    assert [s["speaker"] for s in transcript["segments"]] == ["Собеседники", "Сергей"]
    assert "Подготовить план" in (job / "summary.md").read_text(encoding="utf-8")
    assert (job / "obsidian_note.md").is_file()
    assert result["state"] == "done"
    assert result["telegram_status"] == "disabled"
    status = json.loads((job / "status.json").read_text(encoding="utf-8"))
    assert status["state"] == "done"


def test_llm_failure_preserves_transcript_and_does_not_invent_tasks(tmp_path):
    job = _job(tmp_path)

    def fail_llm(request, text):
        raise RuntimeError("тестовый сбой")

    result = meeting_worker.process_job(
        job, transcribe_fn=_transcribe, llm_fn=fail_llm, publish=False,
    )
    assert result["state"] == "done"
    assert result["llm_error"] == "тестовый сбой"
    assert json.loads((job / "action_items.json").read_text(encoding="utf-8")) == []
    assert "Вера говорит" in (job / "transcript.md").read_text(encoding="utf-8")


def test_naive_laptop_time_is_moscow_not_server_utc():
    request = {"started_at": "2026-11-26T15:08:11"}
    assert meeting_worker.started_msk(request).strftime("%H:%M") == "15:08"


def test_exact_microphone_echo_is_removed_in_favour_of_system_channel():
    transcript = meeting_worker.merge_channels({
        "mic": {"segments": [{"start": 1, "end": 2, "text": "Та же самая фраза собеседника"}]},
        "system": {"segments": [{"start": 1, "end": 2, "text": "Та же самая фраза собеседника"}]},
    })
    assert len(transcript["segments"]) == 1
    assert transcript["segments"][0]["speaker"] == "Собеседники"


def test_telegram_failure_preserves_results_and_retries_delivery_only(tmp_path, monkeypatch):
    job = _job(tmp_path)
    request_path = job / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["send_telegram"] = True
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    transcribe_calls = []

    def counted_transcribe(path, language):
        transcribe_calls.append(path.name)
        return _transcribe(path, language)

    monkeypatch.setattr(meeting_worker, "save_to_vault", lambda *args: ("test.md", True))

    def fail_telegram(path, with_button=True, with_obsidian=True, chat_id=None):
        raise RuntimeError("Telegram временно недоступен")

    monkeypatch.setattr(meeting_worker, "send_telegram", fail_telegram)
    result = meeting_worker.process_job(
        job, transcribe_fn=counted_transcribe, llm_fn=_analysis, publish=True,
    )
    assert result["state"] == "telegram_error"
    assert result["telegram_status"] == "error"
    assert (job / "transcript.json").is_file()
    assert (job / "summary.md").is_file()
    assert (job / "obsidian_note.md").is_file()
    assert json.loads((job / "status.json").read_text(encoding="utf-8"))["state"] == "telegram_error"
    summary_before = (job / "summary.md").read_text(encoding="utf-8")
    calls_before = list(transcribe_calls)

    deliveries = []

    def succeed(path, with_button=True, with_obsidian=True, chat_id=None):
        deliveries.append((Path(path).name, with_button))
        return "OK: message_ids=[123]"

    monkeypatch.setattr(meeting_worker, "send_telegram", succeed)
    retried = meeting_worker.retry_telegram(job)
    assert retried["state"] == "done"
    assert retried["telegram_status"] == "OK: message_ids=[123]"
    assert "telegram_error" not in retried
    assert deliveries == [("summary.md", True)]
    assert transcribe_calls == calls_before
    assert (job / "summary.md").read_text(encoding="utf-8") == summary_before
    assert json.loads((job / "status.json").read_text(encoding="utf-8"))["state"] == "done"


def test_telegram_has_no_task_button_when_no_tasks(tmp_path, monkeypatch):
    job = _job(tmp_path)
    request_path = job / "request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["send_telegram"] = True
    request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(meeting_worker, "save_to_vault", lambda *args: ("test.md", True))
    deliveries = []

    def succeed(path, with_button=True, with_obsidian=True, chat_id=None):
        deliveries.append(with_button)
        return "OK: message_ids=[124]"

    def no_tasks(request, text):
        analysis = _analysis(request, text)
        analysis["tasks"] = []
        return analysis

    monkeypatch.setattr(meeting_worker, "send_telegram", succeed)
    result = meeting_worker.process_job(
        job, transcribe_fn=_transcribe, llm_fn=no_tasks, publish=True,
    )
    assert result["state"] == "done"
    assert deliveries == [False]
    summary = (job / "summary.md").read_text(encoding="utf-8")
    assert "нажмите кнопку" not in summary


def test_delayed_microphone_echo_is_removed_too():
    transcript = meeting_worker.merge_channels({
        "system": {"segments": [{"start": 1.0, "end": 2.0, "text": "Фраза собеседника из динамиков"}]},
        "mic": {"segments": [{"start": 2.0, "end": 3.0, "text": "Фраза собеседника из динамиков"}]},
    })
    assert len(transcript["segments"]) == 1
    assert transcript["segments"][0]["speaker"] == "Собеседники"


def test_same_words_apart_in_time_are_not_removed():
    transcript = meeting_worker.merge_channels({
        "system": {"segments": [{"start": 1.0, "end": 2.0, "text": "Повторяющаяся фраза встречи"}]},
        "mic": {"segments": [{"start": 8.0, "end": 9.0, "text": "Повторяющаяся фраза встречи"}]},
    })
    assert len(transcript["segments"]) == 2


def test_incoming_queue_retries_telegram_without_processing_job(tmp_path, monkeypatch):
    import importlib
    import types

    fake_fcntl = types.SimpleNamespace(
        LOCK_EX=1, LOCK_NB=2, flock=lambda *args: None,
    )
    monkeypatch.setitem(sys.modules, "fcntl", fake_fcntl)
    incoming = importlib.import_module("server.process_incoming")
    job = _job(tmp_path)
    meeting_worker.update_status(job, "telegram_error", "Нужен повтор Telegram")
    meeting_worker.atomic_json(job / "result.json", {
        "id": "20261126_120000", "state": "telegram_error",
        "telegram_status": "error", "obsidian_synced": True,
    })
    monkeypatch.setattr(incoming, "BASE", tmp_path)
    monkeypatch.setattr(incoming, "JOBS", tmp_path)
    monkeypatch.setattr(incoming, "LOCK", tmp_path / ".processor.lock")
    monkeypatch.setattr(incoming, "LOG", tmp_path / "processor.log")
    retried = []

    def should_not_process(job):
        raise AssertionError("Whisper/LLM не должны запускаться повторно")

    monkeypatch.setattr(incoming, "process_job", should_not_process)
    monkeypatch.setattr(
        incoming, "retry_telegram",
        lambda job: retried.append(job.name) or {"id": "20261126_120000"},
    )
    assert incoming.main() == 0
    assert retried == ["job"]


def test_gemini_provider_sends_prompt_and_returns_json_text(monkeypatch):
    import io

    values = {
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-test-flash",
    }
    monkeypatch.setattr(meeting_worker, "_env_value", lambda name: values.get(name))
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data)
        captured["timeout"] = timeout
        response = {"candidates": [{"content": {"parts": [{"text": '{"title":"Тест"}'}]}}]}
        return io.BytesIO(json.dumps(response).encode())

    monkeypatch.setattr(meeting_worker.urllib.request, "urlopen", fake_urlopen)
    raw = meeting_worker.gemini_complete("Разбери встречу")
    assert json.loads(raw) == {"title": "Тест"}
    assert "models/gemini-test-flash:generateContent" in captured["url"]
    assert captured["body"]["contents"][0]["parts"][0]["text"] == "Разбери встречу"
    assert captured["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert captured["timeout"] == 180


def test_gemini_empty_response_is_an_error(monkeypatch):
    import io

    values = {"GEMINI_API_KEY": "test-key", "GEMINI_MODEL": "gemini-test-flash"}
    monkeypatch.setattr(meeting_worker, "_env_value", lambda name: values.get(name))
    monkeypatch.setattr(
        meeting_worker.urllib.request, "urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps({"candidates": []}).encode()),
    )
    with pytest.raises(RuntimeError, match="пустой ответ Gemini"):
        meeting_worker.gemini_complete("Разбери встречу")


def test_zoom_conference_window_is_enough_without_audio():
    result = detect_meeting(set(), [(7504, "Zoom Конференция")], {7504: "Zoom.exe"})
    assert result["audio_active"] is False
    assert result["present"] is True
    assert result["label"] == "Zoom"


def test_monitor_starts_recording_on_conference_window_without_audio():
    from app.meeting_monitor import MeetingMonitor

    class Config:
        def get(self, section, key):
            values = {"auto_record": True, "auto_record_threshold": 0}
            return values[key]

    class Detector:
        start_delay = 0

        def poll(self):
            return {"audio_active": False, "present": True, "label": "Zoom"}

    monitor = MeetingMonitor(Config())
    monitor.detector = Detector()
    starts = []
    monitor.auto_start_requested.connect(starts.append)
    monitor.poll()
    assert starts == ["Zoom"]
    assert monitor.tracking is True
