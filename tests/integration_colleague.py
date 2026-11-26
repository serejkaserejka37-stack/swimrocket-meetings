"""Сквозной тест версии коллег: API без SSH, Telegram без Obsidian."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.api_client import ApiClient
from app.utils.config import Config
from app.utils.audio_devices import get_default_mic, get_default_output
from app.recording.recorder import Recorder, RecordingState
from app.remote_processing import RemoteProcessingWorker

code = os.environ.get("SR_SETUP_CODE")
if not code:
    raise RuntimeError("Нужен SR_SETUP_CODE для теста")
base_url = "https://meetings.179.252.208.207.sslip.io"
setup = ApiClient.exchange_code(base_url, code)


class TestConfig(Config):
    def get(self, *keys):
        if keys == ("remote", "mode"):
            return "api"
        return super().get(*keys)


config = TestConfig()
config.data["remote"]["server_url"] = base_url
config.data["remote"]["api_token"] = setup["token"]
config.data["remote"]["chat_id"] = str(setup["chat_id"])
config.data["output"]["directory"] = str(ROOT / "test-recordings")
config.data["general"]["min_recording_length"] = 2
recorder = Recorder(config)
recorder.start_recording(
    mic_device=get_default_mic(), loopback_device=get_default_output(),
    capture_mode="legacy", name="Тест коллеги SwimRocket Встречи",
    participants="Сергей, Вера",
)
if recorder.state != RecordingState.RECORDING:
    raise RuntimeError("Запись не началась")
print("RECORDING_STARTED", setup["user_id"], flush=True)
text = "Это тест подключения коллеги. Запись отправлена по защищенному API без SSH."
ps = (
    "Add-Type -AssemblyName System.Speech; "
    "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    f"$s.Speak('{text}');"
)
speech = subprocess.Popen(["powershell", "-NoProfile", "-Command", ps])
time.sleep(3)
speech.wait(timeout=25)
time.sleep(8)
recorder.stop_recording()
session = recorder._current_session
worker = RemoteProcessingWorker(session, config)
errors, results = [], []
worker.progress.connect(lambda message: print("STATUS", message, flush=True))
worker.error.connect(lambda message: (errors.append(message), print("ERROR", message, flush=True)))
worker.finished.connect(lambda result: results.append(result))
worker.run()
if errors or not results:
    raise RuntimeError(errors[-1] if errors else "Нет результата")
result_dir = Path(session["directory"])
print("RESULT", json.dumps(results[0]["result"], ensure_ascii=False), flush=True)
print("SUMMARY", (result_dir / "summary.md").read_text(encoding="utf-8"), flush=True)
print("COLLEAGUE_INTEGRATION_OK", result_dir, flush=True)
