from typing import Any, Dict, List, Sequence, Tuple

from .bus import I2CBus, I2CDevice

ADDRESS: int
REG_ALERT_STATUS: int
REG_PORT_STATUS_TRANS: int
REG_PORT_STATUS: int
REG_MON_STATUS_TRANS: int
REG_MON_STATUS: int
REG_CC_STATUS: int
REG_HW_FAULT_TRANS: int
REG_HW_FAULT: int
REG_PD_TYPEC_STATUS: int
REG_TYPEC_STATUS: int
REG_PRT_STATUS: int
REG_CMD_CTRL: int
REG_RESET_CTRL: int
REG_PE_FSM: int
REG_DEVICE_ID: int
REG_TX_HEADER_LOW: int
REG_RW_BUFFER: int
REG_DPM_PDO_NUMB: int
REG_DPM_SNK_PDO1: int
REG_RDO_STATUS: int
REG_FTP_PASSWORD: int
REG_FTP_CTRL_0: int
REG_FTP_CTRL_1: int
DEVICE_IDS: Tuple[int, ...]
FTP_PASSWORD: int
FTP_PWR: int
FTP_RST_N: int
FTP_REQ: int
FTP_SECT: int
FTP_SER: int
FTP_OPCODE: int
OP_READ: int
OP_WRITE_PL: int
OP_WRITE_SER: int
OP_ERASE: int
OP_PROG: int
OP_SOFT_PROG: int
TYPEC_FSM: Dict[int, str]
PE_STATE: Dict[int, str]
PE_SNK_READY: int
CC_STATE: Tuple[str, str, str, str]

class PDO:
    raw: int
    voltage: float
    current: float
    def __init__(self, raw: int) -> None: ...

class Contract:
    raw: int
    position: int
    operating_current: float
    max_current: float
    capability_mismatch: bool
    give_back: bool
    def __init__(self, raw: int) -> None: ...
    @property
    def valid(self) -> bool: ...

class STUSB4500:
    dev: I2CDevice
    def __init__(self, i2c: I2CBus, address: int = ..., check: bool = True) -> None: ...
    @property
    def device_id(self) -> int: ...
    def status(self) -> Dict[str, Any]: ...
    def monitoring_events(self) -> List[str]: ...
    def clear_alerts(self) -> None: ...
    @property
    def pe_state(self) -> int: ...
    @property
    def contract_ready(self) -> bool: ...
    @property
    def contract(self) -> Contract: ...
    @property
    def pdo_count(self) -> int: ...
    @pdo_count.setter
    def pdo_count(self, n: int) -> None: ...
    def sink_pdos(self, all_three: bool = False) -> List[PDO]: ...
    def set_sink_pdo(self, index: int, volts: float, amps: float) -> None: ...
    def renegotiate(self) -> None: ...
    def software_reset(self) -> None: ...
    def _ftp_wait(self) -> None: ...
    def _ftp_exit(self) -> None: ...
    def read_nvm(self) -> List[bytes]: ...
    def write_nvm(self, sectors: Sequence[bytes], confirm: bool = False) -> None: ...
    @staticmethod
    def decode_nvm_pdos(sectors: Sequence[bytes]) -> Tuple[int, List[Tuple[float, float]]]: ...
    @staticmethod
    def encode_nvm_pdos(
        sectors: Sequence[bytes], pdos: Sequence[Tuple[float, float]], count: int = 3
    ) -> List[bytes]: ...
