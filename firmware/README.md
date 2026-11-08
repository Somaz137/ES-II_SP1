# ESP32 BSEC firmware

This source prepares BSEC low-power acquisition every three seconds.
It does not establish a working hardware integration.
No firmware build, test, installation or flashing occurred on Windows.

## Before compilation on Linux

1. Check the actual ESP32 board and sensor breakout.
2. Agree on exact firmware dependencies and ESP32 core versions.
3. Check the BME680 supply voltage from board documentation or measurement.
4. Set ROOM_BME680_SUPPLY_MV in bsec_board_config.h to 1800 or 3300.

The initial value zero deliberately stops compilation.
Breakout VIN and the BME680 supply can differ.
The source includes the matching Bosch three-second, four-day-history configuration.
Four days describes baseline history, not a required warm-up wait.

## Dependency references

| Component | Inspected candidate | Approval and verification |
|---|---|---|
| Bosch BSEC2 wrapper | 1.10.2610, algorithm 2.6.1.0 | Source reference only. Exact installation requires agreement. |
| Bosch BME68x wrapper | v1.3.40408 | Source reference only. Exact installation requires agreement. |
| ESP32 board core | Not selected | Check installed version and compatibility. |
| Arduino IDE | Course version 2.3.10 | Preserve this requirement. |

This change uses the existing Python dependencies.
The sketch no longer uses the Adafruit BME680 library.
This change does not authorize removing an installed library.
Bosch distributes algorithm binaries and configuration under its own license.
Use the upstream distribution rather than copying those files into this repository.

## Source organization

- room_environment_safety_control_bme680.ino handles BSEC setup, callbacks, and errors.
- bsec_board_config.h contains the explicit supply selection and reporting intervals.
- bsec_serial_format.h converts scalar values and status fields to JSON.
- tests/test_bsec_serial_format.cpp checks the formatter without a sensor or Arduino library.

## Serial behavior

The sketch uses 115200 baud and I2C SDA21/SCL22.
It tries address 0x76 and then 0x77.
BSEC controls acquisition timing through BSEC_SAMPLE_RATE_LP.
The loop calls BSEC frequently without a three-second delay.
Only a new callback produces a reading record.

Each reading includes temp_c, humidity_pct, pressure_hpa, and gas_ohms.
The bsec object includes stabilization_status, run_in_status, and iaq_accuracy.
Missing status fields appear as null.
Python treats incomplete status information as unknown.
The example in [bsec_reading.json](../tests/fixtures/bsec_reading.json) describes the format.
It is a fixture, not observed hardware output.

Expected BSEC warm-up flags do not prevent valid raw readings.
Invalid conversions and failures produce recognized error records.
Continuous failure reports errors at most once every three seconds.
Two missing sample periods trigger reporting when BSEC returns without measurements.
Python still applies its separate 120-second fault rules.
Initialization failures continue reporting until intervention or restart.
Automatic sensor reinitialization and calibration-state storage remain future work.

## Pressure contract

The inspected wrapper converts pressure to hPa before the application callback.
The sketch therefore sends callback pressure without another division by 100.
Generic BSEC output documentation describes pressure in Pa.
Check this version-sensitive behavior before using another wrapper release.
Check real pressure units independently before accepting hardware results.

## Deferred verification

- Build and execute the portable formatter test using an available Linux C++11 toolchain.
- Execute the full Python suite in the existing approved environment.
- Compile the sketch with the approved Arduino setup and checked supply configuration.
- Check three-second fresh output and correct measurement units.
- Check that startup, missing-data and read failures continue recognized error reporting.
- Check reported warm-up transitions without a host countdown.
- Check whether opening the laptop serial port resets this board.
- Check callback status extraction, missing fields, and timestamp matching.
- Check the six-second measurement watchdog and three-second error reporting interval.
- Check reporting behavior across the millisecond counter rollover.

No dashboard, occupancy logic, environmental thresholds, or state persistence exists in this sketch.

## Upstream references

- [BSEC2 API source](https://github.com/boschsensortec/Bosch-BSEC2-Library/tree/1.10.2610)
- [BME68x wrapper source](https://github.com/boschsensortec/Bosch-BME68x-Library/tree/v1.3.40408)
- [Adafruit BSEC guide](https://learn.adafruit.com/adafruit-bme680-humidity-temperature-barometic-pressure-voc-gas/bsec-air-quality-library)
