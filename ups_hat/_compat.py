# Small portability layer so the same code runs on MicroPython and CPython.

import sys
import time

MICROPYTHON = sys.implementation.name == "micropython"

try:
    from micropython import const  # noqa: F401
except ImportError:  # CPython
    def const(x):
        return x

if hasattr(time, "ticks_ms"):
    def ticks_ms():
        return time.ticks_ms()

    def ticks_diff(a, b):
        return time.ticks_diff(a, b)

    def sleep_ms(ms):
        time.sleep_ms(ms)
else:
    def ticks_ms():
        return int(time.monotonic() * 1000)

    def ticks_diff(a, b):
        return a - b

    def sleep_ms(ms):
        time.sleep(ms / 1000.0)


def now_s():
    """Monotonic time in seconds (float)."""
    return ticks_ms() / 1000.0


def wall_time():
    """Wall-clock seconds since the epoch, or None if the clock is not set."""
    try:
        t = time.time()
    except Exception:
        return None
    # Boards without a set RTC report a date near 2000; treat that as unknown.
    return t if t > 1600000000 else None


def to_signed16(v):
    return v - 0x10000 if v & 0x8000 else v


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v
