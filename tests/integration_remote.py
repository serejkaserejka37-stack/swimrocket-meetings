"""Реальный тест: Windows audio -> сервер Whisper -> разбор -> Obsidian.

Telegram специально отключён. Тест создаёт одну тестовую заметку в vault.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.utils.config import Config
from app.utils.audio_devices import get_default_mic, get_default_output
from app.recording.recorder import Recorder, RecordingState
from app.remote_processing import RemoteProcessingWorker


class TestConfig(Config):
    def get(self, *keys):
        if keys == ("remote", "send_telegram"):
            return False
        return super().get(*keys)


config = TestConfig()
output = ROOT / "test-recordings"
config.data["output"]["directory"] = str(output)
config.data["general"]["min_recording_length"] = 2
recorder = Recorder(config)
recorder.start_recording(
    mic_device=get_default_mic(),
    loopback_device=get_default_output(),
    capture_mode="legacy",
    name="Тест интеграции SwimRocket Встречи",
    participants="Сергей, Вера",
)
if recorder.state != RecordingState.RECORDING:
    raise RuntimeError("Запись не началась")
print("RECORDING_STARTED", flush=True)
text = (
    "Это тестовая встреча Свим Рокет. "
    "Мы решили начать пилот в понедельник. "
    "Сергей просит Веру подготовить план запуска завтра."
)
ps = (
    "Add-Type -AssemblyName System.Speech; "
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    "$s.Rate=0; "
    f"$s.Speak('{text}');"
)
speech = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps])
time.sleep(3)
speech.wait(timeout=25)
time.sleep(9)
recorder.stop_recording()
session = recorder._current_session
print("RECORDING_SAVED", json.dumps({
    "id": session["id"],
    "duration": session.get("duration"),
    "audio": {k: Path(v).stat().st_size for k, v in session.get("audio_files", {}).items()},
}, ensure_ascii=False), flush=True)

errors = []
results = []
worker = RemoteProcessingWorker(session, config)
worker.progress.connect(lambda message: print("STATUS", message, flush=True))
worker.error.connect(lambda message: (errors.append(message), print("ERROR", message, flush=True)))
worker.finished.connect(lambda result: results.append(result))
worker.run()
if errors or not results:
    raise RuntimeError(errors[-1] if errors else "Нет результата")
result_dir = Path(session["directory"])
print("RESULT", json.dumps(results[0]["result"], ensure_ascii=False), flush=True)
print("TRANSCRIPT", (result_dir / "transcript.md").read_text(encoding="utf-8"), flush=True)
print("SUMMARY", (result_dir / "summary.md").read_text(encoding="utf-8"), flush=True)
print("INTEGRATION_OK", result_dir, flush=True)
