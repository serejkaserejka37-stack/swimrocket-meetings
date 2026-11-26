import copy
import json
import os
import sys
from pathlib import Path


def default_output_directory():
    """В portable-сборке записи не должны попадать во временный каталог."""
    if getattr(sys, "frozen", False):
        return str(Path.home() / "Documents" / "SwimRocket" / "Recordings")
    return str(Path(__file__).parent.parent.parent / "recordings")


DEFAULT_CONFIG = {
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "mic_device": None,
        "loopback_device": None,
        "last_mic": "",
        "last_mic2": "",
        # Общий системный канал нужен для Zoom: per-app capture может вернуть тишину.
        "capture_mode": "legacy",
        "selected_apps": ["Zoom"],
        "hidden_devices": [],
        "mic_count": 1,
        "mic_mute_on_start": False,
        "mic_gain": 1.0,
    },
    "output": {
        "directory": default_output_directory(),
        "format": "wav",
        "filename_template": "recording_{timestamp}",
    },
    "transcription": {
        "model_size": "small",
        "language": "ru",
        "device": "cpu",
        "min_duration": 5,
        "batch_size": 1,
    },
    "diarization": {
        "enabled": False,
        "hf_token": "",
        "min_speakers": None,
        "max_speakers": None,
    },
    "ai": {
        "provider": "none",
        "api_key": "",
        "model": "",
        "local_model_path": "",
        "embed_model": "all-MiniLM-L6-v2",
        "auto_summarize": False,
        "provider_settings": {},
    },
    "remote": {
        "mode": "api",
        "server_url": "https://meetings.179.252.208.207.sslip.io",
        "api_token": "",
        "chat_id": "",
        "allow_obsidian": False,
        "allow_tasks": False,
        "setup_complete": False,
        "host": "root@100.76.227.97",
        "directory": "/root/SwimRocket/meeting_processor",
        "send_telegram": True,
    },
    "general": {
        "min_recording_length": 5,
        "auto_record": True,
        "auto_record_threshold": 5,
        "auto_transcribe": True,
        "silence_auto_stop": True,
        "silence_duration": 120,
        "minimize_to_tray": False,
        "show_tray_hint": True,
        "start_menu_offer_done": True,
    },
    "ui": {
        "theme": "dark",
        "speakers_collapsed": False,
    },
}

CONFIG_DIR = Path.home() / ".swimrocket-meetings"
CONFIG_FILE = CONFIG_DIR / "settings.json"


class Config:
    def __init__(self):
        self._data = {}
        self.load()

    def load(self):
        self._data = None
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r") as f:
                    saved = json.load(f)
                if not isinstance(saved, dict):
                    raise ValueError("settings root is not an object")
                self._data = self._deep_merge(DEFAULT_CONFIG, saved)
            except (json.JSONDecodeError, ValueError, OSError):
                self._backup_corrupt_file()
        if self._data is None:
            self._data = copy.deepcopy(DEFAULT_CONFIG)
        try:
            os.makedirs(self._data["output"]["directory"], exist_ok=True)
        except OSError:
            self._data["output"]["directory"] = DEFAULT_CONFIG["output"]["directory"]
            os.makedirs(self._data["output"]["directory"], exist_ok=True)

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = CONFIG_FILE.parent / (CONFIG_FILE.name + ".tmp")
        with open(tmp_path, "w") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp_path, CONFIG_FILE)
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except OSError:
            pass

    def _backup_corrupt_file(self):
        try:
            backup = CONFIG_FILE.parent / (CONFIG_FILE.name + ".bak")
            os.replace(CONFIG_FILE, backup)
        except OSError:
            pass

    def get(self, *keys):
        value = self._data
        for key in keys:
            value = value[key]
        return value

    def set(self, *keys_and_value):
        keys = keys_and_value[:-1]
        value = keys_and_value[-1]
        d = self._data
        for key in keys[:-1]:
            d = d[key]
        d[keys[-1]] = value
        self.save()

    @property
    def data(self):
        return self._data

    def _deep_merge(self, base, override):
        # Deep-copy so missing sections don't alias (and later mutate)
        # the module-global DEFAULT_CONFIG through Config.set().
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
