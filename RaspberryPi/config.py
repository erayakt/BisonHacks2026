from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MouseConfig:
    # Input device
    device_path: str = "/dev/input/by-id/usb-Logitech_USB_Receiver-if02-event-mouse"

    # Absolute coordinate space (your virtual screen / canvas)
    min_x: int = 0
    max_x: int = 1600
    min_y: int = 0
    max_y: int = 1101

    # Initial absolute position
    start_x: int = max_x // 2
    start_y: int = max_y // 2

    # Startup averaging
    startup_samples: int = 10

    # Optional scale if you want to speed up / slow down integrated movement
    scale_x: float = 1.0
    scale_y: float = 1.0

    # Mouse is physically rotated 180° => reverse both axes
    rotate_180: bool = True


@dataclass(frozen=True)
class WebSocketConfig:
    """
    Raspberry Pi -> Computer websocket connection.
    """
    # Default laptop IP from your message, but configurable.
    server_ip: str = "192.168.137.1"
    server_port: int = 8765

    # If you want to bind it to wss later, just change scheme to "wss"
    scheme: str = "ws"

    reconnect_delay_s: float = 1.0

    @property
    def server_uri(self) -> str:
        return f"{self.scheme}://{self.server_ip}:{self.server_port}"


@dataclass(frozen=True)
class AudioConfig:
    """
    ALSA audio output config using the `pyalsaaudio` library (import as `alsaaudio`).
    """
    device: str = "default"
    cardindex: int | None = None
    mixer_name: str | None = None
    default_volume_percent: int = 70
    prefer_mixers: tuple[str, ...] = ("PCM", "Master", "Speaker", "Headphone", "Digital", "Line", "Line Out")
    preferred_device_keywords: tuple[str, ...] = ("usb",)


MOUSE_CONFIG = MouseConfig()
WS_CONFIG = WebSocketConfig()
AUDIO_CONFIG = AudioConfig()
