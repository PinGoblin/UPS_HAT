"""MicroPython example (e.g. Raspberry Pi Pico): poll the UPS HAT+ over I2C.

Wire the HAT's header I2C (pin 3 SDA, pin 5 SCL, pin 6 GND) to the board's I2C
pins. Copy the ups_hat folder (or the precompiled .mpy files) to the board first:
    mpremote cp -r ups_hat :
"""
import time
from machine import I2C, Pin
from ups_hat import UPS, CRITICAL

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
ups = UPS(i2c, cells_parallel=1, cell_capacity_mah=3000, pi_monitor=False)
led = Pin("LED", Pin.OUT)


def on_fault(f):
    print("FAULT", f)


ups.on_fault(on_fault)
ups.on_clear(lambda f: print("cleared", f.code))

while True:
    s = ups.poll()
    print("{:5.2f} V {:+5.2f} A  SoC {}  {}".format(
        s.vbat or 0, s.ibat or 0, "--" if s.soc is None else "%.0f%%" % s.soc,
        "battery" if s.on_battery else "mains"))
    led.value(1 if s.worst_severity() >= CRITICAL else 0)
    time.sleep(2)
