# Installation

You will need four M2.5 standoffs with screws, a USB-C PD adapter that offers 9 V or 15 V at 3 A, and the UPS Pack board with its cells (see [Battery requirements](battery.md)).

1. Shut down the Raspberry Pi and unplug all power, including its own USB-C supply.
2. If you use the Active Cooler or a heatsink, fit it to the Pi first.
3. Screw the four M2.5 standoffs to the Pi's mounting holes.
4. Line up the board's 40-pin header with the Pi's GPIO pins and press it down evenly until it sits on the standoffs. Check that no pins are offset by one row or column.
5. Fix the board to the standoffs with the four screws.
6. Prepare the pack. With its switch OFF, measure each cell and keep them within 0.1 V of each other. Fit the cells following the + marks: BT1 (and BT3) first, then BT2 (and BT4).
7. Switch the pack ON and plug its XT30 lead into J3.
8. Connect the USB-C adapter to J1. The PWR LED lights, the Pi starts, and the CHG LED lights while the cells charge. A newly fitted pack gives no output until the HAT has had USB-C power once, so the first start must be on the adapter.
9. Continue with [Raspberry Pi configuration](pi-configuration.md).

Do not connect a power supply to the Pi's own USB-C port; the board supplies everything the Pi needs. If one is connected by mistake, the board's back-feed blocker stops it driving current into the board.

To start the board from battery alone (no adapter), press SW1 briefly.
