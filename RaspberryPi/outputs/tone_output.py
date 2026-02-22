#!/usr/bin/env python3
"""
tone_output.py

Continuous sine-wave tone output (headless) via ALSA using `pyalsaaudio` (import as `alsaaudio`).

Why:
- For rapid feedback (e.g., mouse moving across a 6x6 grid), starting/stopping WAV playback
  is too heavy. This module keeps a background audio thread running and lets you update
  the "level" (0..100) in real time.

API:
- tone = ToneOutput()
- tone.start(freq_hz=440)
- tone.set_level(0..100)   # updates loudness immediately
- tone.stop()

Notes:
- Uses 16-bit signed PCM at 44.1kHz, mono by default.
- If ALSA mixer volume is also available, you can combine with outputs/audio_output.py
  to set hardware volume, but this module controls amplitude in software.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from typing import Optional

from config import AUDIO_CONFIG

try:
    import alsaaudio  # type: ignore
except Exception as e:  # pragma: no cover
    alsaaudio = None  # type: ignore
    _ALSAAUDIO_IMPORT_ERROR = e
else:
    _ALSAAUDIO_IMPORT_ERROR = None


class ToneOutputError(RuntimeError):
    pass


def _require_alsaaudio() -> None:
    if alsaaudio is None:
        raise ToneOutputError(
            "pyalsaaudio (alsaaudio) is not available.\n"
            "Install with: sudo apt-get install -y python3-alsaaudio\n"
            f"Import error: {_ALSAAUDIO_IMPORT_ERROR}"
        )


@dataclass(frozen=True)
class ToneConfig:
    device: str = AUDIO_CONFIG.device
    sample_rate: int = 44100
    channels: int = 1
    period_size: int = 1024  # frames per write
    # Software amplitude ceiling (0..1). Keep below 1 to avoid clipping.
    max_amp: float = 0.6


class ToneOutput:
    """
    Background sine-wave generator with real-time loudness updates.
    """

    def __init__(self, cfg: ToneConfig = ToneConfig()):
        _require_alsaaudio()
        self.cfg = cfg

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._level: int = 0  # 0..100
        self._freq_hz: float = 440.0
        self._phase: float = 0.0

        self._pcm = None

    def start(self, *, freq_hz: float = 440.0, level: int = 0) -> None:
        """
        Start (or restart) the continuous tone thread.
        """
        with self._lock:
            self._freq_hz = float(freq_hz)
            self._level = int(max(0, min(100, level)))

            if self._thread and self._thread.is_alive():
                return

            self._stop.clear()
            self._thread = threading.Thread(
                target=self._worker,
                name="ToneOutput",
                daemon=True,
            )
            self._thread.start()

    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def set_level(self, level: int) -> None:
        """
        Update loudness in range 0..100. 0 = silence.
        """
        with self._lock:
            self._level = int(max(0, min(100, level)))

    def set_frequency(self, freq_hz: float) -> None:
        with self._lock:
            self._freq_hz = float(freq_hz)

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            t = self._thread
        if t:
            t.join(timeout=2.0)
        with self._lock:
            self._thread = None
            self._stop.clear()

    # ------------------------

    def _worker(self) -> None:
        pcm = None
        try:
            pcm = alsaaudio.PCM(  # type: ignore
                type=alsaaudio.PCM_PLAYBACK,  # type: ignore
                mode=alsaaudio.PCM_NORMAL,  # type: ignore
                device=self.cfg.device,
            )
            pcm.setchannels(self.cfg.channels)
            pcm.setrate(self.cfg.sample_rate)
            pcm.setformat(alsaaudio.PCM_FORMAT_S16_LE)  # type: ignore
            pcm.setperiodsize(self.cfg.period_size)

            # Precompute time step
            sr = float(self.cfg.sample_rate)
            two_pi = 2.0 * math.pi

            # 16-bit signed range
            i16_max = 32767

            while not self._stop.is_set():
                with self._lock:
                    level = self._level
                    freq = self._freq_hz

                # Scale level -> amplitude
                amp = (level / 100.0) * self.cfg.max_amp
                # Convert to int16 amplitude
                a = int(i16_max * amp)

                # Generate one period_size block
                buf = bytearray()
                # phase increment per sample
                dphi = two_pi * freq / sr
                phi = self._phase

                for _ in range(self.cfg.period_size):
                    # sine in [-1,1]
                    s = int(a * math.sin(phi))
                    # pack little-endian int16
                    buf += (s).to_bytes(2, byteorder="little", signed=True)
                    phi += dphi
                    if phi >= two_pi:
                        phi -= two_pi

                self._phase = phi

                # Write to ALSA
                pcm.write(bytes(buf))

                # Small sleep is usually unnecessary; PCM write blocks as needed.
                # But if ALSA is very permissive, keep CPU usage sane:
                time.sleep(0.0)

        except Exception as e:
            raise ToneOutputError(f"ToneOutput failed: {e}") from e
        finally:
            try:
                if pcm is not None:
                    pcm.close()
            except Exception:
                pass


if __name__ == "__main__":
    t = ToneOutput()
    t.start(freq_hz=440, level=0)
    print("Ramping 0..100 then back. Ctrl+C to stop.")
    try:
        for v in list(range(0, 101, 5)) + list(range(100, -1, -5)):
            t.set_level(v)
            time.sleep(0.08)
    except KeyboardInterrupt:
        pass
    finally:
        t.stop()
