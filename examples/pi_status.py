"""Print the UPS HAT+ status once (Raspberry Pi)."""
from ups_hat import UPS

ups = UPS(cells_parallel=1, cell_capacity_mah=3000)
s = ups.poll()
print(ups.report(s))
print()
print("On battery:", s.on_battery, " SoC:", s.soc, " Faults:", s.fault_codes())
