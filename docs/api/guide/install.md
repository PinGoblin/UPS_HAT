# Installation

## Raspberry Pi

1. Enable I²C: Run `sudo raspi-config` and choose **Interface Options → I2C**, or add `dtparam=i2c_arm=on` to `/boot/firmware/config.txt` and reboot.
2. Give your user access to I²C, then log out and back in:

    ```sh
    sudo usermod -aG i2c $USER
    ```

3. Install the library:

    ```sh
    sudo pip install --break-system-packages git+https://github.com/PinGoblin/UPS_HAT
    ```

    To install a particular release, add its tag: `git+https://github.com/PinGoblin/UPS_HAT@v1.4.0`.

4. Check that the library can see the PinGoblin UPS HAT+:

    ```sh
    ups-hat status
    ```

## MicroPython

Connect the PinGoblin UPS HAT+ header I²C pins to the board: Pin 3 (SDA), pin 5 (SCL) and pin 6 (GND).

=== "Precompiled files (recommended)"

    1. Download `ups_hat-mpy-<version>.zip` from the [latest release](https://github.com/PinGoblin/UPS_HAT/releases/latest) and unzip it.
    2. Check that the `.mpy` version in `README.txt` in the zip matches your MicroPython firmware.
    3. Copy the folder to the board:

        ```sh
        mpremote cp -r ups_hat :
        ```

    The board loads these files without compiling them, so they need the least RAM.

=== "Source files"

    Install the `.py` files from GitHub into `/lib` on the board:

    ```sh
    mpremote mip install github:PinGoblin/UPS_HAT/micropython            # latest
    mpremote mip install github:PinGoblin/UPS_HAT/micropython@v1.4.0     # a release
    ```

    The board compiles these files when you import them, which needs more RAM: See [MicroPython notes](micropython.md).

Then create a `UPS` with your board's I²C pins, for example on a Raspberry Pi Pico:

```python
from machine import I2C, Pin
from ups_hat import UPS

ups = UPS(I2C(0, sda=Pin(4), scl=Pin(5), freq=400000), pi_monitor=False)
print(ups.report())
```

## Command-line tool

Raspberry Pi only.

| Command | What it does |
|---|---|
| `ups-hat status` | One-off report (the default). |
| `ups-hat watch [secs]` | Live report, refreshed every `secs` seconds (default 2). |
| `ups-hat json` | One snapshot as JSON. |
| `ups-hat faults` | List every fault code. |
| `ups-hat registers` | Dump the charger registers. |
| `ups-hat pd` | USB-C PD configuration and contract. |
| `ups-hat poweroff [low]` | Shutdown hook: Ship mode, reset or nothing. |

| Environment variable | Default | Meaning |
|---|---|---|
| `UPS_HAT_CELLS_PARALLEL` | `1` | `1` for a DUAL pack (2 cells), `2` for a QUAD pack (4 cells). |
| `UPS_HAT_CELL_MAH` | `3000` | Rated capacity of one cell. |
| `UPS_HAT_STATE` | `/var/lib/ups-hat/state.json` | File for learned battery data. |
