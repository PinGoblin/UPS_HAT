#!/bin/sh
# Smallest MicroPython heap (KB) that can import ups_hat and run one UPS poll.
#
#   tools/mp_heap.sh <micropython-binary> <dir>
#
# <dir> as for tools/mp_mem.py. Uses the unix port's -X heapsize option and a
# binary search between 8 KB and 1024 KB. This includes the compiler's peak
# memory when <dir> holds .py files.
set -u
MP=$1; DIR=$2
lo=8; hi=1024
"$MP" -X heapsize=${hi}K tools/mp_mem.py "$DIR" >/dev/null 2>&1 || { echo "fails even at ${hi} KB"; exit 1; }
while [ $((hi - lo)) -gt 1 ]; do
  mid=$(((lo + hi) / 2))
  if "$MP" -X heapsize=${mid}K tools/mp_mem.py "$DIR" >/dev/null 2>&1; then hi=$mid; else lo=$mid; fi
done
echo "$hi"
