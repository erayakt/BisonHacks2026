import time
from output.pwm_controller import PWMController


class ServoController:
    def __init__(self, pwm_controller, min_pulse_us=500, max_pulse_us=2500, max_angle=180):
        self.pwm = pwm_controller
        self.min_pulse_us = min_pulse_us
        self.max_pulse_us = max_pulse_us
        self.max_angle = max_angle
        self.current_angle = None
        
    def initialize(self):
        # Set 50Hz frequency (20ms period)
        if not self.pwm.set_period(20_000_000):
            return False
        
        # Start at center
        center_angle = self.max_angle // 2
        self.set_angle(center_angle)
        
        return self.pwm.enable()
    
    def set_angle(self, angle):
        if angle < 0 or angle > self.max_angle:
            return False
        
        # Convert angle to pulse width
        pulse_us = self.min_pulse_us + (angle * (self.max_pulse_us - self.min_pulse_us)) // self.max_angle
        pulse_ns = pulse_us * 1000
        
        if self.pwm.set_duty_cycle(pulse_ns):
            self.current_angle = angle
            return True
        return False
    
    def set_pulse_width(self, pulse_us):
        if pulse_us < self.min_pulse_us or pulse_us > self.max_pulse_us:
            return False
        
        pulse_ns = pulse_us * 1000
        return self.pwm.set_duty_cycle(pulse_ns)
    
    def sweep(self, start_angle=0, end_angle=None, step=5, delay=0.1):
        if end_angle is None:
            end_angle = self.max_angle
        
        # Forward sweep
        for angle in range(start_angle, end_angle + 1, step):
            self.set_angle(angle)
            time.sleep(delay)
        
        # Backward sweep
        for angle in range(end_angle, start_angle - 1, -step):
            self.set_angle(angle)
            time.sleep(delay)
    
    def center(self):
        return self.set_angle(self.max_angle // 2)
    
    def stop(self):
        self.center()
        time.sleep(0.5)
        self.pwm.disable()


if __name__ == "__main__":
    pwm = PWMController()
    servo = ServoController(pwm, min_pulse_us=500, max_pulse_us=2500)
    
    servo.initialize()
    print("Servo initialized")
    
    try:
        while True:
            print("Sweeping...")
            servo.sweep()
            time.sleep(1)
    except KeyboardInterrupt:
        servo.stop()
        pwm.cleanup()
        print("Stopped")