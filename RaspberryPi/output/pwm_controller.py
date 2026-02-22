import os
import time

class PWMController:
    def __init__(self, chip=0, channel=0):
        self.chip = chip
        self.channel = channel
        self.pwm_path = f'/sys/class/pwm/pwmchip{chip}/pwm{channel}'
        self.chip_path = f'/sys/class/pwm/pwmchip{chip}'
        self.exported = False
        
    def export(self):
        if os.path.exists(self.pwm_path):
            self.exported = True
            return True
            
        try:
            with open(f'{self.chip_path}/export', 'w') as f:
                f.write(str(self.channel))
            time.sleep(0.1)
            self.exported = True
            return True
        except:
            return False
    
    def set_period(self, period_ns):
        if not self.exported:
            if not self.export():
                return False
        try:
            with open(f'{self.pwm_path}/period', 'w') as f:
                f.write(str(period_ns))
            return True
        except:
            return False
    
    def set_duty_cycle(self, duty_ns):
        try:
            with open(f'{self.pwm_path}/duty_cycle', 'w') as f:
                f.write(str(duty_ns))
            return True
        except:
            return False
    
    def enable(self):
        try:
            with open(f'{self.pwm_path}/enable', 'w') as f:
                f.write('1')
            return True
        except:
            return False
    
    def disable(self):
        try:
            with open(f'{self.pwm_path}/enable', 'w') as f:
                f.write('0')
            return True
        except:
            return False
    
    def cleanup(self):
        self.disable()
        if self.exported:
            try:
                with open(f'{self.chip_path}/unexport', 'w') as f:
                    f.write(str(self.channel))
            except:
                pass


if __name__ == "__main__":
    pwm = PWMController()
    pwm.set_period(20_000_000)  # 20ms
    pwm.enable()
    
    # Test different duty cycles
    for duty in [1_000_000, 1_500_000, 2_000_000]:
        pwm.set_duty_cycle(duty)
        print(f"Duty: {duty//1000}μs")
        time.sleep(1)
    
    pwm.cleanup()