#!/usr/bin/env python3
"""
tactile_output.py
High-level tactile output layer using a servo (SG90) driven by sysfs PWM via PWMController + ServoController.

Behavior:
- touch(0)        -> not touching angle (e.g., 50)
- touch(0..1]     -> maps to touching angle range (e.g., 150..190)
"""

from dataclasses import dataclass
import time

from output.pwm_controller import PWMController
from output.servo_controller import ServoController


@dataclass(frozen=True)
class TactileServoConfig:
    # Hardware PWM sysfs selection
    chip: int = 0
    channel: int = 0

    # Servo pulse defaults (SG90-ish; adjust if needed)
    min_pulse_us: int = 500
    max_pulse_us: int = 2500
    max_angle: int = 180  # ServoController uses this for mapping; angles below are what we command.

    # Logical angles for your tactile behavior
    not_touching_angle: int = 50
    touching_angle: int = 150
    max_touching_angle: int = 190  # may exceed max_angle; we will clamp to servo max_angle if needed

    # Optional: small settle delay after changes
    settle_s: float = 0.02


class TactileOutput:
    """
    High-level tactile control:
      - initialize()
      - touch(strength 0..1)
      - release()
      - cleanup()
    """

    def __init__(self, config: TactileServoConfig = TactileServoConfig()):
        self.cfg = config
        self.pwm = PWMController(chip=self.cfg.chip, channel=self.cfg.channel)
        self.servo = ServoController(
            self.pwm,
            min_pulse_us=self.cfg.min_pulse_us,
            max_pulse_us=self.cfg.max_pulse_us,
            max_angle=self.cfg.max_angle,
        )
        self._initialized = False
        self._last_angle = None

    def initialize(self) -> None:
        """Set up PWM, enable, and move to not-touching position."""
        if not self.servo.initialize():
            raise RuntimeError(
                "TactileOutput init failed. Check dtoverlay, /sys/class/pwm, permissions, chip/channel."
            )
        self._initialized = True
        self.release()

    def _clamp(self, v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def _set_angle(self, angle: int) -> None:
        """Set angle with clamping + avoid redundant writes."""
        if not self._initialized:
            raise RuntimeError("TactileOutput not initialized. Call initialize() first.")

        # Clamp to servo's configured max_angle range
        angle = int(round(angle))
        angle = max(0, min(self.cfg.max_angle, angle))

        if self._last_angle == angle:
            return

        ok = self.servo.set_angle(angle)
        if not ok:
            raise RuntimeError(f"Failed to set servo angle to {angle}")

        self._last_angle = angle
        if self.cfg.settle_s > 0:
            time.sleep(self.cfg.settle_s)

    def release(self) -> None:
        """Go to 'not touching' position."""
        self._set_angle(self.cfg.not_touching_angle)

    def touch(self, strength: float) -> None:
        """
        strength: 0..1
          - 0 -> not touching (50)
          - (0..1] -> maps to [touching_angle .. max_touching_angle] (150..190)
        """
        s = float(strength)
        s = self._clamp(s, 0.0, 1.0)

        if s <= 0.0:
            self.release()
            return

        start = self.cfg.touching_angle
        end = self.cfg.max_touching_angle

        # linear interpolation from start->end
        angle = start + (end - start) * s
        self._set_angle(int(round(angle)))

    def stop(self) -> None:
        """Safely stop: center then disable PWM (uses ServoController.stop)."""
        if not self._initialized:
            return
        self.servo.stop()

    def cleanup(self) -> None:
        """Disable PWM and unexport sysfs PWM channel."""
        try:
            self.stop()
        finally:
            self.pwm.cleanup()
            self._initialized = False


if __name__ == "__main__":
    # Demo usage
    t = TactileOutput(
        TactileServoConfig(
            chip=0,
            channel=0,
            not_touching_angle=50,
            touching_angle=150,
            max_touching_angle=190,
        )
    )

    try:
        t.initialize()
        print("Initialized. release() -> touch(0.2) -> touch(1.0) -> release()")

        t.release()
        time.sleep(1)

        t.touch(0.2)
        time.sleep(2)

        t.touch(1.0)
        time.sleep(2)

        t.release()
        time.sleep(1)

    finally:
        t.cleanup()
        print("Clean exit.")