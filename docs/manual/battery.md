# Battery requirements

The battery is the UPS Pack board with your own cells, or a ready-made 2S pack that has its own protection. The HAT itself has no cell protection. The cells must meet every item below.

- Cell type: 18650 lithium-ion (3.6–3.7 V nominal, 4.2 V fully charged), unprotected, flat or button top. Protected cells are usually too long for the holders, and the pack board provides the protection. Do not use LiFePO4 (3.2 V) cells; the board would over-charge them.
- Number: two cells for the DUAL pack (2S1P), four for the QUAD (2S2P).
- Matched cells: every cell must be the same make, model, capacity and age, charged to the same voltage (within 0.1 V) before fitting.
- Discharge rating: at least 5 A continuous per cell for the DUAL, or at least 3 A per cell for the QUAD, for the full 5 A output. Check that this is the continuous rating, not the peak. Lower-rated cells still work but limit the DUAL's output: 2.6 A cells give about 2.7 A at 5 V, enough for a Pi 5 without power-hungry USB devices. For USB drives or an SSD, use the QUAD pack. Recommended cell: Samsung INR18650-25R or 25RM (2,500 mAh, 20 A continuous).
- Other packs: any 2S lithium-ion pack (8.4 V full) with a built-in protection circuit and an XT30 plug wired + to +. Set the pack type with ups-config so the charge current suits it.

**Pack configurations**

Adding cells in parallel increases runtime and shares the load current between cells. At the full 5 A output the pack supplies up to about 4.7 A, so the DUAL pack needs high-drain cells.

| Pack | Example cells | Capacity | Usable energy (8.2 V charge) | Current per cell at 5 A output | Runtime at 6 W (Pi 5, typical) | Runtime at 15 W (heavy load) | Charge current and time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DUAL (2S1P) | 2 × 18650, 3,000 mAh | 3.0 Ah | about 19.5 Wh | 4.7 A (use cells rated 10 A or more) | about 2.7 h | about 1.1 h | 1.5 A, about 2.5 h |
| QUAD (2S2P) | 4 × 18650, 3,000 mAh | 6.0 Ah | about 39 Wh | 2.4 A | about 5.5 h | about 2.2 h | 2.0 A, about 3.5 h |

Usable energy assumes the software's 8.2 V charge voltage, which stores about 10 % less than charging to 8.4 V but roughly doubles cell life. Runtimes assume 85 % conversion efficiency and end at the 5 % shutdown point. The software charges at 1.5 A for 2S1P and 2.0 A for 2S2P; tell it your pack type with ups-config (see [Software](software.md)).

**Runtime.** Runtime depends on pack capacity and the Pi's load. As a guide, divide the pack energy by the load power and allow about 85 % for conversion losses:

**Runtime (h) ≈ 7.2 V × capacity (Ah) × 0.85 ÷ Pi load (W)**

For example, a 3,000 mAh pack (21.6 Wh) running a Raspberry Pi 5 that draws 6 W lasts about 2.7 hours when charged to 8.2 V. The software shuts the Pi down before the pack is fully discharged, so the usable runtime is slightly shorter.
