"""ups_hat.bus: exceptions, I2CDevice register helpers, LinuxI2C and open_bus."""

import errno
import sys
import types
import unittest
from unittest import mock

import helpers  # noqa: F401
from ups_hat import bus as bus_mod
from ups_hat.bus import (BusError, DeviceNotFound, I2CDevice, LinuxI2C, NotSupported, UPSError,
                         open_bus)


class MemoryBus:
    """machine.I2C-style bus backed by a 256-byte register file per address."""

    def __init__(self, addresses=(0x50,)):
        self.mem = {a: bytearray(256) for a in addresses}
        self.writes = []
        self.fail_reads = False
        self.fail_writes = False

    def readfrom_mem(self, addr, reg, n):
        if self.fail_reads or addr not in self.mem:
            raise OSError(errno.EIO, "EIO")
        return bytes(self.mem[addr][reg:reg + n])

    def writeto_mem(self, addr, reg, buf):
        if self.fail_writes or addr not in self.mem:
            raise OSError(errno.EIO, "EIO")
        self.writes.append((addr, reg, bytes(buf)))
        self.mem[addr][reg:reg + len(buf)] = buf


class ExceptionTests(unittest.TestCase):
    def test_hierarchy(self):
        for cls in (DeviceNotFound, BusError, NotSupported):
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(cls, UPSError))
        self.assertTrue(issubclass(UPSError, Exception))

    def test_reexported_from_package(self):
        import ups_hat
        for name in ("UPSError", "DeviceNotFound", "BusError", "NotSupported", "LinuxI2C", "I2CDevice", "open_bus"):
            with self.subTest(name=name):
                self.assertIs(getattr(ups_hat, name), getattr(bus_mod, name))


class I2CDeviceTests(unittest.TestCase):
    def setUp(self):
        self.bus = MemoryBus()
        self.dev = I2CDevice(self.bus, 0x50, "TEST")

    def test_read_write_bytes(self):
        self.dev.write(0x10, [1, 2, 3])
        self.assertEqual(self.dev.read(0x10, 3), b"\x01\x02\x03")
        self.assertEqual(self.bus.writes[-1], (0x50, 0x10, b"\x01\x02\x03"))

    def test_u8(self):
        self.dev.set_u8(0x05, 0x1FF)          # only the low 8 bits are written
        self.assertEqual(self.dev.u8(0x05), 0xFF)

    def test_u16_big_endian(self):
        self.dev.set_u16be(0x01, 0x0334)
        self.assertEqual(bytes(self.bus.mem[0x50][1:3]), b"\x03\x34")
        self.assertEqual(self.dev.u16be(0x01), 820)

    def test_s16_big_endian(self):
        self.dev.set_u16be(0x20, 0xFA24)
        self.assertEqual(self.dev.s16be(0x20), -1500)

    def test_u32_little_endian(self):
        self.dev.set_u32le(0x91, 0x2004B12C)
        self.assertEqual(bytes(self.bus.mem[0x50][0x91:0x95]), b"\x2c\xb1\x04\x20")
        self.assertEqual(self.dev.u32le(0x91), 0x2004B12C)

    def test_field_and_set_field_leave_other_bits(self):
        self.dev.set_u8(0x10, 0b1010_1010)
        self.dev.set_field(0x10, 2, 3, 0b111)
        self.assertEqual(self.dev.u8(0x10), 0b1011_1110)
        self.assertEqual(self.dev.field(0x10, 2, 3), 0b111)
        self.dev.set_field(0x10, 2, 3, 0b1_000)  # excess bits masked off
        self.assertEqual(self.dev.u8(0x10), 0b1010_0010)

    def test_wide_field(self):
        self.dev.set_u16be(0x03, 0xFE00)
        self.dev.set_field(0x03, 0, 9, 150, wide=True)
        self.assertEqual(self.dev.u16be(0x03), 0xFE00 | 150)
        self.assertEqual(self.dev.field(0x03, 0, 9, wide=True), 150)

    def test_bits(self):
        self.dev.set_bit(0x14, 7, True)
        self.dev.set_bit(0x14, 5, True)
        self.assertTrue(self.dev.bit(0x14, 7))
        self.dev.set_bit(0x14, 7, False)
        self.assertFalse(self.dev.bit(0x14, 7))
        self.assertTrue(self.dev.bit(0x14, 5))

    def test_present(self):
        self.assertTrue(self.dev.present())
        self.assertFalse(I2CDevice(self.bus, 0x51).present())

    def test_read_error_becomes_bus_error(self):
        self.bus.fail_reads = True
        with self.assertRaises(BusError) as cm:
            self.dev.u8(0x2A)
        self.assertIn("TEST (0x50)", str(cm.exception))
        self.assertIn("0x2A", str(cm.exception))

    def test_write_error_becomes_bus_error(self):
        self.bus.fail_writes = True
        with self.assertRaises(BusError) as cm:
            self.dev.set_u8(0x2B, 1)
        self.assertIn("write to 0x2B", str(cm.exception))


class LinuxI2CTests(unittest.TestCase):
    """LinuxI2C with os/fcntl replaced, so no /dev/i2c-N is needed."""

    def setUp(self):
        self.os = mock.Mock()
        self.os.O_RDWR = 2
        self.os.open.return_value = 7
        self.os.read.side_effect = lambda fd, n: bytes(range(n))
        self.fcntl = mock.Mock()
        # LinuxI2C imports os and fcntl inside __init__: swap them only for that call.
        with mock.patch.dict(sys.modules, {"os": self.os, "fcntl": self.fcntl}):
            self.i2c = LinuxI2C(3)
        self.assertIs(self.i2c._os, self.os)

    def test_opens_device_file(self):
        self.os.open.assert_called_once_with("/dev/i2c-3", 2)
        self.assertEqual(self.i2c.bus, 3)

    def test_read_selects_address_once(self):
        self.assertEqual(self.i2c.readfrom_mem(0x6B, 0x31, 4), b"\x00\x01\x02\x03")
        self.i2c.readfrom_mem(0x6B, 0x00, 1)
        self.fcntl.ioctl.assert_called_once_with(7, LinuxI2C.I2C_SLAVE, 0x6B)
        self.i2c.readfrom_mem(0x28, 0x00, 1)
        self.assertEqual(self.fcntl.ioctl.call_count, 2)
        self.os.write.assert_any_call(7, b"\x31")

    def test_short_read_raises(self):
        self.os.read.side_effect = lambda fd, n: b"\x00"
        with self.assertRaises(OSError):
            self.i2c.readfrom_mem(0x6B, 0x31, 22)

    def test_write_prefixes_register(self):
        self.i2c.writeto_mem(0x6B, 0x01, b"\x03\x34")
        self.os.write.assert_called_with(7, b"\x01\x03\x34")

    def test_scan(self):
        def read(fd, n):
            return b"\x00"

        def ioctl(fd, req, addr):
            self.current = addr

        def write(fd, data):
            if self.current not in (0x28, 0x6B):
                raise OSError(errno.ENXIO, "no device")

        self.fcntl.ioctl.side_effect = ioctl
        self.os.write.side_effect = write
        self.os.read.side_effect = read
        self.assertEqual(self.i2c.scan(), [0x28, 0x6B])

    def test_close_is_idempotent_and_context_manager(self):
        with self.i2c as i2c:
            self.assertIs(i2c, self.i2c)
        self.os.close.assert_called_once_with(7)
        self.i2c.close()
        self.os.close.assert_called_once_with(7)

    def test_missing_device_file(self):
        self.os.open.side_effect = FileNotFoundError(errno.ENOENT, "No such file")
        with mock.patch.dict(sys.modules, {"os": self.os, "fcntl": self.fcntl}):
            with self.assertRaises(OSError):
                LinuxI2C(9)


class OpenBusTests(unittest.TestCase):
    def test_linux_returns_linux_i2c(self):
        with mock.patch.object(bus_mod, "LinuxI2C") as cls:
            self.assertIs(open_bus(4), cls.return_value)
        cls.assert_called_once_with(4)

    def test_micropython_needs_machine_i2c(self):
        fake = types.SimpleNamespace(name="micropython")
        with mock.patch.object(sys, "implementation", fake):
            with self.assertRaises(NotSupported):
                open_bus()


if __name__ == "__main__":
    unittest.main()
