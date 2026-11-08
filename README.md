# Room Environment Safety Control — Project 8

Room Environment Safety Monitor for an Ubuntu 22.04 laptop and ESP32.

**Current scope:** one room, one BME680 and one camera. Code includes dependency definitions, environment diagnostics, an experimental ESP32/BME680 serial test, and technical-alert configuration loading/validation. The full monitoring application is not implemented. Hardware operation has not been verified.

## Start here

**Returning to Linux?** Read the [Linux AI handoff](reference_files/LINUX_AI_HANDOFF.md) first. Testing is explicitly deferred to the existing Linux environment; it has not been completed on Windows.

| File | Role |
|---|---|
| [Implementation plan](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md) | Current progress, decisions, blockers, and next steps |
| [Manual reference](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md) | Extracted course facts, source pages, version justification, and constraints |
| [requirements.txt](requirements.txt) | Executable Python package pins |

The original lecture PDFs and VIGIL ZIP are not included. The reference is an extraction, not a replacement for those source files.

## Existing code

| File | What it does |
|---|---|
| `firmware/room_environment_safety_control_bme680.ino` | Experimental Adafruit BME680 reader; GPIO21/22 I2C, 115200-baud JSON records |
| `tools/read_sensor.py` | Prints JSON received from an explicitly selected serial port |
| `tools/check_setup.py` | Reports Python/package metadata, device paths, and serial group membership |
| `config/alerts.yaml` | Separate communication and sensor-error timeouts, initially 120 seconds each |
| `config_loader.py` | `load_alert_settings(path)` reads a validated YAML settings snapshot |
| `config_validation.py` | `validate_alert_settings(data)` checks both required positive, finite numeric durations |
| `tests/test_config.py` | Hardware-free configuration loading and validation tests |
| `setup_ubuntu.sh` | Legacy starter installer; see warning below |
| `.gitignore` | Excludes environments, caches, editor metadata, and logs |

No rule engine, occupancy detector, database, patient settings form, dashboard, or notification worker exists yet. Configuration tests are written; the full pytest run is pending the pinned environment.

## Technical alert settings

Edit `config/alerts.yaml` to set `communication_timeout_s` and `sensor_error_timeout_s`, in seconds. Both are required positive, finite numbers; booleans and numeric strings are invalid.

The future monitor should call the loader once during startup and keep its returned settings:

```python
from config_loader import load_alert_settings

settings = load_alert_settings("config/alerts.yaml")
```

The loader does not watch the file. Restart the monitor to apply technical-setting changes once startup integration is added. Patient-profile live updates are a separate future feature. This step does not implement timers or connect the loader to the experimental serial reader.

From the repository root, using the pinned project environment, run the full test suite with `python -m pytest`.

Verification so far: Python 3.10 grammar checks passed for the new modules/tests; a host-interpreter, standard-library-only validator smoke check passed one valid and 27 invalid inputs. PyYAML integration and the pytest suite have not run: the available Windows environments do not contain the approved dependency versions. No dependencies were installed or replaced.

## Environment and setup policy

The recorded working environment is **`env`**, with Python **3.10.12** on Ubuntu **22.04**. Requirements installation was reported successful; individual import/version checks remain pending. See the implementation plan for the current verification steps.

**Do not run `setup_ubuntu.sh` as the default setup path.** It is retained as a legacy starter: it installs system packages, upgrades pip, and creates a separate `.venv`. Its procedure has not been reconciled with the manual-only policy or the existing environment.

Use the exact course-prescribed versions. Obtain approval before selecting unspecified libraries, versions, algorithms, or procedures. Do not repeat completed environment setup.

## Sensor test limitations

The firmware and reader use the same JSON format and baud rate. They are experimental code, not proof of a working hardware integration. The sketch depends on Adafruit's BME680 library, which is not specified by the available course materials. Neither an ESP32 core version nor a BME680 library version has been approved in the recorded plan.

Confirm the board, breakout, toolchain, and missing course instructions before installing dependencies or flashing. Electrical guidance and manual pin assignments are in the reference.

Gas resistance is raw ohms, not calibrated AQI, CO2, or CO. This is a teaching prototype; patient-specific safe limits have not been defined.

## VIGIL reference and project-specific decisions

See [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for the verified manual-backed differences and authorized code-reuse scope. The current project name is **Room Environment Safety Control**; the repository remains `ES-II_SP1`.

