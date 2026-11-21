from typing import Any, Dict, Optional, Tuple

INFO: int
WARNING: int
CRITICAL: int
SEVERITY_NAMES: Tuple[str, str, str]
CATALOGUE: Dict[str, Tuple[int, str, str, str]]

class Fault:
    code: str
    severity: int
    source: str
    message: str
    advice: str
    data: Dict[str, Any]
    transient: bool
    since: Optional[float]
    def __init__(
        self,
        code: str,
        data: Optional[Dict[str, Any]] = None,
        transient: bool = False,
        since: Optional[float] = None,
    ) -> None: ...
    @property
    def severity_name(self) -> str: ...
    def to_dict(self) -> Dict[str, Any]: ...

def _fmt(v: object) -> str: ...
