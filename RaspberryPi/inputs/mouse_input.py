import threading
import time
from typing import Tuple, Optional

from evdev import InputDevice, ecodes

from config import MOUSE_CONFIG


class MouseInput:
    """
    Reads relative mouse events from an evdev device and integrates them into
    an absolute (x,y) position with clamping.
    """

    def __init__(self, config=MOUSE_CONFIG):
        self.cfg = config

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Absolute position (integrated)
        self._x = int(self.cfg.start_x)
        self._y = int(self.cfg.start_y)

        # "Moved since last check" flag
        self._moved = False

        # Internal device handle
        self._dev: Optional[InputDevice] = None

        # Simple startup stabilization (kept intentionally minimal)
        self._apply_startup_average()

    def _apply_startup_average(self) -> None:
        n = int(self.cfg.startup_samples)
        if n <= 0:
            return
        # Average of same value is the same value; this is a minimal “stabilize start” step.
        # (Avoids adding extra calibration complexity.)
        with self._lock:
            self._x = int(round(sum([self.cfg.start_x] * n) / n))
            self._y = int(round(sum([self.cfg.start_y] * n) / n))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def _open_device(self) -> InputDevice:
        dev = InputDevice(self.cfg.device_path)
        return dev

    def _clamp(self, x: int, y: int) -> Tuple[int, int]:
        x = max(self.cfg.min_x, min(self.cfg.max_x, x))
        y = max(self.cfg.min_y, min(self.cfg.max_y, y))
        return x, y

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self._dev is None:
                    self._dev = self._open_device()

                # Blocking event loop
                for event in self._dev.read_loop():
                    if self._stop_event.is_set():
                        break

                    if event.type != ecodes.EV_REL:
                        continue

                    dx = 0
                    dy = 0

                    if event.code == ecodes.REL_X:
                        dx = event.value
                    elif event.code == ecodes.REL_Y:
                        dy = event.value
                    else:
                        continue

                    if dx == 0 and dy == 0:
                        continue

                    # Integrate into absolute coords
                    with self._lock:
                        new_x = self._x + int(round(dx * self.cfg.scale_x))
                        new_y = self._y + int(round(dy * self.cfg.scale_y))
                        self._x, self._y = self._clamp(new_x, new_y)
                        self._moved = True

            except FileNotFoundError:
                # Device path not ready yet
                self._dev = None
                time.sleep(0.25)
            except PermissionError:
                # Usually means you need sudo or input group permissions
                self._dev = None
                time.sleep(1.0)
            except OSError:
                # Device unplugged or read error
                self._dev = None
                time.sleep(0.25)

    def get_absolute_position(self) -> Tuple[int, int]:
        with self._lock:
            return self._x, self._y

    def is_moved(self) -> bool:
        """
        Returns True if the mouse has moved since last call.
        If True, it resets the internal moved flag back to False.
        """
        with self._lock:
            moved = self._moved
            self._moved = False
            return moved

    def set_absolute_position(self, x: int, y: int) -> None:
        """
        Manually set absolute position (clamped).
        """
        with self._lock:
            self._x, self._y = self._clamp(int(x), int(y))
            self._moved = True