#!/usr/bin/env python3
import time

# IMPORTANT: adjust this import to your real path
# from src.camera.pwm_controller import PWMController
from output.pwm_controller import PWMController
from output.servo_controller import ServoController
from output.tactile_output import TactileOutput
from output.tactile_output import TactileServoConfig

# Demo usage
t = TactileOutput(
    TactileServoConfig(
        chip=0,
        channel=0,
        not_touching_angle=50,
        touching_angle=130,
        max_touching_angle=180,
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