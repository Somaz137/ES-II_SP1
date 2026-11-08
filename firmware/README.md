# DOIT ESP32 DevKit V1 BSEC firmware

This source prepares BSEC low-power acquisition every three seconds.
It does not establish a working hardware integration.
No firmware build, test, installation or flashing occurred on Windows.

## Before compilation on Linux

1. Use the DOIT ESP32 DevKit V1 with the classic ESP32 chip.
2. Select **DOIT ESP32 DEVKIT V1** in Arduino IDE 2.3.10.
3. Check the installed firmware libraries and ESP32 core version.
4. Select the actual USB serial port.

The user confirmed a 3.3 V sensor supply on 8 November 2026.
ROOM_BME680_SUPPLY_MV therefore defaults to 3300 in bsec_board_config.h.
The header rejects supply values other than 1800 and 3300.
Breakout VIN and the BME680 supply can differ.
Check this setting again if you change the sensor breakout.

## Board configuration

| Setting | Value |
|---|---|
| Arduino board | DOIT ESP32 DEVKIT V1 |
| Arduino board identifier | esp32:esp32:esp32doit-devkit-v1 |
| Sensor SDA | GPIO21 |
| Sensor SCL | GPIO22 |
| Serial speed | 115200 baud |
| Sensor supply | 3.3 V, confirmed by the user |
| BSEC sampling | Low-power mode, one acquisition every three seconds |

Connect sensor SDA to GPIO21 and sensor SCL to GPIO22.
Connect the sensor ground to the board ground.
Use the breakout documentation to identify its power terminal.
The header stores the pins and serial speed as named constants.
The sketch uses those constants during startup.
The header rejects compilation for C3, S2, S3, and other chip types.
It checks the selected chip type, not the physical board.
Select the DOIT board explicitly in the IDE.
Recompile the sketch for this board before uploading.

Bosch BSEC2 includes a binary for the classic ESP32 chip.
Bosch BME68x reads the sensor and is required by BSEC2.
Wire comes with the Espressif ESP32 Arduino core.
Python requirements.txt does not install these firmware libraries.
The exact core and library versions still require agreement and a Linux build check.

Python receives the same JSON records at the same serial speed.
Its parser, fault rules, and gas readiness rules need no change for this board.
Select the actual device path when you start the laptop monitor.
Opening the port can reset the board. Check this behavior on Linux.

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
- bsec_board_config.h contains the chip check, pins, serial speed, supply selection, and reporting intervals.
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
- Compile for DOIT ESP32 DEVKIT V1 with the approved Arduino setup and the 3300 supply setting.
- Check that a C3 target fails with the board-selection message.
- Check that an invalid supply value fails with the supply-selection message.
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
