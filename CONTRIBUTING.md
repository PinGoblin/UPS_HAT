# Contributing

These notes are for working on the library. The customer documentation is in `docs/` and is published by CI to <https://pingoblin.github.io/UPS_HAT/>: Edit it there, push, and let CI build the site.

## Testing

The library is tested without hardware. `tests/sim.py` simulates the BQ25798 charger and the STUSB4500 USB-C controller at register level, and the tests drive those simulators.

### Running the tests

**pytest (recommended):**

```sh
pip install -r requirements-test.txt     # pytest, coverage, hypothesis
python -m pytest
```

With branch coverage:

```sh
python -m coverage run -m pytest
python -m coverage report                # fails below 95 %
python -m coverage html                  # htmlcov/index.html
```

**Standard library only:**

No packages needed; runs on CPython 3.8 or later:

```sh
python -m unittest discover -s tests
```

The property tests then run with a seeded random sampler instead of Hypothesis.

**MicroPython:**

The end-to-end scenarios run unchanged under MicroPython:

```sh
micropython tests/scenarios.py
```

Warnings are errors under pytest (`filterwarnings = error` in `pyproject.toml`), so an unclosed file or a deprecated call fails the run.

### What is tested

| File | Covers |
|---|---|
| `test_compat.py` | The CPython/MicroPython layer: signed values, clamping, clocks, and the MicroPython code paths. |
| `test_bus.py` | `I2CDevice` register and bit-field helpers, error wrapping, `LinuxI2C` (with `/dev/i2c-N` mocked) and `open_bus`. |
| `test_faults.py` | Every catalogue entry is well formed, has advice when needed, and is raised by `board.py`; `Fault` formatting; the fault codes page is up to date. |
| `test_battery.py` | The OCV table, coulomb counting, rest correction, capacity learning, resistance tracking and the state file round trip. |
| `test_bq25798.py` | Every charger setting: round trip, step rounding and clamping; every on/off setting changes exactly one bit; status, fault and flag decoding; ADC decoding; ship-FET control. |
| `test_stusb4500.py` | PDO and contract decoding, status and events, sink PDO editing, NVM read, write, time-out and encoding. |
| `test_board.py` | The `UPS` class: missing and returning chips, configuration and repair after a charger reset, power-off decisions, USB-C PD, **every fault rule** (raised after its debounce time and cleared again), callbacks, the state file, I²C errors in the middle of a poll, and the report. |
| `test_pimon.py` | Raspberry Pi 5 monitoring with `vcgencmd` mocked: throttle bits, `EXT5V_V`, non-Pi systems and time-outs. |
| `test_cli.py` | Every `ups-hat` command and its environment variables. |
| `test_packaging.py` | One version everywhere; the MicroPython file list; a matching `.pyi` stub and an API page for every module; no CPython-only imports or syntax in the modules MicroPython installs. |
| `test_properties.py` | Invariants for any input (Hypothesis): register fields, setting ranges, NVM encoding, the battery model's bounds, and a fuzz test that `poll()` never raises whatever the chips report. |
| `test_scenarios.py` | Runs each end-to-end scenario in `scenarios.py` as its own test. |
| `test_examples.py` | Every `Example:` in the docstrings runs on the simulator, and every script in `examples/` runs with `--mock`. |

Time-based fault rules use a simulated clock (`tests/helpers.py`), so a rule that needs a condition to hold for two minutes is tested in milliseconds.

### In CI

Every pull request runs:

- the suite on CPython 3.10, 3.12 and 3.13 with coverage and Hypothesis, and on 3.8 with the standard library only;
- `mypy` and `stubtest` on the type stubs;
- the scenarios under MicroPython, plus the RAM measurements below.

The coverage report appears in the job summary, and the HTML report is attached to the run as `coverage-html`.

### MicroPython RAM figures

The free-RAM figures on the [MicroPython notes](https://pingoblin.github.io/UPS_HAT/api/guide/micropython/) page are measured by the `micropython` CI job on the unix port of MicroPython 1.25 (`tools/mp_mem.py`, `tools/mp_heap.sh`): Import the library, create a `UPS` on the register simulator and poll it twice. The 32-bit build stands in for RP2040, RP2350 and ESP32 boards. The job summary of every pull request shows the latest figures; update the page if they change.

### Examples

Every example in `examples/` runs without hardware with `--mock`, using the register simulator in `tests/sim.py`. `tests/test_examples.py` runs each one that way.

## Releases

Set the new version in `pyproject.toml`, `ups_hat/__init__.py` and `micropython/package.json`, check them with `python3 tools/check_packaging.py v1.5.0`, then push a tag such as `v1.5.0`. GitHub builds the `.mpy` files and publishes a release with `ups_hat-mpy-1.5.0.zip` attached.

## Fault codes page

`docs/api/faults.md` is generated from `ups_hat/faults.py`. After changing the catalogue, run `python3 tools/gen_faults_md.py`; `tests/test_faults.py` fails if the page is out of date.
