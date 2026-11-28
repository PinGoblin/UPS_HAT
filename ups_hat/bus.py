"""This module provides I²C access and exposes the library's exception classes.

Any object with MicroPython's `machine.I2C` memory methods can carry the I²C bus:

```python
readfrom_mem(addr, reg, nbytes) -> bytes
writeto_mem(addr, reg, buf)
```

On a Raspberry Pi (CPython), [`LinuxI2C`][ups_hat.bus.LinuxI2C] talks to `/dev/i2c-N`
directly and needs no extra packages.
"""

from ._compat import to_signed16


class UPSError(Exception):
    """Base class for every error raised by this library.

    Example:
        ```python
        from ups_hat import UPSError

        try:
            ups.ship_mode()
        except UPSError as e:
            print(e)
        ```
    """


class DeviceNotFound(UPSError):
    """A chip did not answer on the I²C bus, or reported the wrong ID.

    Example:
        ```python
        from ups_hat import DeviceNotFound

        try:
            ups.configure()
        except DeviceNotFound as e:
            print(e)
        ```
    """


class BusError(UPSError):
    """An I²C transfer failed.

    Example:
        ```python
        from ups_hat import BusError

        try:
            print(chg.read_adc())
        except BusError as e:
            print(e)
        ```
    """


class NotSupported(UPSError):
    """The operation is not possible on this board or in this environment.

    Raised, for example, by the power-off methods on a board built without the ship FET.

    Example:
        ```python
        from ups_hat import NotSupported

        try:
            ups.power_off()
        except NotSupported as e:
            print(e)
        ```
    """


class LinuxI2C:
    """`machine.I2C`-compatible wrapper for Linux `/dev/i2c-N`.

    Uses plain `read()`/`write()` on the character device, so it needs no third-party
    package. The Raspberry Pi header I²C (pins 3 and 5) is bus 1.

    Can be used as a context manager, which closes the device on exit.

    Args:
        bus: I²C bus number.

    Raises:
        OSError: The device file does not exist or cannot be opened (I²C disabled, or no
            permission: run as root or join the `i2c` group).

    Example:
        ```python
        from ups_hat import LinuxI2C, BQ25798

        with LinuxI2C(1) as i2c:
            print(BQ25798(i2c).read_adc())
        ```
    """

    I2C_SLAVE = 0x0703

    def __init__(self, bus=1):
        import os
        import fcntl
        self._os = os
        self._fcntl = fcntl
        path = "/dev/i2c-%d" % bus
        try:
            self._fd = os.open(path, os.O_RDWR)
        except OSError as e:
            if e.errno == 2:
                hint = "enable I2C with sudo raspi-config (Interface Options, I2C) and reboot"
            elif e.errno == 13:
                hint = "run as root, or add your user to the i2c group and log in again"
            else:
                hint = "check that I2C is enabled"
            raise OSError(e.errno, "cannot open %s: %s" % (path, hint), path)
        self._addr = None
        self.bus = bus

    def _select(self, addr):
        if addr != self._addr:
            self._fcntl.ioctl(self._fd, self.I2C_SLAVE, addr)
            self._addr = addr

    def readfrom_mem(self, addr, reg, nbytes):
        """Read consecutive registers from a device.

        Args:
            addr: 7-bit device address.
            reg: First register address.
            nbytes: Number of bytes to read.

        Returns:
            The bytes read.

        Raises:
            OSError: The transfer failed or returned fewer bytes than asked for.

        Example:
            ```python
            print(i2c.readfrom_mem(0x6B, 0x48, 1))
            ```
        """
        self._select(addr)
        self._os.write(self._fd, bytes([reg]))
        data = self._os.read(self._fd, nbytes)
        if len(data) != nbytes:
            raise OSError(5, "short read")
        return data

    def writeto_mem(self, addr, reg, buf):
        """Write consecutive registers on a device.

        Args:
            addr: 7-bit device address.
            reg: First register address.
            buf: Bytes to write.

        Raises:
            OSError: The transfer failed.

        Example:
            ```python
            i2c.writeto_mem(0x6B, 0x10, i2c.readfrom_mem(0x6B, 0x10, 1))   # write back unchanged
            ```
        """
        self._select(addr)
        self._os.write(self._fd, bytes([reg]) + bytes(buf))

    def scan(self):
        """List the devices that answer on the bus.

        Returns:
            7-bit addresses (0x08 to 0x77) that acknowledged a one-byte read.

        Example:
            ```python
            print([hex(a) for a in i2c.scan()])       # ['0x28', '0x6b']
            ```
        """
        found = []
        for addr in range(0x08, 0x78):
            try:
                self.readfrom_mem(addr, 0, 1)
                found.append(addr)
            except OSError:
                pass
        return found

    def close(self):
        """Close the device file. Safe to call more than once.

        Example:
            ```python
            i2c.close()
            ```
        """
        if self._fd is not None:
            self._os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open_bus(bus=1):
    """Return an I²C object for the current platform.

    On Linux this is a [`LinuxI2C`][ups_hat.bus.LinuxI2C] on `/dev/i2c-<bus>`. On
    MicroPython, create `machine.I2C` yourself (pins differ between boards) and pass it to
    [`UPS`][ups_hat.board.UPS].

    Args:
        bus: I²C bus number (Linux only).

    Returns:
        An object with `readfrom_mem()` and `writeto_mem()`.

    Raises:
        NotSupported: Called on MicroPython.
        OSError: The Linux device file cannot be opened.

    Example:
        ```python
        from ups_hat import open_bus

        i2c = open_bus(1)
        ```
    """
    import sys
    if sys.implementation.name == "micropython":
        raise NotSupported("UPS() cannot open the I2C bus on MicroPython: pass a machine.I2C object, "
                           "for example UPS(machine.I2C(0, sda=Pin(4), scl=Pin(5)))")
    return LinuxI2C(bus)


class I2CDevice:
    """Register access helpers for one chip.

    All methods raise [`BusError`][ups_hat.bus.BusError] when a transfer fails.

    Args:
        i2c: Bus object with `readfrom_mem()` and `writeto_mem()`.
        address: 7-bit device address.
        name: Chip name used in error messages.

    Example:
        ```python
        from ups_hat import I2CDevice, LinuxI2C

        dev = I2CDevice(LinuxI2C(1), 0x6B, "BQ25798")
        print(hex(dev.u8(0x48)))
        ```
    """

    def __init__(self, i2c, address, name="device"):
        self.i2c = i2c
        self.address = address
        self.name = name

    def read(self, reg, n):
        """Read consecutive registers.

        Args:
            reg: First register address.
            n: Number of bytes.

        Returns:
            The bytes read.

        Raises:
            BusError: The transfer failed.

        Example:
            ```python
            print(dev.read(0x00, 2))
            ```
        """
        try:
            return self.i2c.readfrom_mem(self.address, reg, n)
        except OSError as e:
            raise BusError("%s (0x%02X): read of 0x%02X failed: %s" % (self.name, self.address, reg, e))

    def write(self, reg, data):
        """Write consecutive registers.

        Args:
            reg: First register address.
            data: Bytes (or byte values) to write.

        Raises:
            BusError: The transfer failed.

        Example:
            ```python
            dev.write(0x10, dev.read(0x10, 1))       # write back unchanged
            ```
        """
        try:
            self.i2c.writeto_mem(self.address, reg, bytes(data))
        except OSError as e:
            raise BusError("%s (0x%02X): write to 0x%02X failed: %s" % (self.name, self.address, reg, e))

    def u8(self, reg):
        """Read one 8-bit register.

        Args:
            reg: Register address.

        Returns:
            The register value, 0 to 255.

        Example:
            ```python
            print(hex(dev.u8(0x48)))
            ```
        """
        return self.read(reg, 1)[0]

    def set_u8(self, reg, value):
        """Write one 8-bit register.

        Args:
            reg: Register address.
            value: Value; only the low 8 bits are written.

        Example:
            ```python
            dev.set_u8(0x10, dev.u8(0x10))           # write back unchanged
            ```
        """
        self.write(reg, (value & 0xFF,))

    def u16be(self, reg):
        """Read a 16-bit register pair, most significant byte first.

        Args:
            reg: Address of the high byte.

        Returns:
            The value, 0 to 65535.

        Example:
            ```python
            print(dev.u16be(0x01))
            ```
        """
        b = self.read(reg, 2)
        return (b[0] << 8) | b[1]

    def s16be(self, reg):
        """Read a signed 16-bit register pair, most significant byte first.

        Args:
            reg: Address of the high byte.

        Returns:
            The value, -32768 to 32767.

        Example:
            ```python
            print(dev.s16be(0x33))                   # battery current (mA)
            ```
        """
        return to_signed16(self.u16be(reg))

    def set_u16be(self, reg, value):
        """Write a 16-bit register pair, most significant byte first.

        Args:
            reg: Address of the high byte.
            value: Value, 0 to 65535.

        Example:
            ```python
            dev.set_u16be(0x01, 820)                 # charge voltage 8.20 V
            ```
        """
        self.write(reg, ((value >> 8) & 0xFF, value & 0xFF))

    def u32le(self, reg):
        """Read a 32-bit value stored least significant byte first.

        Args:
            reg: Address of the lowest byte.

        Returns:
            The value, 0 to 2³²−1.

        Example:
            ```python
            pd_dev = I2CDevice(i2c, 0x28, "STUSB4500")
            print(hex(pd_dev.u32le(0x85)))           # first sink PDO
            ```
        """
        b = self.read(reg, 4)
        return b[0] | (b[1] << 8) | (b[2] << 16) | (b[3] << 24)

    def set_u32le(self, reg, value):
        """Write a 32-bit value, least significant byte first.

        Args:
            reg: Address of the lowest byte.
            value: Value, 0 to 2³²−1.

        Example:
            ```python
            pd_dev = I2CDevice(i2c, 0x28, "STUSB4500")
            pd_dev.set_u32le(0x89, pd_dev.u32le(0x89))   # write back unchanged
            ```
        """
        self.write(reg, (value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF))

    def field(self, reg, shift, width, wide=False):
        """Read a bit field.

        Args:
            reg: Register address (the high byte when `wide` is true).
            shift: Position of the field's lowest bit.
            width: Field width in bits.
            wide: Read the field from a 16-bit big-endian register pair.

        Returns:
            The field value.

        Example:
            ```python
            print(dev.field(0x10, 0, 3))             # watchdog setting
            ```
        """
        v = self.u16be(reg) if wide else self.u8(reg)
        return (v >> shift) & ((1 << width) - 1)

    def set_field(self, reg, shift, width, value, wide=False):
        """Read-modify-write a bit field, leaving the other bits unchanged.

        Args:
            reg: Register address (the high byte when `wide` is true).
            shift: Position of the field's lowest bit.
            width: Field width in bits.
            value: New field value; excess bits are masked off.
            wide: The field is in a 16-bit big-endian register pair.

        Example:
            ```python
            dev.set_field(0x10, 0, 3, 0)             # watchdog off
            ```
        """
        mask = ((1 << width) - 1) << shift
        v = self.u16be(reg) if wide else self.u8(reg)
        v = (v & ~mask) | ((int(value) << shift) & mask)
        if wide:
            self.set_u16be(reg, v)
        else:
            self.set_u8(reg, v)

    def bit(self, reg, n):
        """Read one bit.

        Args:
            reg: Register address.
            n: Bit number, 0 = least significant.

        Returns:
            `True` if the bit is set.

        Example:
            ```python
            print(dev.bit(0x0F, 5))                  # charge enable
            ```
        """
        return bool((self.u8(reg) >> n) & 1)

    def set_bit(self, reg, n, on):
        """Set or clear one bit, leaving the others unchanged.

        Args:
            reg: Register address.
            n: Bit number, 0 = least significant.
            on: `True` to set, `False` to clear.

        Example:
            ```python
            dev.set_bit(0x0F, 5, True)               # charge enable on
            ```
        """
        self.set_field(reg, n, 1, 1 if on else 0)

    def present(self):
        """Check that the chip answers.

        Returns:
            `True` if a one-byte read of register 0 succeeds.

        Example:
            ```python
            print(dev.present())
            ```
        """
        try:
            self.i2c.readfrom_mem(self.address, 0, 1)
            return True
        except OSError:
            return False
