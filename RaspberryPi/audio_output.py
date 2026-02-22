"""
audio_output.py

Pure-Python ALSA playback + volume control via `pyalsaaudio` (alsaaudio).
- Plays .wav (PCM) directly.
- Sets hardware mixer volume.
- Tracks whether audio is currently playing.
- If play_wav() is called while already playing:
    - returns False (default)
    - or if force=True, stops current playback and starts new one.

Install on Raspberry Pi / DietPi:
  sudo apt-get install -y python3-alsaaudio
"""

from __future__ import annotations

import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from config import AUDIO_CONFIG

try:
    import alsaaudio  # type: ignore
except Exception as e:  # pragma: no cover
    alsaaudio = None  # type: ignore
    _ALSAAUDIO_IMPORT_ERROR = e
else:
    _ALSAAUDIO_IMPORT_ERROR = None


class AudioOutputError(RuntimeError):
    pass


def _require_alsaaudio() -> None:
    if alsaaudio is None:
        raise AudioOutputError(
            "pyalsaaudio (alsaaudio) is not available.\n"
            "Install with: sudo apt-get install -y python3-alsaaudio\n"
            f"Import error: {_ALSAAUDIO_IMPORT_ERROR}"
        )


@dataclass(frozen=True)
class PlaybackInfo:
    path: str
    started_at: float


class AudioOutput:
    """
    Threaded WAV player with stop/force logic.
    """

    def __init__(self):
        _require_alsaaudio()

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._playing: bool = False
        self._current: Optional[PlaybackInfo] = None

        self.device = AUDIO_CONFIG.device
        self._mixer = self._init_mixer(
            mixer_name=AUDIO_CONFIG.mixer_name,
            cardindex=AUDIO_CONFIG.cardindex,
            prefer=AUDIO_CONFIG.prefer_mixers,
        )

    # ---------------------------
    # Public API
    # ---------------------------

    def is_playing(self) -> bool:
        with self._lock:
            # if thread died unexpectedly, reconcile
            if self._playing and self._thread and not self._thread.is_alive():
                self._playing = False
                self._current = None
            return self._playing

    def current(self) -> Optional[PlaybackInfo]:
        with self._lock:
            return self._current

    def stop(self) -> bool:
        """
        Stops playback if currently playing.
        Returns True if something was playing, else False.
        """
        with self._lock:
            if not self._playing:
                return False
            self._stop_event.set()
            t = self._thread

        # Join outside lock to avoid deadlocks
        if t:
            t.join(timeout=2.0)

        with self._lock:
            self._playing = False
            self._current = None
            self._thread = None
            self._stop_event.clear()
        return True

    def set_volume(self, percent: int) -> None:
        """
        Sets ALSA mixer volume (0..100).
        """
        if percent < 0 or percent > 100:
            raise ValueError("percent must be between 0 and 100")
        if self._mixer is None:
            raise AudioOutputError(
                "No ALSA mixer available to set volume. "
                "Set AUDIO_CONFIG.mixer_name / cardindex or check ALSA mixer controls."
            )

        # Many ALSA mixers are stereo; setvolume handles both if given one value
        self._mixer.setvolume(int(percent))

    def play_wav(self, wav_path: str | Path, *, force: bool = False, blocking: bool = False) -> bool:
        """
        Start playing a WAV.

        Returns:
          True  => started playing
          False => rejected because something is already playing (and force=False)

        If blocking=True, this call blocks until playback finishes or is stopped.
        """
        p = Path(wav_path)
        if not p.exists():
            raise FileNotFoundError(str(p))
        if p.suffix.lower() != ".wav":
            raise ValueError("Only .wav files are supported.")

        with self._lock:
            if self._playing:
                if not force:
                    return False
                # force: stop current then continue
                # We do stop() outside lock to avoid join deadlock
            else:
                # not playing; proceed
                pass

        if force:
            self.stop()

        # Start new playback thread
        with self._lock:
            if self._playing:
                # extremely unlikely race, but safe
                if not force:
                    return False
                self.stop()

            self._stop_event.clear()
            self._playing = True
            self._current = PlaybackInfo(path=str(p), started_at=time.time())

            t = threading.Thread(
                target=self._playback_worker,
                args=(str(p),),
                daemon=True,
                name="AudioOutputPlayback",
            )
            self._thread = t
            t.start()

        if blocking:
            t.join()
        return True

    # ---------------------------
    # Mixer init (hardware volume)
    # ---------------------------

    def _init_mixer(self, mixer_name: Optional[str], cardindex: Optional[int], prefer: tuple[str, ...]):
        """
        Try to create an alsaaudio.Mixer for volume control.
        If it fails, we return None (playback still works).
        """
        _require_alsaaudio()

        # Helper: try create mixer with specific name/card
        def try_mixer(name: str, idx: Optional[int]):
            try:
                if idx is None:
                    return alsaaudio.Mixer(name)  # type: ignore
                return alsaaudio.Mixer(name, cardindex=idx)  # type: ignore
            except Exception:
                return None

        # If explicit mixer_name provided, try it first
        if mixer_name:
            m = try_mixer(mixer_name, cardindex)
            if m is not None:
                return m
            # If explicit name fails, still try autodetect below

        # Autodetect mixer: we need to look at available mixers.
        # `alsaaudio.mixers(cardindex=...)` exists; if cardindex None, try several cards.
        card_indices_to_try = []
        if cardindex is not None:
            card_indices_to_try = [cardindex]
        else:
            # Best-effort: try cards 0..7 (small + fast)
            card_indices_to_try = list(range(0, 8))

        for idx in card_indices_to_try:
            try:
                names = alsaaudio.mixers(cardindex=idx)  # type: ignore
            except Exception:
                continue

            # Prefer common names
            for wanted in prefer:
                for name in names:
                    if name.lower() == wanted.lower():
                        m = try_mixer(name, idx)
                        if m is not None:
                            return m

            # Fallback: any mixer
            for name in names:
                m = try_mixer(name, idx)
                if m is not None:
                    return m

        return None

    # ---------------------------
    # Playback worker
    # ---------------------------

    def _playback_worker(self, wav_path: str) -> None:
        """
        Stream WAV frames to ALSA PCM until done or stop_event is set.
        """
        pcm = None
        try:
            with wave.open(wav_path, "rb") as wf:
                channels = wf.getnchannels()
                rate = wf.getframerate()
                sampwidth = wf.getsampwidth()

                fmt = self._alsa_format_from_sampwidth(sampwidth)

                # Use plug device for safety (rate/format conversions)
                # Many systems accept "default". If you use hw:* you may need exact format/rate.
                pcm = alsaaudio.PCM(  # type: ignore
                    type=alsaaudio.PCM_PLAYBACK,  # type: ignore
                    mode=alsaaudio.PCM_NORMAL,  # type: ignore
                    device=self.device,
                )
                pcm.setchannels(channels)
                pcm.setrate(rate)
                pcm.setformat(fmt)
                pcm.setperiodsize(1024)

                # Stream in chunks
                while not self._stop_event.is_set():
                    data = wf.readframes(1024)
                    if not data:
                        break
                    # write() may accept partial; but for PCM_NORMAL it generally blocks appropriately
                    pcm.write(data)

        except Exception as e:
            # If playback fails, mark not playing
            with self._lock:
                self._playing = False
                self._current = None
                self._thread = None
                self._stop_event.clear()
            # Re-raise as AudioOutputError for visibility in logs
            raise AudioOutputError(f"Playback failed for {wav_path}: {e}") from e
        finally:
            # Close PCM device
            try:
                if pcm is not None:
                    pcm.close()
            except Exception:
                pass

            # Mark complete if we ended naturally (or stop was requested)
            with self._lock:
                self._playing = False
                self._current = None
                self._thread = None
                self._stop_event.clear()

    @staticmethod
    def _alsa_format_from_sampwidth(sampwidth: int):
        """
        Map WAV sample width to ALSA format.
        """
        _require_alsaaudio()

        if sampwidth == 1:
            return alsaaudio.PCM_FORMAT_U8  # type: ignore
        if sampwidth == 2:
            return alsaaudio.PCM_FORMAT_S16_LE  # type: ignore
        if sampwidth == 3:
            # 24-bit packed little-endian is the common WAV form
            # pyalsaaudio supports S24_3LE on many builds
            if hasattr(alsaaudio, "PCM_FORMAT_S24_3LE"):
                return alsaaudio.PCM_FORMAT_S24_3LE  # type: ignore
            # fallback if not available
            raise AudioOutputError("24-bit WAV not supported by this alsaaudio build (missing PCM_FORMAT_S24_3LE).")
        if sampwidth == 4:
            return alsaaudio.PCM_FORMAT_S32_LE  # type: ignore

        raise AudioOutputError(f"Unsupported WAV sample width: {sampwidth} bytes")


if __name__ == "__main__":
    # Minimal test:
    #   python3 audio_output.py /path/to/test.wav 70
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 audio_output.py <file.wav> [volume_percent]")
        raise SystemExit(2)

    wav = sys.argv[1]
    vol = int(sys.argv[2]) if len(sys.argv) >= 3 else None

    ao = AudioOutput()
    if vol is None:
        ao.set_volume(AUDIO_CONFIG.default_volume_percent)
        print(f"Volume set to {AUDIO_CONFIG.default_volume_percent}% (default)")
    else:
        ao.set_volume(vol)
        print(f"Volume set to {vol}%")

    started = ao.play_wav(wav, force=True, blocking=True)
    print("Started:", started, "| Done. is_playing:", ao.is_playing())