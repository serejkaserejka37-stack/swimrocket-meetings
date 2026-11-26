"""Обнаружение Zoom и Яндекс Телемоста без ботов и API-паролей.

Для запуска достаточно окна конференции, активный звук не обязателен.
После начала встречи окно позволяет не останавливать запись во время
длительной тишины. Обычные страницы браузера без «Телемоста» игнорируются.
"""
import ctypes
import logging
import os
import platform
import subprocess

import psutil

logger = logging.getLogger(__name__)

BROWSERS = {"chrome", "msedge", "firefox", "browser", "yandex", "yandextelemost"}


def _base(name):
    name = (name or "").lower()
    return name[:-4] if name.endswith(".exe") else name


def _process_names():
    result = {}
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["pid"]:
                result[proc.info["pid"]] = _base(proc.info["name"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


def _active_audio_pids():
    try:
        from pycaw.pycaw import AudioUtilities
        sessions = AudioUtilities.GetAllSessions()
    except Exception as exc:
        logger.debug("Не удалось прочитать аудиосессии: %s", exc)
        return set()
    result = set()
    for session in sessions:
        try:
            if session.Process and session.Process.pid and session.State == 1:
                result.add(session.Process.pid)
        except Exception:
            continue
    return result


def _mac_window_titles():
    script = r'''
    tell application "System Events"
        set output to ""
        repeat with p in (processes whose visible is true)
            set pname to name of p
            if pname contains "Zoom" or pname contains "Telemost" or pname contains "Chrome" or pname contains "Safari" or pname contains "Yandex" then
                try
                    set pid to unix id of p
                    repeat with w in windows of p
                        set output to output & pid & "|" & (name of w) & linefeed
                    end repeat
                end try
            end if
        end repeat
    end tell
    return output
    '''
    try:
        proc = subprocess.run(["osascript", "-e", script], capture_output=True,
                              text=True, timeout=3)
        if proc.returncode != 0:
            logger.debug("macOS window titles: %s", proc.stderr.strip())
            return []
        result = []
        for line in proc.stdout.splitlines():
            if "|" not in line:
                continue
            pid, title = line.split("|", 1)
            try:
                result.append((int(pid), title))
            except ValueError:
                continue
        return result
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("Не удалось прочитать окна macOS: %s", exc)
        return []


def _window_titles():
    if os.name != "nt":
        if platform.system() == "Darwin":
            return _mac_window_titles()
        return []
    result = []
    try:
        user32 = ctypes.windll.user32
        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def visit(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            result.append((int(pid.value), buffer.value))
            return True

        user32.EnumWindows(enum_proc(visit), 0)
    except Exception as exc:
        logger.debug("Не удалось прочитать заголовки окон: %s", exc)
    return result


def detect_meeting(active_pids, windows, process_names):
    """Возвращает признаки встречи; функция изолирована для модульных тестов."""
    zoom_audio = any(
        pid in active_pids and _base(process_names.get(pid)) == "zoom"
        for pid in process_names
    )
    telemost_audio = any(
        pid in active_pids and "telemost" in _base(process_names.get(pid))
        for pid in process_names
    )
    zoom_window = False
    telemost_window = False
    for pid, title in windows:
        low = (title or "").casefold()
        process = _base(process_names.get(pid))
        if "zoom" in low and any(word in low for word in ("meeting", "собрание", "конференц")):
            zoom_window = True
        if "телемост" in low or "telemost" in low:
            if process in BROWSERS or "telemost" in process or not process:
                telemost_window = True
    audio = zoom_audio or telemost_audio
    present = audio or zoom_window or telemost_window
    label = "Zoom" if (zoom_audio or zoom_window) else "Яндекс Телемост"
    return {"audio_active": audio, "present": present, "label": label if present else ""}


class MeetingDetector:
    def __init__(self, start_delay=5, stop_delay=10):
        self.start_delay = start_delay
        self.stop_delay = stop_delay

    def poll(self):
        return detect_meeting(_active_audio_pids(), _window_titles(), _process_names())
