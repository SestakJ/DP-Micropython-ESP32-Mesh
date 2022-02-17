import time
from machine import Pin
for i in range(25, 40):
    try:
        p = Pin(i, Pin.OUT)
        print("PIN : " + str(i))
        # p.value(not(p.value()))
        # time.sleep(1)
        print(p.value())
        # p.value(not(p.value))
        # print("PIN End")
    except:
        # print("No pin")
        pass


import time
from machine import Pin
p25 = Pin(25, Pin.OUT)
p25.value()

from machine import Pin, PWM
try:
    f = 100  # Hz
    d = 1024 // 16  # 6.25%
    pins = (15, 2, 4, 18, 19, 22, 23, 25, 27, 14 , 12, 13, 32, 33)
    pwms = []
    for i, pin in enumerate(pins):
        pwms.append(PWM(Pin(pin), freq=f * (i // 2 + 1), duty= 1023 if i==15 else d * (i + 1)))
        print(pwms[i])
finally:
    for pwm in pwms:
        try:
            pwm.deinit()
        except:
            pass

