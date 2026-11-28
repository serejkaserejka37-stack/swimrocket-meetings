"""Применяет проверенный повторный разбор без изменения аудио и публикации в Obsidian."""
import json
import sys
from pathlib import Path

from meeting_worker import (
    atomic_json, atomic_text, build_obsidian_note, build_summary,
    send_telegram,
)

job_dir = Path(sys.argv[1])
request = json.loads((job_dir / "request.json").read_text(encoding="utf-8"))
analysis = json.loads((job_dir / "reanalysis.json").read_text(encoding="utf-8"))
transcript_md = (job_dir / "transcript.md").read_text(encoding="utf-8")
summary = "🔄 Исправленный разбор встречи\n\n" + build_summary(analysis, request)
for name in ("summary.md", "action_items.json", "obsidian_note.md", "result.json"):
    original = job_dir / name
    if original.exists():
        backup = job_dir / (name.replace(".", "_initial."))
        if not backup.exists():
            backup.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")

atomic_text(job_dir / "summary.md", summary)
atomic_json(job_dir / "action_items.json", analysis["tasks"])
note = build_obsidian_note(analysis, request, summary, transcript_md)
atomic_text(job_dir / "obsidian_note.md", note)
result_path = job_dir / "result.json"
result = json.loads(result_path.read_text(encoding="utf-8"))
result.update({
    "title": analysis["title"],
    "llm_error": None,
    "analysis_version": int(result.get("analysis_version", 1)) + 1,
})
if not result.get("obsidian_synced"):
    result["obsidian_status"] = "pending"
atomic_json(result_path, result)
status = send_telegram(
    job_dir / "summary.md",
    with_button=bool(analysis["tasks"]) and request.get("allow_tasks", True),
    with_obsidian=request.get("allow_obsidian", True),
    chat_id=request.get("chat_id", "678675695"),
)
result["telegram_status"] = status
atomic_json(result_path, result)
print(json.dumps({"tasks": len(analysis["tasks"]), "telegram": status}, ensure_ascii=False))
