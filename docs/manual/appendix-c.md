# Appendix C: UPS Pack technical information

A one-page summary of the UPS Pack board ratings, for both variants. Ranges are worst case where the design gives one; the typical value is in the notes. Figures marked † are calculated and still to be confirmed on production packs.

| Parameter | Value or range | Notes |
| --- | --- | --- |
| Variants | DUAL: 2S1P, 2 × 18650. QUAD: 2S2P, 4 × 18650 | One electronics design, two board sizes |
| Cells | Unprotected 18650 lithium-ion (NMC or NCA), flat or button top, rated 5 A or more continuous | Not LiFePO4: the HAT would over-charge them. Use matched cells of one type and age |
| Pack voltage | 5.6–8.4 V | 7.2 V nominal; the HAT uses 6.0–8.4 V |
| Capacity | DUAL: one cell's capacity. QUAD: two cells' capacity | For example 3000 mAh cells: DUAL 3.0 Ah (≈ 21.6 Wh), QUAD 6.0 Ah (≈ 43 Wh) |
| Output connector | XT30 female plug on an 18 AWG lead | Mates with the HAT's J3 |
| Continuous discharge current | 0–5 A | About 4.5 A at the HAT's full output and lowest pack voltage † |
| Cell over-charge cut-off | 4.25 V per cell | Charging stops |
| Cell over-discharge cut-off | 2.80 V per cell | Output stops; the pack stays off until a charger is connected |
| Discharge over-current cut-off | About 8–19 A † | Sensed across the protection MOSFETs; short circuit cut off within 150–400 µs |
| Charge over-current cut-off | About 10–17 A † |  |
| Fuse | 10 A, fast-acting | In the positive lead, at the cells |
| Balancing | On above 4.20 V per cell, off below 4.19 V | Bleeds about 15 mA (DUAL) or 35 mA (QUAD) per cell † |
| Temperature cut-off | 57.8–61.0 °C | 59.4 °C typical, cells rising; whole pack switches off |
| Temperature release | 54.2–57.2 °C | 55.7 °C typical, cells falling |
| Cold-charging limit | None | Do not charge below 0 °C |
| Self-drain, switch OFF | About 30 µA on the HAT, 250 µA on its own † | Use OFF for storage and transport |
| Self-drain, switch ON | About 0.50 mA (DUAL), 0.56 mA (QUAD) † | Temperature monitor running |
| Operating ambient temperature | 0–45 °C | Discharging, on the HAT |
| Charging ambient temperature | 0–45 °C |  |
| Storage temperature | −20 to 45 °C for up to a month | 10–25 °C for long-term storage, switch OFF |
| Board size | DUAL 135 × 49 mm; QUAD 135 × 97 mm | Through-hole cell holders, 75.5 × 21 mm each |

**Sources**

- [TI BQ25798 datasheet, SLUSDV2C](https://www.ti.com/document-viewer/BQ25798/datasheet): electrical characteristics and PROG defaults
- [TI TPS54620 datasheet, SLVS949](https://www.ti.com/product/TPS54620): reference, EN/UVLO, current-limit, frequency and thermal limits
- HYCON HY2120 datasheet (DS-HY2120-V15): pack protector thresholds, delays and power-down behaviour
- Board values (dividers, balancing, temperature cut-off, drain, ship-mode test limit): UPS HAT+ Rev D netlist, UPS Pack Rev B design notes and the QA test procedure
