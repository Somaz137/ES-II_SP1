# SAFE-ROOM — Project 8

Room Environment Safety Monitor for an Ubuntu 22.04 laptop and ESP32.

**Current scope:** dependency definitions, environment diagnostics, and an ESP32/BME680 serial test. The full monitoring application is not implemented. Hardware operation has not been verified.

## Start here

| File | Role |
|---|---|
| [Implementation plan](reference_files/SAFE_ROOM_PROJECT8_IMPLEMENTATION_PLAN.md) | Current progress, decisions, blockers, and next steps |
| [Manual reference](reference_files/SAFE_ROOM_MANUAL_REFERENCE.md) | Extracted course facts, source pages, version justification, and constraints |
| [requirements.txt](requirements.txt) | Executable Python package pins |

The original lecture PDFs and VIGIL ZIP are not included. The reference is an extraction, not a replacement for those source files.

## Existing code

| File | What it does |
|---|---|
| `firmware/safe_room_bme680.ino` | Experimental Adafruit BME680 reader; GPIO21/22 I2C, 115200-baud JSON records |
| `tools/read_sensor.py` | Prints JSON received from an explicitly selected serial port |
| `tools/check_setup.py` | Reports Python/package metadata, device paths, and serial group membership |
| `setup_ubuntu.sh` | Legacy starter installer; see warning below |
| `.gitignore` | Excludes environments, caches, editor metadata, and logs |

No rule engine, occupancy detector, database, patient settings form, dashboard, notification worker, or automated tests exist yet.

## Environment and setup policy

The recorded working environment is **`env`**, with Python **3.10.12** on Ubuntu **22.04**. Requirements installation was reported successful; individual import/version checks remain pending. See the implementation plan for the current verification steps.

**Do not run `setup_ubuntu.sh` as the default setup path.** It is retained as a legacy starter: it installs system packages, upgrades pip, and creates a separate `.venv`. Its procedure has not been reconciled with the manual-only policy or the existing environment.

Use the exact course-prescribed versions. Obtain approval before selecting unspecified libraries, versions, algorithms, or procedures. Do not repeat completed environment setup.

## Sensor test limitations

The firmware and reader use the same JSON format and baud rate. They are experimental code, not proof of a working hardware integration. The sketch depends on Adafruit's BME680 library, which is not specified by the available course materials. Neither an ESP32 core version nor a BME680 library version has been approved in the recorded plan.

Confirm the board, breakout, toolchain, and missing course instructions before installing dependencies or flashing. Electrical guidance and manual pin assignments are in the reference.

Gas resistance is raw ohms, not calibrated AQI, CO2, or CO. This is a teaching prototype; patient-specific safe limits have not been defined.
