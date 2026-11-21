"""Portability layer so the same code runs on MicroPython and CPython.

Internal module: not part of the public interface.
"""

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
    """Monotonic time.

    Returns:
        Seconds from an arbitrary start point, as a float. Only differences are meaningful.
    """
    return ticks_ms() / 1000.0


def wall_time():
    """Wall-clock time, if the clock has been set.

    Returns:
        Seconds since the Unix epoch, or `None` on a board whose clock has not been set.
    """
    try:
        t = time.time()
    except Exception:
        return None
    # Boards without a set RTC report a date near 2000; treat that as unknown.
    return t if t > 1600000000 else None


def to_signed16(v):
    """Convert a 16-bit register value to a signed integer.

    Args:
        v: Unsigned value, 0 to 65535.

    Returns:
        The two's-complement value, -32768 to 32767.
    """
    return v - 0x10000 if v & 0x8000 else v


def clamp(v, lo, hi):
    """Limit a value to a range.

    Args:
        v: Value to limit.
        lo: Lowest allowed value.
        hi: Highest allowed value.

    Returns:
        `v`, or the nearer limit if `v` is outside `lo`..`hi`.
    """
    return lo if v < lo else hi if v > hi else v
