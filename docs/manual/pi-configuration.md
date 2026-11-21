# Raspberry Pi configuration

These steps assume Raspberry Pi OS Bookworm or later. Run the commands in a terminal on the Pi.

1. Enable I²C. Run `sudo raspi-config` and choose Interface Options → I2C, or add this line to `/boot/firmware/config.txt`:

    ```
    dtparam=i2c_arm=on
    ```

2. Download the software and install the `ups_hat` library. This also installs the `ups-hat` command.

    ```bash
    sudo apt install -y git python3-pip
    git clone https://github.com/PinGoblin/UPS_HAT
    cd UPS_HAT
    sudo pip install --break-system-packages .
    ```

3. Install the `ups-hat` service and its shutdown hook. The service watches the battery and shuts the Pi down when it runs low. The hook switches the board off at the end of a power-off on battery.

    ```bash
    sudo mkdir -p /usr/local/lib/ups-hat
    sudo cp -r examples /usr/local/lib/ups-hat/
    sudo cp examples/systemd/ups-hat.service /etc/systemd/system/
    sudo cp examples/systemd/ups-hat-shutdown /usr/lib/systemd/system-shutdown/
    sudo chmod +x /usr/lib/systemd/system-shutdown/ups-hat-shutdown
    ```

4. Tell the software your pack type. Open the service file with `sudo nano /etc/systemd/system/ups-hat.service` and set these lines:

    ```
    Environment=UPS_HAT_CELLS_PARALLEL=1
    Environment=UPS_HAT_CELL_MAH=3000
    ```

    `UPS_HAT_CELLS_PARALLEL` is `1` for the DUAL pack (2S1P, charged at 1.5 A) and `2` for the QUAD pack or a larger third-party pack (2S2P, charged at 2.0 A). `UPS_HAT_CELL_MAH` is the capacity of one cell. Then start the service:

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable --now ups-hat
    ```

5. Raspberry Pi 5 only: allow full USB current. The Pi 5 may not detect a 5 A supply through the GPIO header, so by default it limits USB peripherals to 600 mA and may show a low-power warning. Add this line to `/boot/firmware/config.txt`:

    ```
    usb_max_current_enable=1
    ```

    Then run `sudo rpi-eeprom-config --edit` and add this line:

    ```
    PSU_MAX_CURRENT=5000
    ```

6. Reboot with `sudo reboot`.
7. Check the board and the software. `i2cdetect -y 1` should list **28** and **6b**, `ups-hat status` should print a report with no critical faults, and `systemctl status ups-hat` should show the service as active. If not, see [Troubleshooting](troubleshooting.md).

The [UPS HAT+ API](../api/index.md) section has more detail on the library, the service and the shutdown hook, and on using the board from MicroPython boards.
