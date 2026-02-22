from dataclasses import dataclass


@dataclass(frozen=True)
class MouseConfig:
    # Input device
    device_path: str = "/dev/input/by-id/usb-Logitech_USB_Receiver-if02-event-mouse"

    # Absolute coordinate space (you define what these mean)
    min_x: int = 0
    max_x: int = 1920
    min_y: int = 0
    max_y: int = 1080

    # Initial absolute position
    start_x: int = 960
    start_y: int = 540

    # Startup averaging
    startup_samples: int = 10

    # Optional scale if you want to speed up / slow down integrated movement
    scale_x: float = 1.0
    scale_y: float = 1.0


@dataclass(frozen=True)
class AudioConfig:
    """
    ALSA audio output config using the `pyalsaaudio` library (import as `alsaaudio`).

    Install:
      sudo apt-get install -y python3-alsaaudio

    Notes:
    - `device` is an ALSA PCM device name. On most systems "default" works.
    - If you have multiple, you can set device to something you discover via alsaaudio.pcms().
    - Mixer name varies by card; common ones: "PCM", "Master", "Speaker", "Headphone".
    """

    # ALSA PCM playback device name. Usually "default" is correct.
    device: str = "default"

    # ALSA card index to use for Mixer (None => autodetect via available mixers)
    cardindex: int | None = None

    # If None => autodetect a reasonable mixer name (PCM/Master/Speaker/Headphone)
    mixer_name: str | None = None

    # Default volume if you want to set it during init/boot
    default_volume_percent: int = 70

    # Mixer preference order for autodetect
    prefer_mixers: tuple[str, ...] = ("PCM", "Master", "Speaker", "Headphone", "Digital", "Line", "Line Out")

    # If multiple devices exist and you decide to extend autodetect later, these can help
    preferred_device_keywords: tuple[str, ...] = ("usb",)


MOUSE_CONFIG = MouseConfig()
AUDIO_CONFIG = AudioConfig()