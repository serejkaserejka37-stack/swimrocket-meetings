"""Повторная отправка сохранённой записи через HTTPS API."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.remote_processing import RemoteProcessingWorker
from app.utils.config import Config

session_dir = ROOT / "recordings" / "recording_20261127_150447"
session = json.loads((session_dir / "metadata.json").read_text(encoding="utf-8"))
config = Config()
worker = RemoteProcessingWorker(session, config)
errors, results = [], []
worker.progress.connect(lambda message: print("STATUS", message, flush=True))
worker.error.connect(lambda message: (errors.append(message), print("ERROR", message, flush=True)))
worker.finished.connect(lambda result: results.append(result))
worker.run()
if errors or not results:
    raise RuntimeError(errors[-1] if errors else "Нет результата")
print("RESUME_OK", json.dumps(results[0]["result"], ensure_ascii=False), flush=True)
