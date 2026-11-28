"""Повторный разбор готовой расшифровки на сервере без Whisper."""
import json
import os
import sys
from pathlib import Path

from meeting_worker import analyze_meeting, normalize_analysis, build_summary

if len(sys.argv) > 2:
    os.environ["GEMINI_MODEL"] = sys.argv[2]

job_dir = Path(sys.argv[1])
request = json.loads((job_dir / "request.json").read_text(encoding="utf-8"))
transcript = json.loads((job_dir / "transcript.json").read_text(encoding="utf-8"))
lines = [
    f"[{s['start']}] {s.get('speaker') or 'Участник'}: {s['text']}"
    for s in transcript["segments"]
]
analysis = normalize_analysis(analyze_meeting(request, "\n".join(lines)), request)
(job_dir / "reanalysis.json").write_text(
    json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8",
)
(job_dir / "summary_new.md").write_text(build_summary(analysis, request), encoding="utf-8")
(job_dir / "action_items_new.json").write_text(
    json.dumps(analysis["tasks"], ensure_ascii=False, indent=2), encoding="utf-8",
)
print("TASKS", len(analysis["tasks"]), flush=True)
print(build_summary(analysis, request), flush=True)
