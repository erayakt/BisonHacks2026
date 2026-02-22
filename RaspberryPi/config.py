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

    # Startup averaging:
    # If > 0, we’ll “average” by setting position to the mean of (start_x,start_y) repeated N times,
    # which effectively just gives a stable start point and avoids any early jitter logic.
    # (Kept intentionally simple; you can set to 0 to skip.)
    startup_samples: int = 10

    # Optional scale if you want to speed up / slow down integrated movement
    scale_x: float = 1.0
    scale_y: float = 1.0


# Single shared instance for other modules to import
MOUSE_CONFIG = MouseConfig()