# Specifications

| Parameter | Value |
| --- | --- |
| Input connector | USB-C (power only) |
| Input voltage | 5 V, 9 V or 15 V (USB-C PD), up to 3 A; 9 V or 15 V at 3 A required (see [Power sources](power-sources.md)) |
| Input current limit | Set by the software from the adapter: 3 A, 1.5 A or 0.5 A; hardware limit 2.82 A typical |
| Battery | UPS Pack Rev A: DUAL (2 × 18650, 2S1P) or QUAD (4 × 18650, 2S2P); or any protected 2S lithium-ion pack with an XT30 plug |
| Battery connector | XT30: J3 on the HAT (male, vertical); the pack has an XT30 female plug on an 18 AWG lead |
| Battery voltage range | 6.0–8.4 V (7.2 V nominal) |
| Charge current | 1.5 A (2S1P) or 2.0 A (2S2P), set by the software; 1 A before the software first runs |
| Charge voltage | 8.2 V (4.1 V per cell) set by the software; 8.4 V (4.2 V per cell) before the software first runs |
| Cell over-charge / over-discharge protection | 4.23 V / 2.70 V per cell (pack board) |
| Pack over-current cut-off | 8.3 A discharge (short circuit 33 A), 5 A charge; 10 A fuse (pack board) |
| Cell balancing | Automatic above 4.20 V per cell: about 15 mA (DUAL) or 35 mA (QUAD) |
| Temperature cut-off | Pack switches off above about 60 °C, back on below about 56 °C; no cold-charging limit |
| Output voltage | 5.1 V (measured at the header) |
| Continuous output current | 5 A |
| Output current limit | About 7–10 A (converter peak switch current 8–11 A) |
| Low-battery output cut-off | Software shutdown at 5 % remaining charge; hardware output cut-off at 5.6 V pack (≈ 2.8 V/cell), on again above 6.1 V |
| I²C bus (to Pi) | I2C1, header pins 3 (SDA) and 5 (SCL) |
| I²C addresses | 0x6B battery charger and monitor, 0x28 USB-C PD controller |
| HAT+ ID EEPROM | 0x50 on the ID bus (pins 27/28) |
| Form factor | HAT: Raspberry Pi HAT+, full Pi size (85 × 56 mm). Pack board: DUAL 135 × 49 mm, QUAD 135 × 97 mm |
