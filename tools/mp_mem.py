"""Measure the RAM ups_hat uses under MicroPython (run with the unix port).

    micropython tools/mp_mem.py <dir>

<dir> is the folder that holds the ups_hat package: "." for the .py source, or
"build/mpy" for the compiled .mpy files. Prints the bytes still allocated after
the import, and after creating a UPS on the register simulator and polling it.
Exits with an error (MemoryError) if the heap is too small.
"""
import gc
import sys

sys.path.insert(0, "tests")
from sim import FakeI2C   # loaded before the baseline so it is not counted

sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
gc.collect()
base = gc.mem_alloc()

import ups_hat            # noqa: E402

gc.collect()
imported = gc.mem_alloc() - base

bus = FakeI2C()
bus.bq.set_status()
bus.stusb.set_attached()
bus.stusb.set_contract(2, 3.0)
ups = ups_hat.UPS(bus, pi_monitor=False)
ups.poll()
ups.poll()
gc.collect()
running = gc.mem_alloc() - base
print("import_bytes", imported)
print("running_bytes", running)
