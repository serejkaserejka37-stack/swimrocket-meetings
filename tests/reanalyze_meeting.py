"""Повторный разбор готовой расшифровки без повторной обработки аудио."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "server"))

from server.meeting_worker import analyze_meeting, normalize_analysis, build_summary

session_dir = ROOT / "recordings" / "recording_20261127_150447"
request = json.loads((session_dir / "remote_request.json").read_text(encoding="utf-8"))
transcript = json.loads((session_dir / "transcript.json").read_text(encoding="utf-8"))
lines = [
    f"[{s['start']}] {s.get('speaker') or 'Участник'}: {s['text']}"
    for s in transcript["segments"]
]
analysis = normalize_analysis(analyze_meeting(request, "\n".join(lines)), request)
(session_dir / "reanalysis.json").write_text(
    json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8",
)
(session_dir / "summary_new.md").write_text(build_summary(analysis, request), encoding="utf-8")
(session_dir / "action_items_new.json").write_text(
    json.dumps(analysis["tasks"], ensure_ascii=False, indent=2), encoding="utf-8",
)
print("TASKS", len(analysis["tasks"]), flush=True)
print("SUMMARY", build_summary(analysis, request), flush=True)
