"""Generate docs/api/faults.md from ups_hat.faults.CATALOGUE.

    python3 tools/gen_faults_md.py          write docs/api/faults.md
    python3 tools/gen_faults_md.py --check  exit 1 if docs/api/faults.md is out of date
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ups_hat.faults import CATALOGUE, SEVERITY_NAMES  # noqa: E402

ORDER = {"bus": 0, "charger": 1, "pd": 2, "inferred": 3, "pi": 4}
PATH = os.path.join(ROOT, "docs", "api", "faults.md")


def render():
    rows = sorted(CATALOGUE.items(), key=lambda kv: (ORDER[kv[1][1]], kv[0]))
    lines = [
        "# Fault codes",
        "",
        "Every fault the library reports, with what to do. [`CATALOGUE`][ups_hat.faults.CATALOGUE] holds the same list.",
        "",
        "| Severity | Meaning |",
        "|---|---|",
        "| `critical` | Act now. |",
        "| `warning` | Needs attention. |",
        "| `info` | No action needed. |",
        "",
        "| Source | Meaning |",
        "|---|---|",
        "| `charger` | Read from the BQ25798 charger. |",
        "| `pd` | Read from the STUSB4500 USB-C controller. |",
        "| `bus` | A chip did not answer on I²C. |",
        "| `inferred` | Worked out from measurements over time. Most must hold for 5 s to 2 minutes before they "
        "are reported. Confirm an inferred battery fault by measuring the cells before replacing anything. |",
        "| `pi` | Read from the Raspberry Pi 5 firmware. |",
        "",
        "| Code | Severity | Source | Meaning | What to do |",
        "|---|---|---|---|---|",
    ]
    for code, (sev, src, msg, adv) in rows:
        lines.append("| `{}` | {} | {} | {} | {} |".format(code, SEVERITY_NAMES[sev], src, msg, adv or "—"))
    return "\n".join(lines) + "\n"


def main():
    text = render()
    if "--check" in sys.argv:
        with open(PATH) as f:
            if f.read() != text:
                print("docs/api/faults.md is out of date: run python3 tools/gen_faults_md.py")
                return 1
        print("docs/api/faults.md is up to date")
        return 0
    with open(PATH, "w") as f:
        f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
