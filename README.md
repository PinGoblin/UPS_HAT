# ups_hat: PinGoblin UPS HAT+ library for Python and MicroPython

`ups_hat` reads and controls everything the PinGoblin UPS HAT+ can measure, control or report. The same code runs on a Raspberry Pi (Python 3.7 or later) and on MicroPython boards. It needs no third-party packages.

**Documentation:** <https://pingoblin.github.io/UPS_HAT/>

- **UPS HAT+ User Manual** (`docs/manual/`): Setting up and using the board and the UPS Pack.
- **UPS HAT+ API** (`docs/api/`): Installation, concepts, power-off integration, fault codes and the full API reference.

The files in `docs/` are the master copy of both. CI builds and publishes the site on every push to `main`.

## Installation

### Raspberry Pi

1. Enable I²C: Run `sudo raspi-config` and choose **Interface Options → I2C**.
2. Install the library and check that it can see the board:

    ```sh
    sudo pip install --break-system-packages git+https://github.com/PinGoblin/UPS_HAT
    ups-hat status
    ```

### MicroPython

Download `ups_hat-mpy-<version>.zip` from the [latest release](https://github.com/PinGoblin/UPS_HAT/releases/latest), unzip it and copy the folder to the board:

```sh
mpremote cp -r ups_hat :
```

See [Installation](https://pingoblin.github.io/UPS_HAT/api/guide/install/) for the full steps.

## Quick start

```python
from ups_hat import UPS, UPSError

try:
    ups = UPS(cells_parallel=1, cell_capacity_mah=3000)   # Raspberry Pi
    s = ups.poll()
except (UPSError, OSError) as e:
    raise SystemExit("UPS HAT+ not available: %s" % e)

print(s.vbat, s.ibat, s.soc, s.on_battery)
print(s.fault_codes())
print(ups.report(s))
```

## Examples

| Script | What it does |
|---|---|
| `examples/pi_status.py` | Prints the status once. |
| `examples/pi_daemon.py` | The monitoring service: logs faults and shuts the Pi down at low battery. |
| `examples/micropython_main.py` | MicroPython: prints the battery state every 2 s. |

Every example runs without hardware with `--mock`, from a copy of this repository:

```sh
PYTHONPATH=. python3 examples/pi_status.py --mock
```

## Contributing

Testing, CI, releases and the generated fault codes page: See [CONTRIBUTING.md](CONTRIBUTING.md).

## Version 1.4.0

The main class is `UPS` and the base error class is `UPSError`. Code written for 1.3 needs those two names changed; nothing else in the interface changed.

## Licence

MIT. See [LICENSE](LICENSE).
