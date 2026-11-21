"""Generate docs/faults.md from ups_hat.faults.CATALOGUE.

    python3 tools/gen_faults_md.py          write docs/faults.md
    python3 tools/gen_faults_md.py --check  exit 1 if docs/faults.md is out of date
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ups_hat.faults import CATALOGUE, SEVERITY_NAMES  # noqa: E402

ORDER = {"bus": 0, "charger": 1, "pd": 2, "inferred": 3, "pi": 4}
PATH = os.path.join(ROOT, "docs", "faults.md")


def render():
    rows = sorted(CATALOGUE.items(), key=lambda kv: (ORDER[kv[1][1]], kv[0]))
    lines = [
        "# Fault codes",
        "",
        "Every fault the library can report, as listed in [`CATALOGUE`][ups_hat.faults.CATALOGUE]. "
        "Codes are stable: safe to log, match on or show to users.",
        "",
        "- **Severity:** `info` needs no action, `warning` needs attention, `critical` needs action now.",
        "- **Source:** `charger` and `pd` faults are read from the chips; `bus` means a chip did not answer; "
        "`pi` comes from the Raspberry Pi 5 firmware; `inferred` faults are worked out from measurements over time "
        "and are a strong hint rather than proof. Most must persist for a few seconds to a few minutes before they "
        "are reported.",
        "",
        "The same list is printed by `ups-hat faults`.",
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
                print("docs/faults.md is out of date: run python3 tools/gen_faults_md.py")
                return 1
        print("docs/faults.md is up to date")
        return 0
    with open(PATH, "w") as f:
        f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
