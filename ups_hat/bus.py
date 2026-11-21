"""I2C access for the UPS HAT+.

Any object with MicroPython's ``machine.I2C`` memory methods works::

    readfrom_mem(addr, reg, nbytes) -> bytes
    writeto_mem(addr, reg, buf)

On a Raspberry Pi (CPython) use :class:`LinuxI2C`, which talks to
``/dev/i2c-N`` directly and needs no extra packages.
"""

from ._compat import to_signed16


class UPSError(Exception):
    """Base class for all errors raised by this library."""


class DeviceNotFound(UPSError):
    """A chip did not answer on the I2C bus or reported the wrong ID."""


class BusError(UPSError):
    """An I2C transfer failed."""


class NotSupported(UPSError):
    """The operation is not possible on this board or in this environment."""


class LinuxI2C:
    """``machine.I2C``-compatible wrapper for Linux ``/dev/i2c-N``.

    Uses plain read()/write() on the character device, so it needs no
    third-party package. The Pi's header I2C is bus 1.
    """

    I2C_SLAVE = 0x0703

    def __init__(self, bus=1):
        import os
        import fcntl
        self._os = os
        self._fcntl = fcntl
        self._fd = os.open("/dev/i2c-%d" % bus, os.O_RDWR)
        self._addr = None
        self.bus = bus

    def _select(self, addr):
        if addr != self._addr:
            self._fcntl.ioctl(self._fd, self.I2C_SLAVE, addr)
            self._addr = addr

    def readfrom_mem(self, addr, reg, nbytes):
        self._select(addr)
        self._os.write(self._fd, bytes([reg]))
        data = self._os.read(self._fd, nbytes)
        if len(data) != nbytes:
            raise OSError(5, "short read")
        return data

    def writeto_mem(self, addr, reg, buf):
        self._select(addr)
        self._os.write(self._fd, bytes([reg]) + bytes(buf))

    def scan(self):
        found = []
        for addr in range(0x08, 0x78):
            try:
                self.readfrom_mem(addr, 0, 1)
                found.append(addr)
            except OSError:
                pass
        return found

    def close(self):
        if self._fd is not None:
            self._os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open_bus(bus=1):
    """Return an I2C object for the current platform.

    On Linux this is :class:`LinuxI2C` on ``/dev/i2c-<bus>``. On MicroPython
    create ``machine.I2C`` yourself (pins differ between boards) and pass it
    to :class:`ups_hat.UPS`.
    """
    import sys
    if sys.implementation.name == "micropython":
        raise NotSupported("pass a machine.I2C object, e.g. UPS(machine.I2C(0, sda=Pin(4), scl=Pin(5)))")
    return LinuxI2C(bus)


class I2CDevice:
    """Register access helpers for one chip."""

    def __init__(self, i2c, address, name="device"):
        self.i2c = i2c
        self.address = address
        self.name = name

    def read(self, reg, n):
        try:
            return self.i2c.readfrom_mem(self.address, reg, n)
        except OSError as e:
            raise BusError("%s (0x%02X): read of 0x%02X failed: %s" % (self.name, self.address, reg, e))

    def write(self, reg, data):
        try:
            self.i2c.writeto_mem(self.address, reg, bytes(data))
        except OSError as e:
            raise BusError("%s (0x%02X): write to 0x%02X failed: %s" % (self.name, self.address, reg, e))

    def u8(self, reg):
        return self.read(reg, 1)[0]

    def set_u8(self, reg, value):
        self.write(reg, (value & 0xFF,))

    def u16be(self, reg):
        b = self.read(reg, 2)
        return (b[0] << 8) | b[1]

    def s16be(self, reg):
        return to_signed16(self.u16be(reg))

    def set_u16be(self, reg, value):
        self.write(reg, ((value >> 8) & 0xFF, value & 0xFF))

    def u32le(self, reg):
        b = self.read(reg, 4)
        return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)

    def set_u32le(self, reg, value):
        self.write(reg, (value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF))

    def field(self, reg, shift, width, wide=False):
        v = self.u16be(reg) if wide else self.u8(reg)
        return (v >> shift) & ((1 << width) - 1)

    def set_field(self, reg, shift, width, value, wide=False):
        mask = ((1 << width) - 1) << shift
        v = self.u16be(reg) if wide else self.u8(reg)
        v = (v & ~mask) | ((int(value) << shift) & mask)
        if wide:
            self.set_u16be(reg, v)
        else:
            self.set_u8(reg, v)

    def bit(self, reg, n):
        return bool((self.u8(reg) >> n) & 1)

    def set_bit(self, reg, n, on):
        self.set_field(reg, n, 1, 1 if on else 0)

    def present(self):
        try:
            self.i2c.readfrom_mem(self.address, 0, 1)
            return True
        except OSError:
            return False
