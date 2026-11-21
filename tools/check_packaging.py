"""Check that the version and the MicroPython file list agree everywhere.

    python3 tools/check_packaging.py [tag]

Checks pyproject.toml, ups_hat.__version__ and micropython/package.json share
one version (and match the Git tag, e.g. v1.4.0, if one is given), and that
package.json lists every module except the Raspberry Pi-only cli.py and pimon.py.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PI_ONLY = {"cli.py", "pimon.py"}


def main():
    errors = []
    py = re.search(r'^version = "([^"]+)"', open(os.path.join(ROOT, "pyproject.toml")).read(), re.M).group(1)
    init = re.search(r'^__version__ = "([^"]+)"', open(os.path.join(ROOT, "ups_hat", "__init__.py")).read(),
                     re.M).group(1)
    pkg = json.load(open(os.path.join(ROOT, "micropython", "package.json")))
    versions = {"pyproject.toml": py, "ups_hat/__init__.py": init, "micropython/package.json": pkg["version"]}
    if len(sys.argv) > 1:
        versions["git tag"] = sys.argv[1].lstrip("v")
    if len(set(versions.values())) != 1:
        errors.append("versions differ: " + ", ".join("%s %s" % kv for kv in versions.items()))

    modules = {f for f in os.listdir(os.path.join(ROOT, "ups_hat")) if f.endswith(".py")} - PI_ONLY
    listed = {dest.split("/")[-1] for dest, _ in pkg["urls"]}
    if listed != modules:
        errors.append("package.json lists %s, expected %s" % (sorted(listed), sorted(modules)))
    for dest, src in pkg["urls"]:
        if not src.endswith("/" + dest):
            errors.append("package.json: %s does not match %s" % (dest, src))

    for e in errors:
        print(e)
    if not errors:
        print("packaging OK, version", py)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
