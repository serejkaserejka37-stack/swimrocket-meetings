"""Еженедельная очистка аудио с сохранением всех результатов обработки."""
import argparse
import datetime as dt
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
AUDIO_SUFFIXES = {".wav", ".mp3", ".mp4", ".avi", ".uploading"}
SKIP_STATES = {"queued", "processing", "uploading"}


def read_state(job_dir):
    try:
        return json.loads((job_dir / "status.json").read_text(encoding="utf-8")).get("state", "")
    except (OSError, json.JSONDecodeError):
        return ""


def should_clean(job_dir, now):
    state = read_state(job_dir)
    if state in SKIP_STATES:
        return False
    if state in ("done", "telegram_error"):
        return True
    # Зависшие/старые записи можно чистить только спустя неделю.
    newest = max((p.stat().st_mtime for p in job_dir.iterdir() if p.is_file()), default=0)
    return (now - dt.datetime.fromtimestamp(newest, dt.timezone.utc).timestamp()) >= 7 * 86400


def clean(root, dry_run=True):
    now = dt.datetime.now(dt.timezone.utc).timestamp()
    deleted = []
    skipped = []
    for group in ("jobs", "uploads"):
        base = root / group
        if not base.is_dir():
            continue
        for job_dir in base.iterdir():
            if not job_dir.is_dir():
                continue
            if group == "jobs" and not should_clean(job_dir, now):
                skipped.append(job_dir.name)
                continue
            if group == "uploads":
                newest = max((p.stat().st_mtime for p in job_dir.iterdir() if p.is_file()), default=0)
                if now - newest < 86400:
                    skipped.append(job_dir.name)
                    continue
            for path in job_dir.iterdir():
                if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
                    deleted.append((path, path.stat().st_size))
                    if not dry_run:
                        path.unlink()
    return deleted, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=BASE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    deleted, skipped = clean(args.root, dry_run=args.dry_run)
    summary = {
        "date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "dry_run": args.dry_run,
        "deleted_files": len(deleted),
        "deleted_bytes": sum(size for _, size in deleted),
        "skipped_active_jobs": len(skipped),
        "results_preserved": [
            "request.json", "result.json", "status.json", "transcript.json",
            "transcript.md", "summary.md", "action_items.json", "obsidian_note.md",
        ],
    }
    line = json.dumps(summary, ensure_ascii=False)
    print(line)
    log = args.root / "audio_cleanup.log"
    with log.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


if __name__ == "__main__":
    main()
