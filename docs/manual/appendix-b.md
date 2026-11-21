# Appendix B: UPS HAT+ technical information

A one-page summary of the UPS HAT+ ratings. Ranges are worst case over component tolerances; the typical value is in the notes. [Appendix A](appendix-a.md) gives the full electrical characteristics and their test conditions.

| Parameter | Value or range | Notes |
| --- | --- | --- |
| Input connector | USB-C, power only | No data connection to the Pi |
| Adapter required | USB PD, 9 V or 15 V at 3 A (27 W or more) | 15 V at 3 A (45 W) for full output while charging; see [Power sources](power-sources.md) |
| Input voltage | 4.75–15.75 V | Negotiated 5 V, 9 V or 15 V contract |
| Maximum continuous input voltage | 16 V | Input surge diode conducts above this |
| Input current limit | 2.72–2.92 A | 2.82 A typical |
| Output voltage, no load | 5.06–5.34 V | 5.20 V typical |
| Output voltage at the header, 5 A | 5.16 V typical | After the back-feed blocking switch (estimate) |
| Continuous output current | 0–5.0 A | 25.5 W at 5.1 V |
| Output current limit | 7–10 A | Converter peak switch current 8–11 A |
| Output turn-on voltage (battery only) | 5.78–6.50 V | 6.14 V typical, pack voltage rising |
| Output turn-off voltage (battery only) | 5.14–5.95 V | 5.59 V typical (about 2.8 V per cell), pack voltage falling |
| Software low-battery shutdown | 5 % charge or 6.2 V under load | Whichever comes first, with the ups-hat service running |
| System voltage on the adapter, pack flat or removed | 7.12–7.32 V | Always above the turn-on voltage, so the Pi starts without a battery |
| Switchover to battery | No interruption | 5 V stays above 4.90 V in production test |
| Battery | 2S lithium-ion, 6.0–8.4 V | UPS Pack DUAL or QUAD, or any protected 2S pack with an XT30 plug |
| Battery connector | XT30 male, vertical (J3) | Pad 1 −, pad 2 + |
| Charge voltage | 8.18–8.25 V | 8.20 V (4.10 V per cell) with the service running; 8.38–8.45 V before it first runs |
| Charge current | 1.41–1.65 A (2S1P); 1.87–2.16 A (2S2P) | 0.95–1.08 A before the service first runs |
| Converter switching frequency | 400–560 kHz | 480 kHz typical, fixed |
| Charger switching frequency | 750 kHz | Typical |
| Battery drain, ship mode (board off) | 20 µA maximum | 11 µA typical (estimate) |
| Battery drain, running with no load | 3 mA typical | Output on, Pi disconnected, 5 V LED lit (estimate) |
| Operating ambient temperature | 0–45 °C | Board, pack and Pi; the Raspberry Pi 5 itself is rated to 50 °C |
| Charging ambient temperature | 0–45 °C | Not enforced by the board; keep the cells within this range |
| Storage temperature, board only | −20 to 60 °C | In its anti-static bag |
| Converter thermal shutdown | 160–175 °C die | 10 °C hysteresis |
| Charger thermal regulation / shutdown | 120 °C / 150 °C die | Charge current is reduced above 120 °C |
| I²C addresses | 0x6B charger, 0x28 USB-C controller | I2C1, header pins 3 and 5; bus at 3.3 V, 100–400 kHz |
| HAT+ ID EEPROM | 0x50 on the ID bus | Header pins 27 and 28 |
| ESD rating, USB-C CC and data pins | 22 kV | Protection diode rating (IEC 61000-4-2); board not yet tested |
| Board size | 85 × 56 mm | Raspberry Pi HAT+ outline |
| Mounting | 4 × M2.5, 16 mm female/female standoffs | 15–16 mm spacing per the HAT+ specification |
