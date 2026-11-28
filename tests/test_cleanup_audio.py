import json
import os
from pathlib import Path

from server.cleanup_audio import clean


def _job(root, name, state):
    directory = root / "jobs" / name
    directory.mkdir(parents=True)
    (directory / "status.json").write_text(json.dumps({"state": state}), encoding="utf-8")
    for filename in (
        "mic.wav", "system.wav", "combined.wav", "request.json", "result.json",
        "transcript.json", "transcript.md", "summary.md", "action_items.json",
        "obsidian_note.md",
    ):
        (directory / filename).write_text("test", encoding="utf-8")
    return directory


def test_cleanup_deletes_only_audio_and_preserves_all_results(tmp_path):
    done = _job(tmp_path, "done", "done")
    active = _job(tmp_path, "active", "processing")
    deleted, skipped = clean(tmp_path, dry_run=False)
    assert not (done / "mic.wav").exists()
    assert not (done / "system.wav").exists()
    assert not (done / "combined.wav").exists()
    for name in (
        "request.json", "result.json", "status.json", "transcript.json",
        "transcript.md", "summary.md", "action_items.json", "obsidian_note.md",
    ):
        assert (done / name).is_file(), name
        assert (active / name).is_file(), name
    assert (active / "mic.wav").is_file()
    assert "active" in skipped


def test_upload_fragments_are_preserved_for_24_hours(tmp_path):
    upload = tmp_path / "uploads" / "job.part"
    upload.mkdir(parents=True)
    audio = upload / "mic.uploading"
    audio.write_bytes(b"audio")
    deleted, skipped = clean(tmp_path, dry_run=False)
    assert audio.exists()
    old = __import__("time").time() - 90000
    os.utime(audio, (old, old))
    clean(tmp_path, dry_run=False)
    assert not audio.exists()
