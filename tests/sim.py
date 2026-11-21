"""Register-level simulators of the BQ25798 and STUSB4500 for testing without hardware.
Runs on CPython and MicroPython."""


class FakeBQ25798:
    def __init__(self):
        self.r = bytearray(0x49)
        self.power_on_reset()
        self.adc = {"ibus": 0, "ibat": 0, "vbus": 0, "vac1": 0, "vac2": 0, "vbat": 7600,
                    "vsys": 7600, "ts": 614, "tdie": 60, "dp": 0, "dm": 0}
        self.flags = bytearray(6)
        self.writes = []

    def power_on_reset(self):
        r = self.r
        for i in range(len(r)):
            r[i] = 0
        r[0x00] = 0x12            # VSYSMIN 7.0 V
        r[0x01], r[0x02] = 0x03, 0x48   # VREG 8.40 V
        r[0x03], r[0x04] = 0x00, 0x64   # ICHG 1.00 A
        r[0x05] = 0x24
        r[0x06], r[0x07] = 0x01, 0x2C   # IINDPM 3.00 A
        r[0x08] = 0xC3
        r[0x09] = 0x05
        r[0x0A] = 0x63            # 2S, 1024 ms, 200 mV
        r[0x0E] = 0x3D
        r[0x0F] = 0xA2
        r[0x10] = 0x85            # watchdog 40 s
        r[0x11] = 0x40
        r[0x13] = 0x20            # 750 kHz
        r[0x14] = 0x16
        r[0x16] = 0xC0
        r[0x18] = 0x54            # NTC control 1, TS_IGNORE = 0
        r[0x2E] = 0x30
        r[0x48] = 0x19            # PN 3 (BQ25798), rev 1

    def set_status(self, vbus=True, pg=True, chg=3, vbat_present=True, extra0=0, s3=0, fault0=0, fault1=0):
        self.r[0x1B] = (0x08 if pg else 0) | (0x01 if vbus else 0) | (0x02 if vbus else 0) | extra0
        self.r[0x1C] = (chg << 5) | ((0x5 if vbus else 0) << 1)
        self.r[0x1D] = 0x01 if vbat_present else 0
        self.r[0x1E] = s3
        self.r[0x20] = fault0
        self.r[0x21] = fault1

    def _adc_bytes(self):
        out = bytearray()
        for k in ("ibus", "ibat", "vbus", "vac1", "vac2", "vbat", "vsys", "ts", "tdie", "dp", "dm"):
            v = int(self.adc[k]) & 0xFFFF
            out += bytes(((v >> 8) & 0xFF, v & 0xFF))
        return out

    def read(self, reg, n):
        img = bytearray(self.r)
        img[0x22:0x28] = self.flags
        img += bytearray(0x100 - len(img))
        img[0x31:0x31 + 22] = self._adc_bytes()
        img[0x48] = self.r[0x48]
        data = bytes(img[reg:reg + n])
        for a in range(reg, reg + n):          # flags clear on read
            if 0x22 <= a <= 0x27:
                self.flags[a - 0x22] = 0
        return data

    def write(self, reg, data):
        self.writes.append((reg, bytes(data)))
        for i, b in enumerate(data):
            a = reg + i
            if a == 0x09 and b & 0x40:         # REG_RST
                self.power_on_reset()
                continue
            if a == 0x10 and b & 0x08:         # WD_RST self-clears
                b &= ~0x08
            if a == 0x11 and not (self.r[0x14] & 0x80):
                b &= ~0x06                     # SDRV_CTRL locked without SFET_PRESENT
            if a < 0x49:
                self.r[a] = b


class FakeSTUSB4500:
    def __init__(self):
        self.r = bytearray(0x100)
        self.r[0x2F] = 0x25
        self.r[0x70] = 3
        self.nvm = [bytearray(b) for b in (
            (0x00, 0x00, 0xB0, 0xAA, 0x00, 0x45, 0x00, 0x00),
            (0x10, 0x40, 0x9C, 0x1C, 0xFF, 0x01, 0x3C, 0xDF),
            (0x02, 0x40, 0x0F, 0x00, 0x32, 0x00, 0xFC, 0xF1),
            (0x00, 0x19, 0x56, 0xAF, 0xF5, 0x35, 0x5F, 0x00),
            (0x00, 0x4B, 0x90, 0x21, 0x43, 0x00, 0x40, 0xFB))]
        self.pl = bytearray(8)
        self.set_pdo(1, 5.0, 3.0)
        self.set_pdo(2, 9.0, 3.0)
        self.set_pdo(3, 15.0, 3.0)
        self.soft_resets = 0
        self.nvm_writes = 0

    def set_pdo(self, n, v, a):
        raw = (int(round(v / 0.05)) << 10) | int(round(a / 0.01)) | (1 << 29 if n == 1 else 0)
        base = 0x85 + 4 * (n - 1)
        for i in range(4):
            self.r[base + i] = (raw >> (8 * i)) & 0xFF

    def set_contract(self, pos, amps, mismatch=False):
        raw = (pos << 28) | (int(amps * 100) << 10) | int(amps * 100) | ((1 << 26) if mismatch else 0)
        for i in range(4):
            self.r[0x91 + i] = (raw >> (8 * i)) & 0xFF

    def set_attached(self, attached=True, vbus_valid=True, pe_ready=True, cc="3.0 A"):
        code = {"open": 0, "default": 1, "1.5 A": 2, "3.0 A": 3}[cc]
        self.r[0x0E] = 0x01 if attached else 0
        self.r[0x10] = (0x02 | 0x08) if vbus_valid else 0x04
        self.r[0x11] = code
        self.r[0x15] = 0x02 if attached else 0
        self.r[0x29] = 0x18 if pe_ready else 0x14

    def read(self, reg, n):
        data = bytes(self.r[reg:reg + n])
        for a in range(reg, reg + n):
            if a in (0x0B, 0x0D, 0x0F, 0x12):
                self.r[a] = 0
        return data

    def write(self, reg, data):
        for i, b in enumerate(data):
            a = reg + i
            self.r[a] = b
            if a == 0x1A and b == 0x26 and self.r[0x51] == 0x0D:
                self.soft_resets += 1
            if a == 0x96 and b & 0x10 and self.r[0x95] == 0x47:
                self._ftp(b & 0x07, self.r[0x97] & 0x07)
                self.r[0x96] = b & ~0x10

    def _ftp(self, sector, op):
        if op == 0x00:       # read
            self.r[0x53:0x5B] = self.nvm[sector]
        elif op == 0x01:     # write PL
            self.pl = bytearray(self.r[0x53:0x5B])
        elif op == 0x06:     # program sector
            self.nvm[sector] = bytearray(self.pl)
            self.nvm_writes += 1
        elif op == 0x05:     # erase
            for s in self.nvm:
                for i in range(8):
                    s[i] = 0xFF


class FakeI2C:
    """machine.I2C-like bus holding the fake chips."""

    def __init__(self, bq=True, pd=True):
        self.devices = {}
        if bq:
            self.devices[0x6B] = FakeBQ25798()
        if pd:
            self.devices[0x28] = FakeSTUSB4500()

    @property
    def bq(self):
        return self.devices.get(0x6B)

    @property
    def stusb(self):
        return self.devices.get(0x28)

    def readfrom_mem(self, addr, reg, n):
        d = self.devices.get(addr)
        if d is None:
            raise OSError(19, "ENODEV")
        return d.read(reg, n)

    def writeto_mem(self, addr, reg, buf):
        d = self.devices.get(addr)
        if d is None:
            raise OSError(19, "ENODEV")
        d.write(reg, buf)
