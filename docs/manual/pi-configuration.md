# Raspberry Pi configuration

These steps assume Raspberry Pi OS Bookworm or later. Run the commands in a terminal on the Pi.

1. Update the system.

    ```bash
    sudo apt update && sudo apt full-upgrade -y
    ```

2. Add the UPS HAT+ software repository. This adds the repository's signing key and source, so the software updates with the rest of the system.

    ```bash
    curl -fsSL https://<repository-url>/install.sh | sudo bash
    ```

3. Install the software. The package enables I²C, installs the `ups-hat` service and its shutdown hook, and starts the service.

    ```bash
    sudo apt install ups-hat
    ```

4. Tell the software your pack type. This sets the charge current: 1.5 A for 2S1P, 2.0 A for 2S2P and larger.

    ```bash
    sudo ups-config --cells 2S1P
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
7. Check the board and the software. `i2cdetect -y 1` should list **28** and **6b**, and `systemctl status ups-hat` should show the service as active. If not, see [Troubleshooting](troubleshooting.md).

*The repository address and the package name `ups-hat` are provisional until the first software release.*
