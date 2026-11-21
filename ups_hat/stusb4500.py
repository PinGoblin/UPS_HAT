"""Driver for the ST STUSB4500 USB-C PD sink controller (U1, I2C address 0x28).

Register map and NVM sequence follow ST's public register map and reference
software (github.com/usb-c/STUSB4500) and SparkFun's STUSB4500 library.
The negotiated contract (RDO) gives the source PDO position and the current.
The source's voltage list is only on the bus for ~3 ms during negotiation, so
the contract voltage is best taken from the charger's VBUS ADC.
"""

from .bus import I2CDevice, DeviceNotFound, UPSError
from ._compat import const, sleep_ms, clamp

ADDRESS = const(0x28)

REG_ALERT_STATUS = const(0x0B)
REG_PORT_STATUS_TRANS = const(0x0D)
REG_PORT_STATUS = const(0x0E)
REG_MON_STATUS_TRANS = const(0x0F)
REG_MON_STATUS = const(0x10)
REG_CC_STATUS = const(0x11)
REG_HW_FAULT_TRANS = const(0x12)
REG_HW_FAULT = const(0x13)
REG_PD_TYPEC_STATUS = const(0x14)
REG_TYPEC_STATUS = const(0x15)
REG_PRT_STATUS = const(0x16)
REG_CMD_CTRL = const(0x1A)
REG_RESET_CTRL = const(0x23)
REG_PE_FSM = const(0x29)
REG_DEVICE_ID = const(0x2F)
REG_TX_HEADER_LOW = const(0x51)
REG_RW_BUFFER = const(0x53)
REG_DPM_PDO_NUMB = const(0x70)
REG_DPM_SNK_PDO1 = const(0x85)
REG_RDO_STATUS = const(0x91)
REG_FTP_PASSWORD = const(0x95)
REG_FTP_CTRL_0 = const(0x96)
REG_FTP_CTRL_1 = const(0x97)

DEVICE_IDS = (0x21, 0x25)

FTP_PASSWORD = const(0x47)
FTP_PWR = const(0x80)
FTP_RST_N = const(0x40)
FTP_REQ = const(0x10)
FTP_SECT = const(0x07)
FTP_SER = const(0xF8)
FTP_OPCODE = const(0x07)
OP_READ = const(0x00)
OP_WRITE_PL = const(0x01)
OP_WRITE_SER = const(0x02)
OP_ERASE = const(0x05)
OP_PROG = const(0x06)
OP_SOFT_PROG = const(0x07)

TYPEC_FSM = {
    0x00: "unattached.SNK", 0x01: "AttachWait.SNK", 0x02: "Attached.SNK",
    0x06: "SNK to SRC PR swap", 0x07: "TryWait.SNK", 0x13: "ErrorRecovery",
}
PE_STATE = {
    0x00: "init", 0x01: "soft reset", 0x02: "hard reset", 0x03: "send soft reset",
    0x04: "BIST", 0x0D: "disabled", 0x12: "SNK startup", 0x13: "SNK discovery",
    0x14: "SNK wait for capabilities", 0x15: "SNK evaluate capabilities",
    0x16: "SNK select capability", 0x17: "SNK transition sink", 0x18: "SNK ready",
    0x19: "SNK ready (sending)", 0x3A: "hard reset shutdown", 0x3B: "hard reset recovery",
    0x40: "error recovery",
}
PE_SNK_READY = const(0x18)
CC_STATE = ("open", "default USB (Rp 500/900 mA)", "1.5 A", "3.0 A")


class PDO:
    """A fixed-supply sink PDO."""

    def __init__(self, raw):
        self.raw = raw
        self.voltage = ((raw >> 10) & 0x3FF) * 0.05
        self.current = (raw & 0x3FF) * 0.01

    def __repr__(self):
        return "PDO({:.2f} V, {:.2f} A)".format(self.voltage, self.current)


class Contract:
    """The request (RDO) the STUSB4500 made and the source accepted."""

    def __init__(self, raw):
        self.raw = raw
        self.position = (raw >> 28) & 7          # source PDO index, 1-based, 0 = none
        self.operating_current = ((raw >> 10) & 0x3FF) * 0.01
        self.max_current = (raw & 0x3FF) * 0.01
        self.capability_mismatch = bool((raw >> 26) & 1)
        self.give_back = bool((raw >> 27) & 1)

    @property
    def valid(self):
        return self.position != 0

    def __repr__(self):
        if not self.valid:
            return "Contract(none)"
        return "Contract(source PDO {}, {:.2f} A{})".format(
            self.position, self.operating_current, ", capability mismatch" if self.capability_mismatch else "")


class STUSB4500:
    def __init__(self, i2c, address=ADDRESS, check=True):
        self.dev = I2CDevice(i2c, address, "STUSB4500")
        if check:
            did = self.device_id
            if did not in DEVICE_IDS:
                raise DeviceNotFound("STUSB4500 not found at 0x%02X (ID 0x%02X)" % (address, did))

    @property
    def device_id(self):
        return self.dev.u8(REG_DEVICE_ID)

    # ---- connection status -----------------------------------------------------------
    def status(self):
        # Read one register at a time: 0x0F and 0x12 clear on read and belong to monitoring_events().
        d = self.dev
        port, mon, cc = d.u8(REG_PORT_STATUS), d.u8(REG_MON_STATUS), d.u8(REG_CC_STATUS)
        hw, typec = d.u8(REG_HW_FAULT), d.u8(REG_TYPEC_STATUS)
        pe = self.pe_state
        fsm = typec & 0x1F
        return {
            "attached": bool(port & 0x01),
            "power_role": "source" if port & 0x08 else "sink",
            "data_role": "DFP" if port & 0x04 else "UFP",
            "attach_mode": (port >> 5) & 7,
            "vbus_valid": bool(mon & 0x02),
            "vbus_vsafe0v": bool(mon & 0x04),
            "vbus_ready": bool(mon & 0x08),
            "cc1": CC_STATE[cc & 3],
            "cc2": CC_STATE[(cc >> 2) & 3],
            "looking_for_connection": bool(cc & 0x20),
            "orientation": "CC2" if typec & 0x80 else "CC1",
            "typec_state": TYPEC_FSM.get(fsm, "0x%02X" % fsm),
            "vpu_ovp": bool(hw & 0x80),
            "vpu_present": bool(hw & 0x40),
            "vbus_discharge_fault": bool(hw & 0x20),
            "pe_state": pe,
            "pe_state_text": PE_STATE.get(pe, "0x%02X" % pe),
        }

    def monitoring_events(self):
        """Transition flags since the last read (reading clears them)."""
        port_t = self.dev.u8(REG_PORT_STATUS_TRANS)
        mon_t = self.dev.u8(REG_MON_STATUS_TRANS)
        hw_t = self.dev.u8(REG_HW_FAULT_TRANS)
        ev = []
        if port_t & 0x01:
            ev.append("ATTACH_CHANGED")
        if mon_t & 0x02:
            ev.append("VBUS_VALID_CHANGED")
        if mon_t & 0x08:
            ev.append("VBUS_READY_CHANGED")
        if mon_t & 0x10:
            ev.append("VBUS_LOW")
        if mon_t & 0x20:
            ev.append("VBUS_HIGH")
        if hw_t & 0x20:
            ev.append("VPU_OVP")
        if hw_t & 0x80:
            ev.append("THERMAL_FAULT")
        return ev

    def clear_alerts(self):
        """Read ALERT_STATUS and the transition registers to clear the ALERT pin."""
        self.dev.read(REG_ALERT_STATUS, 0x0D - REG_ALERT_STATUS + 1)
        self.monitoring_events()

    @property
    def pe_state(self):
        return self.dev.u8(REG_PE_FSM)

    @property
    def contract_ready(self):
        return self.pe_state == PE_SNK_READY

    @property
    def contract(self):
        return Contract(self.dev.u32le(REG_RDO_STATUS))

    # ---- sink PDOs in RAM (loaded from NVM at power-up) -----------------------------
    @property
    def pdo_count(self):
        return self.dev.u8(REG_DPM_PDO_NUMB) & 7

    @pdo_count.setter
    def pdo_count(self, n):
        self.dev.set_u8(REG_DPM_PDO_NUMB, clamp(int(n), 1, 3))

    def sink_pdos(self, all_three=False):
        n = 3 if all_three else self.pdo_count
        return [PDO(self.dev.u32le(REG_DPM_SNK_PDO1 + 4 * i)) for i in range(n)]

    def set_sink_pdo(self, index, volts, amps):
        """Change sink PDO 1-3 in RAM (lost at power-off). PDO1 is always 5 V.
        Call :meth:`renegotiate` to apply."""
        if index not in (1, 2, 3):
            raise ValueError("PDO index must be 1, 2 or 3")
        if index == 1:
            volts = 5.0
        reg = REG_DPM_SNK_PDO1 + 4 * (index - 1)
        raw = self.dev.u32le(reg)
        raw &= ~0xFFFFF
        raw |= (int(round(clamp(volts, 5.0, 20.0) / 0.05)) & 0x3FF) << 10
        raw |= int(round(clamp(amps, 0.0, 5.0) / 0.01)) & 0x3FF
        self.dev.set_u32le(reg, raw)

    def renegotiate(self):
        """Send a PD soft reset so the source re-offers and the sink re-requests.
        VBUS normally stays up, but the source may briefly drop to 5 V."""
        self.dev.set_u8(REG_TX_HEADER_LOW, 0x0D)
        self.dev.set_u8(REG_CMD_CTRL, 0x26)

    def software_reset(self):
        """Full chip reset (as the RESET pin). The port detaches and VBUS falls to 5 V or off."""
        self.dev.set_u8(REG_RESET_CTRL, 1)
        sleep_ms(30)
        self.dev.set_u8(REG_RESET_CTRL, 0)

    # ---- NVM -------------------------------------------------------------------------
    def _ftp_wait(self):
        for _ in range(200):
            if not self.dev.u8(REG_FTP_CTRL_0) & FTP_REQ:
                return
            sleep_ms(1)
        raise UPSError("STUSB4500 NVM operation timed out")

    def _ftp_exit(self):
        self.dev.set_u8(REG_FTP_CTRL_0, FTP_RST_N)
        self.dev.set_u8(REG_FTP_PASSWORD, 0)

    def read_nvm(self):
        """Return the 5 NVM sectors as a list of 5 bytes objects (8 bytes each)."""
        d = self.dev
        sectors = []
        try:
            d.set_u8(REG_FTP_PASSWORD, FTP_PASSWORD)
            d.set_u8(REG_FTP_CTRL_0, 0)
            d.set_u8(REG_FTP_CTRL_0, FTP_PWR | FTP_RST_N)
            for s in range(5):
                d.set_u8(REG_FTP_CTRL_0, FTP_PWR | FTP_RST_N)
                d.set_u8(REG_FTP_CTRL_1, OP_READ & FTP_OPCODE)
                d.set_u8(REG_FTP_CTRL_0, (s & FTP_SECT) | FTP_PWR | FTP_RST_N | FTP_REQ)
                self._ftp_wait()
                sectors.append(bytes(d.read(REG_RW_BUFFER, 8)))
        finally:
            self._ftp_exit()
        return sectors

    def write_nvm(self, sectors, confirm=False):
        """Erase and program all 5 NVM sectors. For factory use only.

        The NVM has limited write endurance; pass confirm=True to proceed.
        """
        if not confirm:
            raise UPSError("write_nvm needs confirm=True (factory operation)")
        if len(sectors) != 5 or any(len(s) != 8 for s in sectors):
            raise ValueError("need 5 sectors of 8 bytes")
        d = self.dev
        try:
            d.set_u8(REG_FTP_PASSWORD, FTP_PASSWORD)
            d.set_u8(REG_RW_BUFFER, 0)
            d.set_u8(REG_FTP_CTRL_0, 0)
            d.set_u8(REG_FTP_CTRL_0, FTP_PWR | FTP_RST_N)
            d.set_u8(REG_FTP_CTRL_1, ((0x1F << 3) & FTP_SER) | (OP_WRITE_SER & FTP_OPCODE))
            d.set_u8(REG_FTP_CTRL_0, FTP_PWR | FTP_RST_N | FTP_REQ)
            self._ftp_wait()
            for op in (OP_SOFT_PROG, OP_ERASE):
                d.set_u8(REG_FTP_CTRL_1, op & FTP_OPCODE)
                d.set_u8(REG_FTP_CTRL_0, FTP_PWR | FTP_RST_N | FTP_REQ)
                self._ftp_wait()
            for s in range(5):
                d.write(REG_RW_BUFFER, sectors[s])
                d.set_u8(REG_FTP_CTRL_0, FTP_PWR | FTP_RST_N)
                d.set_u8(REG_FTP_CTRL_1, OP_WRITE_PL & FTP_OPCODE)
                d.set_u8(REG_FTP_CTRL_0, FTP_PWR | FTP_RST_N | FTP_REQ)
                self._ftp_wait()
                d.set_u8(REG_FTP_CTRL_1, OP_PROG & FTP_OPCODE)
                d.set_u8(REG_FTP_CTRL_0, (s & FTP_SECT) | FTP_PWR | FTP_RST_N | FTP_REQ)
                self._ftp_wait()
        finally:
            self._ftp_exit()

    @staticmethod
    def decode_nvm_pdos(sectors):
        """Sink PDOs stored in NVM: list of (volts, amps), plus the PDO count."""
        s3, s4 = sectors[3], sectors[4]

        def cur(code):
            if code == 0:
                return 0.0
            return code * 0.25 + 0.25 if code < 11 else code * 0.5 - 2.5

        n = (s3[2] & 0x06) >> 1
        pdos = [
            (5.0, cur((s3[2] & 0xF0) >> 4)),
            (((s4[1] << 2) + (s4[0] >> 6)) / 20.0, cur(s3[4] & 0x0F)),
            ((((s4[3] & 0x03) << 8) + s4[2]) / 20.0, cur((s3[5] & 0xF0) >> 4)),
        ]
        return n, pdos

    @staticmethod
    def encode_nvm_pdos(sectors, pdos, count=3):
        """Return new sectors with PDO voltages/currents and count replaced.
        pdos = [(5.0, a1), (v2, a2), (v3, a3)]."""
        s = [bytearray(x) for x in sectors]

        def code(a):
            a = clamp(a, 0.0, 5.0)
            if a < 0.5:
                return 0
            return int(4 * a - 1) if a <= 3.0 else int(2 * a + 5)

        s[3][2] = (s[3][2] & 0x0F) | (code(pdos[0][1]) << 4)
        s[3][4] = (s[3][4] & 0xF0) | code(pdos[1][1])
        s[3][5] = (s[3][5] & 0x0F) | (code(pdos[2][1]) << 4)
        v2 = int(round(clamp(pdos[1][0], 5.0, 20.0) * 20))
        s[4][0] = (s[4][0] & 0x3F) | ((v2 & 0x03) << 6)
        s[4][1] = (v2 >> 2) & 0xFF
        v3 = int(round(clamp(pdos[2][0], 5.0, 20.0) * 20))
        s[4][2] = v3 & 0xFF
        s[4][3] = (s[4][3] & 0xFC) | ((v3 >> 8) & 0x03)
        s[3][2] = (s[3][2] & 0xF9) | ((clamp(count, 1, 3) & 3) << 1)
        return [bytes(x) for x in s]
