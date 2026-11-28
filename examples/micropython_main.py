"""MicroPython example (for example a Raspberry Pi Pico): poll the PinGoblin UPS HAT+.

Connect the HAT's header I²C pins to the board: pin 3 (SDA), pin 5 (SCL) and pin 6 (GND).
Copy the ups_hat folder (or the precompiled .mpy files) to the board first:
    mpremote cp -r ups_hat :

To run without hardware on a PC, from a copy of the repository:
    micropython examples/micropython_main.py --mock
"""
import sys
import time

from ups_hat import UPS, UPSError, CRITICAL

MOCK = "--mock" in getattr(sys, "argv", [])

if MOCK:
    from mock_board import mock_i2c
    i2c = mock_i2c()
    led = None
    polls = 3
else:
    from machine import I2C, Pin
    i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
    led = Pin("LED", Pin.OUT)
    polls = None                      # forever

try:
    ups = UPS(i2c, cells_parallel=1, cell_capacity_mah=3000, pi_monitor=False)
except UPSError as e:
    print("UPS HAT+ error:", e)
    sys.exit(1)

ups.on_fault(lambda f: print("FAULT", f))
ups.on_clear(lambda f: print("cleared", f.code))

n = 0
while polls is None or n < polls:
    s = ups.poll()
    if not s.charger_ok:
        print("UPS HAT+ not answering: check the I2C wiring (SDA, SCL, GND) and pins.")
    print("{:5.2f} V {:+5.2f} A  SoC {}  {}".format(
        s.vbat or 0, s.ibat or 0, "--" if s.soc is None else "%.0f%%" % s.soc,
        "battery" if s.on_battery else "mains"))
    if led is not None:
        led.value(1 if s.worst_severity() >= CRITICAL else 0)
    n += 1
    time.sleep(0 if MOCK else 2)
