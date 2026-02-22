#!/usr/bin/env python3
"""
wav_loop_output.py

Plays a WAV file in an infinite loop on Raspberry Pi (headless) and lets you
update *intensity* (software gain) in real time.

Design goals:
- No spawning external players (aplay/amixer).
- Low-latency updates: set_level(0..100) updates gain quickly.
- Uses ALSA via `pyalsaaudio` (import as `alsaaudio`) like the rest of the project.

Intensity mapping:
- raw_level in [0..100]
- raw_norm = raw_level / 100
- effective = min_intensity + raw_norm * intensity_factor
- capped to [0..1]

So you can:
- keep a minimum audible level (min_intensity), and
- boost everything by a factor (intensity_factor), while capping safely.

API:
- player = LoopingWavOutput()
- player.start(wav_path="test.wav", min_intensity=0.05, intensity_factor=1.5)
- player.set_level(0..100)
- player.stop()

WAV requirements:
- PCM 16-bit WAV is recommended.
- Mono or stereo; stereo will be downmixed to mono.

"""

from __future__ import annotations

import threading
import time
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import AUDIO_CONFIG

try:
    import alsaaudio  # type: ignore
except Exception:  # pragma: no cover
    alsaaudio = None


def _clamp_int(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def _mix_to_mono_i16(frames: bytes, channels: int) -> array:
    """Convert interleaved i16 frames to mono i16 array."""
    a = array("h")
    a.frombytes(frames)
    if channels == 1:
        return a
    # Downmix: average channels
    mono = array("h")
    # len(a) = n_frames * channels
    for i in range(0, len(a), channels):
        s = 0
        for c in range(channels):
            s += a[i + c]
        mono.append(int(s / channels))
    return mono


@dataclass
class LoopingWavOutput:
    device: str = AUDIO_CONFIG.device
    sample_rate: int = 44100
    period_size: int = 1024  # frames per write

    _pcm: Optional["alsaaudio.PCM"] = None
    _thread: Optional[threading.Thread] = None
    _stop_evt: threading.Event = threading.Event()

    _samples: Optional[array] = None  # mono i16
    _pos: int = 0

    _gain_lock: threading.Lock = threading.Lock()
    _gain: float = 0.0  # 0..1 effective intensity (software gain)
    _min_intensity: float = 0.0
    _intensity_factor: float = 1.0

    def start(self, wav_path: str, *, min_intensity: float = 0.0, intensity_factor: float = 1.0) -> None:
        if alsaaudio is None:
            raise RuntimeError(
                "pyalsaaudio (alsaaudio) is not available. Install it (e.g., pip install pyalsaaudio) "
                "or switch to the sine tone backend."
            )

        p = Path(wav_path)
        if not p.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_path}")

        self._min_intensity = float(min_intensity)
        self._intensity_factor = float(intensity_factor)

        # Load wav into memory (mono i16)
        with wave.open(str(p), "rb") as wf:
            channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            rate = wf.getframerate()
            if sampwidth != 2:
                raise ValueError(f"Unsupported WAV sample width: {sampwidth*8} bits (need 16-bit PCM)")
            raw = wf.readframes(wf.getnframes())
            samples = _mix_to_mono_i16(raw, channels)

        self.sample_rate = int(rate)
        self._samples = samples
        self._pos = 0

        # ALSA PCM
        pcm = alsaaudio.PCM(type=alsaaudio.PCM_PLAYBACK, device=self.device)
        pcm.setchannels(1)
        pcm.setrate(self.sample_rate)
        pcm.setformat(alsaaudio.PCM_FORMAT_S16_LE)
        pcm.setperiodsize(self.period_size)

        self._pcm = pcm
        self._stop_evt = threading.Event()

        # start with silence until first set_level
        with self._gain_lock:
            self._gain = 0.0

        self._thread = threading.Thread(target=self._run, name="LoopingWavOutput", daemon=True)
        self._thread.start()

    def set_level(self, level_0_100: int) -> None:
        """Set intensity based on grid value (0..100)."""
        if level_0_100 < 0:
            level_0_100 = 0
        elif level_0_100 > 100:
            level_0_100 = 100

        raw_norm = level_0_100 / 100.0
        effective = self._min_intensity + raw_norm * self._intensity_factor
        if effective < 0.0:
            effective = 0.0
        elif effective > 1.0:
            effective = 1.0

        with self._gain_lock:
            self._gain = effective

    def stop(self) -> None:
        self._stop_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None
        self._pcm = None
        self._samples = None
        self._pos = 0

    def _run(self) -> None:
        assert self._pcm is not None
        assert self._samples is not None

        n = len(self._samples)
        if n == 0:
            return

        while not self._stop_evt.is_set():
            # Copy a chunk and apply gain
            start = self._pos
            end = start + self.period_size
            if end <= n:
                chunk = self._samples[start:end]
                self._pos = end if end < n else 0
            else:
                # wrap
                part1 = self._samples[start:n]
                part2 = self._samples[0 : (end - n)]
                chunk = array("h", part1)
                chunk.extend(part2)
                self._pos = end - n

            with self._gain_lock:
                g = self._gain

            if g <= 0.0001:
                # fast silence path
                out = b"\x00\x00" * len(chunk)
            elif g >= 0.9999:
                out = chunk.tobytes()
            else:
                scaled = array("h")
                scaled_extend = scaled.append
                for s in chunk:
                    scaled_extend(_clamp_int(int(s * g), -32768, 32767))
                out = scaled.tobytes()

            try:
                self._pcm.write(out)
            except Exception:
                # avoid tight loop on audio errors
                time.sleep(0.01)
