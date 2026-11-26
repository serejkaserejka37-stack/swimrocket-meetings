"""macOS: микрофон и виртуальный системный канал (BlackHole) через sounddevice."""
import logging
import shutil
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from app.recording.audio_capture import AudioStream
from app.recording.chunk_writer import ChunkWriter

logger = logging.getLogger(__name__)


class MacLoopbackStream:
    """Тот же интерфейс, что LoopbackStream в Windows, но для BlackHole."""
    def __init__(self, device_name=None, sample_rate=16000, level_callback=None, sink=None):
        self.device_name = device_name
        self.sample_rate = sample_rate
        self.level_callback = level_callback
        self.sink = sink
        self._stream = None

    def start(self, device_index=None):
        device = device_index if device_index is not None else self.device_name
        if device is None:
            raise RuntimeError("Выберите BlackHole или другое виртуальное аудиоустройство")
        self._stream = sd.InputStream(
            device=device, samplerate=self.sample_rate, channels=1,
            dtype="float32", callback=self._callback,
        )
        self._stream.start()

    def _callback(self, indata, frames, time_info, status):
        chunk = indata.copy()
        if self.sink is not None:
            self.sink.put(chunk)
        if self.level_callback is not None:
            self.level_callback(chunk)

    def stop(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def set_gain(self, gain):
        return


class MacDualAudioCapture:
    def __init__(self, mic_device=None, loopback_device=None, sample_rate=16000,
                 capture_mode="legacy", app_pids=None, mic_device_2=None):
        self.mic_device = mic_device
        self.loopback_device = loopback_device
        self.sample_rate = sample_rate
        self.mic_device_2 = mic_device_2
        self._mic = None
        self._system = None
        self._writers = {}
        self._mic_callback = None
        self._system_callback = None
        self._started_at = None
        self._paused = False
        self._silence_duration = None
        self._silence_callback = None
        self._last_sound = None
        self._capture_status = None

    def set_level_callbacks(self, mic_callback=None, system_callback=None):
        self._mic_callback = mic_callback
        self._system_callback = system_callback

    def set_silence_detection(self, threshold, duration, callback):
        self._silence_threshold = threshold
        self._silence_duration = duration
        self._silence_callback = callback

    def set_capture_event_callbacks(self, **kwargs):
        return

    def set_gain(self, gain):
        if self._mic is not None:
            self._mic.set_gain(gain)

    def set_mic_muted(self, muted):
        if self._mic is not None:
            self._mic.set_muted(muted)

    def _system_level(self, chunk):
        if self._silence_duration:
            level = float(np.max(np.abs(chunk))) if chunk.size else 0.0
            if level >= self._silence_threshold:
                self._last_sound = time.monotonic()
            elif self._last_sound and time.monotonic() - self._last_sound >= self._silence_duration:
                if self._silence_callback:
                    self._silence_callback(time.monotonic() - self._last_sound)
                self._last_sound = time.monotonic()
        if self._system_callback:
            self._system_callback(chunk)

    def start(self, session_dir):
        session_dir = Path(session_dir)
        self._started_at = time.monotonic()
        self._last_sound = self._started_at
        self._writers = {}
        if self.mic_device is not None:
            self._writers["mic"] = ChunkWriter(session_dir / "mic.wav", self.sample_rate)
            self._mic = AudioStream(
                self.mic_device, self.sample_rate, channels=1,
                level_callback=self._mic_callback, sink=self._writers["mic"],
            )
        if self.loopback_device is not None:
            self._writers["system"] = ChunkWriter(session_dir / "system.wav", self.sample_rate)
            self._system = AudioStream(
                self.loopback_device, self.sample_rate, channels=1,
                level_callback=self._system_level, sink=self._writers["system"],
            )
        if not self._writers:
            raise RuntimeError("Выберите микрофон и/или BlackHole для записи")
        try:
            if self._system:
                self._system.start()
            if self._mic:
                self._mic.start()
            for writer in self._writers.values():
                writer.release()
        except Exception:
            self.stop()
            raise

    def pause(self):
        self._paused = True
        for stream in (self._mic, self._system):
            if stream:
                stream.pause()

    def resume(self):
        self._paused = False
        for stream in (self._mic, self._system):
            if stream:
                stream.resume()

    def get_elapsed_time(self):
        return max(0.0, time.monotonic() - self._started_at) if self._started_at else 0.0

    def stop(self):
        for stream in (self._mic, self._system):
            if stream:
                stream.stop()
        self._mic = self._system = None
        for writer in self._writers.values():
            writer.stop()
        files = {role: str(writer.path) for role, writer in self._writers.items()
                 if writer.path.exists()}
        self._writers = {}
        if not files:
            return files
        combined = str(next(iter(files.values())).replace("mic.wav", "combined.wav")
                       if "mic" in files else next(iter(files.values())).replace("system.wav", "combined.wav"))
        if "mic" in files and "system" in files:
            mic, rate = sf.read(files["mic"], dtype="float32")
            system, _ = sf.read(files["system"], dtype="float32")
            length = max(len(mic), len(system))
            mic = np.pad(mic, (0, length - len(mic)))
            system = np.pad(system, (0, length - len(system)))
            mixed = np.clip(mic + system, -1.0, 1.0)
            sf.write(combined, mixed, rate, subtype="PCM_16")
        else:
            shutil.copyfile(next(iter(files.values())), combined)
        files["combined"] = combined
        return files
