#!/bin/sh
# Compile the MicroPython part of ups_hat to .mpy and zip it for a release.
#
#   tools/build_mpy.sh <path-to-mpy-cross>
#
# Output: build/mpy/ups_hat/*.mpy and dist/ups_hat-mpy-<version>.zip.
# cli.py and pimon.py are Raspberry Pi only and are left out (as in micropython/package.json).
set -eu
MPY_CROSS=${1:?usage: tools/build_mpy.sh <path-to-mpy-cross>}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
VERSION=$(python3 -c "import re;print(re.search(r'^version = \"([^\"]+)\"', open('pyproject.toml').read(), re.M).group(1))")
rm -rf build/mpy dist && mkdir -p build/mpy/ups_hat dist
for f in ups_hat/*.py; do
  case "$(basename "$f")" in cli.py|pimon.py) continue ;; esac
  "$MPY_CROSS" -o "build/mpy/ups_hat/$(basename "$f" .py).mpy" "$f"
done
MPY_INFO=$("$MPY_CROSS" --version)
cat > build/mpy/README.txt <<EOT
ups_hat $VERSION, precompiled for MicroPython.

Built with: $MPY_INFO
These files load on MicroPython firmware that uses the same .mpy version
(shown above). Copy the ups_hat folder to the board:

    mpremote cp -r ups_hat :

Documentation: https://pingoblin.github.io/UPS_HAT/
EOT
cp LICENSE build/mpy/LICENSE
(cd build/mpy && python3 -m zipfile -c "$ROOT/dist/ups_hat-mpy-$VERSION.zip" ups_hat README.txt LICENSE)
ls -l build/mpy/ups_hat dist
