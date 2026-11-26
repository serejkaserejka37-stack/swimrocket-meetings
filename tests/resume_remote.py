import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.utils.config import Config
from app.remote_processing import RemoteProcessingWorker


class TestConfig(Config):
    def get(self, *keys):
        if keys == ("remote", "send_telegram"):
            return False
        return super().get(*keys)


directory = Path(sys.argv[1])
session = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
worker = RemoteProcessingWorker(session, TestConfig())
errors = []
results = []
worker.progress.connect(lambda message: print("STATUS", message, flush=True))
worker.error.connect(errors.append)
worker.finished.connect(results.append)
worker.run()
if errors or not results:
    raise RuntimeError(errors[-1] if errors else "Нет результата")
print("RESULT", json.dumps(results[0]["result"], ensure_ascii=False), flush=True)
print("TRANSCRIPT", (directory / "transcript.md").read_text(encoding="utf-8"), flush=True)
print("SUMMARY", (directory / "summary.md").read_text(encoding="utf-8"), flush=True)
print("RESUME_OK", flush=True)
