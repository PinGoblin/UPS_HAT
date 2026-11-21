# Power sources

**The USB-C adapter must support USB Power Delivery (PD) at 9 V or 15 V, 3 A (27 W or more).** A 15 V, 3 A (45 W) adapter is needed to run the Pi at its full 5 A and charge the pack at the same time. The Pi's 5.1 V supply is the same from every source; the source only sets how much power the Pi can draw.

**On the adapter.** Power the adapter cannot cover is drawn from the pack, if it is connected and charged.

| Adapter (USB-C contract) | Input current limit (A) | Power for the Pi from the adapter (W) | Pi current at 5.1 V (A) | Result |
| --- | --- | --- | --- | --- |
| 15 V, 3 A PD (45 W) | 2.8 | 25.5 (output limit) | 5.0 | Full load, with about 12 W left to charge the pack |
| 9 V, 3 A PD (27 W) | 2.8 | ≈ 22 | ≈ 4.3 | Covers normal Pi 5 use. Above 22 W the pack makes up the difference and slowly discharges |
| 5 V, 3 A (PD or USB-C 3 A) | 2.8 | ≈ 11 | ≈ 2.2 | Not supported. Runs a lightly loaded Pi; heavier loads drain the pack |
| 5 V, USB-C 1.5 A | 1.5 | ≈ 6 | ≈ 1.2 | Not supported. Most loads drain the pack |
| 5 V, no current advertised (plain USB) | 0.5 | ≈ 2 | ≈ 0.4 | Not supported. The Pi runs from the pack until it is flat |

With the pack flat, switched off or tripped, nothing makes up a shortfall: if the Pi draws more than the adapter's figure, the 5.1 V output switches off. The software warns when the adapter offers less than 9 V, or when the pack is discharging on mains.

**On battery.** With no adapter, the Pi has the full 25.5 W (5 A) at every pack voltage down to the software shutdown. Pack current rises as the pack voltage falls.

| Pack state | Pack voltage (V) | Power for the Pi (W) | Pack current at 5 A out (A) | Current per cell, DUAL / QUAD (A) |
| --- | --- | --- | --- | --- |
| Full (4.10 V per cell) | 8.2 | 25.5 | ≈ 3.4 | 3.4 / 1.7 |
| Nominal (3.7 V per cell) | 7.4 | 25.5 | ≈ 3.7 | 3.7 / 1.9 |
| Low (3.3 V per cell) | 6.6 | 25.5 | ≈ 4.2 | 4.2 / 2.1 |
| Software shutdown floor (3.1 V per cell) | 6.2 | 25.5 | ≈ 4.5 | 4.5 / 2.3 |

At a typical 8 W Pi 5 load the pack supplies about 1.1–1.5 A. Every figure stays below the pack's 8.3 A overcurrent trip; cells must be rated for at least 5 A continuous.

*Figures are calculated, not yet measured. They assume about 93–95 % charger efficiency and about 92 % from the system rail to the Pi header.*
