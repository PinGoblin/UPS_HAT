# Installation

## Raspberry Pi

1. Enable I²C: `sudo raspi-config` → Interface Options → I2C. Alternatively, add `dtparam=i2c_arm=on` to `/boot/firmware/config.txt`.
2. Install the library from the repository folder:

    ```sh
    sudo pip install .           # add --break-system-packages on Bookworm
    ups-hat status               # or: python3 -m ups_hat.cli status
    ```

The library opens `/dev/i2c-1` by itself. Run it as root, or add your user to the `i2c` group.

## MicroPython

Copy the `ups_hat` folder to the board:

```sh
mpremote cp -r ups_hat :
```

Boards with little RAM should use precompiled `.mpy` files instead (MicroPython 1.19 or later). The `.pyi` type stubs and `py.typed` are not needed on the board.

```python
from machine import I2C, Pin
from ups_hat import UPS

ups = UPS(I2C(0, sda=Pin(4), scl=Pin(5), freq=400000), pi_monitor=False)
```

See [MicroPython notes](micropython.md).

## Command-line tool

| Command | What it does |
|---|---|
| `ups-hat status` | One-off report (the default). |
| `ups-hat watch [secs]` | Live report, refreshed every `secs` seconds (default 2). |
| `ups-hat json` | One snapshot as JSON. |
| `ups-hat faults` | List every fault code. |
| `ups-hat registers` | Dump the charger registers. |
| `ups-hat pd` | USB-C PD configuration and contract. |
| `ups-hat poweroff [low]` | systemd-shutdown hook: ship mode, reset or nothing. |

The tool reads `UPS_HAT_CELLS_PARALLEL` (default `1`), `UPS_HAT_CELL_MAH` (default `3000`) and `UPS_HAT_STATE` (default `/var/lib/ups-hat/state.json`) from the environment.
