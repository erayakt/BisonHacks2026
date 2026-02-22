#!/usr/bin/env python3
import time

# IMPORTANT: adjust this import to your real path
# from src.camera.pwm_controller import PWMController
from output.pwm_controller import PWMController
from output.servo_controller import ServoController

def main():
    # Most setups after dtoverlay expose it as pwmchip0, channel 0
    pwm = PWMController(chip=0, channel=0)

    servo = ServoController(pwm, min_pulse_us=500, max_pulse_us=2500, max_angle=180)

    if not servo.initialize():
        raise RuntimeError("Servo init failed. Check dtoverlay + /sys/class/pwm permissions + chip/channel.")

    print("Servo initialized on GPIO12 via sysfs PWM.")

    try:
        for angle in [0, 90, 180, 90]:
            print("Angle:", angle)
            servo.set_angle(angle)
            time.sleep(1.0)

        print("Sweeping...")
        servo.sweep(step=10, delay=0.05)

    finally:
        servo.stop()
        pwm.cleanup()
        print("Clean exit.")

if __name__ == "__main__":
    main()