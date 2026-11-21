# Appendix A: Electrical characteristics

These limits apply to the Rev D board over 0–45 °C ambient unless the Conditions column says otherwise; typical values are at 25 °C with an 8.0 V pack. Minimum and maximum values combine the component datasheet limits with the board's 1 % resistor values. Values marked † are design estimates that will be replaced by measured values after Rev D characterisation.

## A.1 USB-C input

| Parameter | Conditions | Min | Typ | Max | Unit |
| --- | --- | --- | --- | --- | --- |
| Input voltage (VBUS) | Negotiated USB-C PD contract: 5 V, 9 V or 15 V, each up to 3 A | 4.75 | 5 / 9 / 15 | 15.75 | V |
| Maximum continuous VBUS | Above this the input surge diode starts to conduct |  |  | 16 | V |
| Input current limit | 3 A setting, 9 V input | 2.72 | 2.82 | 2.92 | A |
| Charger start-up voltage | VBUS rising | 3.3 | 3.4 | 3.5 | V |
| Weak-adapter detection | VBUS falling under a 12 mA test load | 3.3 | 3.4 | 3.5 | V |
| Charger switching frequency |  |  | 750 |  | kHz |

## A.2 Battery charger

| Parameter | Conditions | Min | Typ | Max | Unit |
| --- | --- | --- | --- | --- | --- |
| Charge voltage, software setting | `ups-hat` service running (4.10 V per cell) | 8.18 | 8.20 | 8.25 | V |
| Charge voltage, hardware default | Before the service first runs, or after the cells are removed | 8.38 | 8.40 | 8.45 | V |
| Charge current, 2S1P setting | Any input voltage | 1.41 | 1.50 | 1.65 | A |
| Charge current, 2S2P setting | Any input voltage | 1.87 | 2.00 | 2.16 | A |
| Charge current, hardware default | Before the service first runs | 0.95 | 1.00 | 1.08 | A |
| Recharge threshold | Pack voltage below charge voltage |  | 200 |  | mV |
| Minimum system voltage | Adapter connected, pack flat or absent | 7.12 | 7.2 | 7.32 | V |
| Charger battery over-voltage stop | Percentage of charge voltage, rising | 103 | 104 | 105 | % |
| Charger thermal regulation | Charger die temperature; charge current is reduced above this |  | 120 |  | °C |
| Charger thermal shutdown | Charger die temperature |  | 150 |  | °C |

Charge current is reduced automatically when the input current limit is reached, so the Raspberry Pi's load always takes priority over charging.

## A.3 Battery pack board (UPS Pack Rev A)

| Parameter | Conditions | Min | Typ | Max | Unit |
| --- | --- | --- | --- | --- | --- |
| Pack voltage range | 2S lithium-ion | 6.0 | 7.2 | 8.4 | V |
| Cell over-charge cut-off (charging stops) | Per cell |  | 4.23 |  | V |
| Cell over-discharge cut-off (output stops) | Per cell |  | 2.70 |  | V |
| Discharge over-current cut-off † | 25 mV across the 3 mΩ sense resistor |  | 8.3 |  | A |
| Second over-current level † | 50 mV across the sense resistor |  | 16.7 |  | A |
| Short-circuit cut-off † | 100 mV across the sense resistor |  | 33 |  | A |
| Charge over-current cut-off † | −15 mV across the sense resistor |  | 5 |  | A |
| Balancing turns on | Per cell, rising |  | 4.20 |  | V |
| Balancing turns off | Per cell, falling |  | 4.19 |  | V |
| Balancing current † | Per cell at 4.2 V: DUAL (270 Ω) / QUAD (120 Ω) |  | 15 / 35 |  | mA |
| Temperature cut-off | NTC between the cells, rising | 57.8 | 59.4 | 61.0 | °C |
| Temperature release | NTC between the cells, falling | 54.2 | 55.7 | 57.2 | °C |
| Pack fuse | F1, fast-acting |  | 10 |  | A |
| Battery current at full output † | 5 A output, 6.0 V pack |  | 4.7 |  | A |

The pack also refuses to charge a cell discharged to near 0 V. Detection delays and threshold tolerances are in the ABLIC S-82B2A datasheet. On the QUAD the temperature limits widen slightly, to 57.7–61.1 °C.

## A.4 5 V output (header pins 2 and 4)

| Parameter | Conditions | Min | Typ | Max | Unit |
| --- | --- | --- | --- | --- | --- |
| Output voltage | No load, any input or battery voltage | 5.06 | 5.20 | 5.34 | V |
| Output voltage at header † | 5 A load, after the back-feed blocking switch |  | 5.16 |  | V |
| Continuous output current |  |  |  | 5.0 | A |
| Output current limit | Converter peak switch current; the output current is about 1 A lower and the output voltage falls | 8 |  | 11 | A |
| Output switches on (battery only) † | SYS rising |  | 6.14 | 6.50 | V |
| Output switches off (battery only) † | SYS falling, about 2.8 V per cell | 5.14 | 5.59 |  | V |
| Software low-battery shutdown | Remaining charge |  | 5 |  | % |
| Software shutdown voltage floor | Pack voltage under load |  | 6.2 |  | V |
| Soft-start time | Output enable to 5.1 V |  | 3.5 |  | ms |
| Converter switching frequency | Fixed, set by a 100 kΩ RT resistor | 400 | 480 | 560 | kHz |
| Converter thermal shutdown | Converter die temperature, 10 °C hysteresis | 160 |  | 175 | °C |

The output switch-on and switch-off limits include the converter's enable-threshold tolerance and the 1 % divider resistors. On the adapter the charger holds the system rail at 7.12 V or more, even with the pack flat or removed, so the output always starts. Current cannot flow back into the board from the header 5 V pins, so a Raspberry Pi running from its own supply cannot back-feed the board's 5 V output.

## A.5 Battery drain

| Parameter | Conditions | Min | Typ | Max | Unit |
| --- | --- | --- | --- | --- | --- |
| HAT in ship mode (board off) | 8 V pack, Pi off; maximum is the production test limit |  | 11 † | 20 | µA |
| Pack board, switch OFF † | Protector and balancers only |  | 20 |  | µA |
| Pack board, switch ON † | Temperature monitor running: DUAL / QUAD |  | 0.50 / 0.56 |  | mA |
| HAT running, no load † | Output on, Pi disconnected, includes the 5 V LED |  | 3 |  | mA |

With the HAT in ship mode and the pack switched OFF, a 3,000 mAh pack loses under 1 % of its charge per month. With the pack switched ON, its temperature monitor adds about 12 mAh a day, so switch the pack off for storage.

## A.6 Interfaces and environment

| Parameter | Conditions | Min | Typ | Max | Unit |
| --- | --- | --- | --- | --- | --- |
| I²C bus voltage | Pi I2C1 (pins 3 and 5), pull-ups on the Pi |  | 3.3 |  | V |
| I²C clock frequency |  |  | 100 | 400 | kHz |
| ID EEPROM supply | Pi 3.3 V rail (pins 1 and 17) |  | 3.3 |  | V |
| ESD rating, USB-C CC and data pins | Protection diode rating (IEC 61000-4-2); board not yet tested |  |  | 22 | kV |
| Charging ambient temperature | Cells; the board has no temperature sensor | 0 |  | 45 | °C |
| Operating ambient temperature | Board, pack and Pi running, on the adapter or on battery | 0 |  | 45 | °C |
| Storage temperature | Board only, in its anti-static bag | −20 |  | 60 | °C |
| Battery storage temperature | Cells, under a month (10–25 °C for long-term storage) | −20 |  | 45 | °C |

Not yet listed: efficiency, output ripple and load-step response. These will be added from Rev D bench measurements.
