# Installation

## Python (e.g. Pi)

    1. Enable I²C: `sudo raspi-config` → Interface Options → I2C. Alternatively, add `dtparam=i2c_arm=on` to `/boot/firmware/config.txt`.
    2. Install the library straight from GitHub:

        ```sh
        sudo pip install git+https://github.com/PinGoblin/UPS_HAT   # add --break-system-packages on Bookworm
        ups-hat status                                              # or: python3 -m ups_hat.cli status
        ```

        To install a particular release, add its tag: `git+https://github.com/PinGoblin/UPS_HAT@v1.4.0`. From a downloaded copy of the repository, use `sudo pip install .` instead.

    The library opens `/dev/i2c-1` by itself. Run it as root, or add your user to the `i2c` group.

## MicroPython (e.g. ESP32)

Copy the `ups_hat` folder to the board:

    ```sh
    mpremote cp -r ups_hat :
    ```

    The board then loads the files without compiling them, which needs much less RAM. `README.txt` in the zip shows the `.mpy` version the files were built for; it must match your firmware.

    **Source files with `mip`.** Installs the `.py` files from GitHub into `/lib` on the board:

    ```sh
    mpremote mip install github:PinGoblin/UPS_HAT/micropython            # latest
    mpremote mip install github:PinGoblin/UPS_HAT/micropython@v1.4.0     # a release
    ```

    The board compiles these when you import them, which needs extra RAM: see [MicroPython notes](micropython.md) for how much.

    Then, for example on a Raspberry Pi Pico:

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
| `ups-hat poweroff [low]` | systemd-shutdown hook: ship mode, reset or nothing. |

The tool reads `UPS_HAT_CELLS_PARALLEL` (default `1`), `UPS_HAT_CELL_MAH` (default `3000`) and `UPS_HAT_STATE` (default `/var/lib/ups-hat/state.json`) from the environment.
