# Room Environment Safety Control — Project 8

Room Environment Safety Monitor for an Ubuntu 22.04 laptop and ESP32.

**Current scope:** one room, one BME680 and one camera. Code includes dependency definitions, environment diagnostics, an experimental ESP32/BME680 serial test, technical-alert configuration loading/validation, pure communication/sensor-fault tracking, and serial-message classification/measurement validation. The full monitoring application is not implemented. Hardware operation has not been verified.

## Start here

**For people:** Read [README_HUMAN.md](README_HUMAN.md) for the project purpose, data flow, alert behavior, gas warm-up decision and remaining work.

PRs #1 through #5 are merged into main. Gas warm-up handling is approved as a design and remains unimplemented. See the [approved design](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md#approved-gas-readiness-design).

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
| `communication_fault.py` | Startup/message timeout tracking and acknowledgment/re-alert logic, with caller-supplied time |
| `tests/test_communication_fault.py` | Deferred Linux scenarios for startup, recovery, acknowledgment and timeout boundaries |
| `sensor_fault.py` | Persistent sensor-error timing, communication-driven pause/resume and valid-measurement recovery |
| `tests/test_sensor_fault.py` | Deferred sensor scenarios, including use of the real communication-state module |
| `measurement_validation.py` | Requires the four measurement fields as finite numeric values; no safety thresholds |
| `serial_parser.py` | Classifies decoded lines; only valid readings carry committable measurements |
| `tests/test_measurement_validation.py`, `tests/test_serial_parser.py` | Deferred validation and real JSON classification cases |
| `.gitignore` | Excludes environments, caches, editor metadata, and logs |

No rule engine, occupancy detector, database, patient settings form, dashboard, or notification worker exists yet. Configuration, fault-tracker, measurement-validation and serial-parser tests are written; all remaining test execution is deferred to the pinned Linux environment.

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

## Communication-fault state

`communication_fault.py` provides `create_communication_state`, `record_communication_message`, `evaluate_communication_fault`, and `acknowledge_communication_fault`. Each returns an immutable state snapshot; callers must retain the returned state.

Use `communication_timeout_s` from the loaded settings. The normal initial wait begins at startup. Recognized reading/error messages reset contact timing; restored communication leaves an outstanding alert awaiting acknowledgment. Acknowledging during an outage starts another full wait without changing the real last-contact time.

`timed_out` and `alert_active` are separate: the first describes missing communication, the second can remain latched after recovery. Supplied times must be finite and nondecreasing within one clock domain. Equality triggers the timeout; a late message is evaluated against preceding silence before being recorded. Acknowledgment with no outstanding alert does not extend a wait.

The future monitor must evaluate periodically even when no serial data arrives. Serial classification is now implemented separately below; runtime clock choice, committed-reading state, history and serial integration remain future work. The separate sensor-error module below is now implemented. Tests are written but not executed, per the user's Linux deferral.

## Sensor-fault state

`sensor_fault.py` provides `create_sensor_state`, `record_sensor_error`, `record_valid_measurement`, and `evaluate_sensor_fault`. Use `sensor_error_timeout_s` from the loaded settings and retain the returned immutable states.

Explicit error messages start or continue an episode; repeated errors do not reset it. A valid measurement resets the timer and automatically clears its alert. Errors and pauses preserve the last-valid-measurement timestamp.

Pass `communication.timed_out` to periodic sensor evaluation, not `communication.alert_active`. Active error time accumulates until a pause is reported, stays unchanged while paused, and resumes when communication returns. Acknowledgment alone does not resume it. Existing sensor alerts stay until a valid measurement; no new sensor alert is raised while paused. If the full wait accumulated before a pause, an error on resume alerts immediately; a valid measurement clears/reset instead.

The module does not choose a real clock, read serial ports, or mutate the communication tracker. Callers must update both trackers for recognized messages and evaluate periodically during silence. Tests are written but not executed; run the full suite on Linux as described in the handoff.

## Serial classification and measurement validation

`parse_serial_line(line)` in `serial_parser.py` returns `valid_reading`, `sensor_error`, `incomplete_reading` or `ignored`. It accepts decoded text, uses the starter firmware's JSON types and calls `validate_measurements(data)` from `measurement_validation.py`.

Valid readings require finite numeric `temp_c`, `humidity_pct`, `pressure_hpa` and `gas_ohms`; bools and numeric strings are invalid. Patient safety limits are not checked here. Only a valid result contains a complete dictionary of committable values. Incomplete/error/ignored results contain no partial replacement data.

The next consumer must retain old measurements and their original timestamp on incomplete readings, expose incomplete status immediately, and count them as sensor errors. Unreadable/non-object/unknown input is ignored without resetting communication timing. This stateless layer does not yet update trackers, store readings, read ports or display a dashboard. All its tests await Linux execution.

## Selected monitoring intervals

Planned intervals are camera occupancy processing every **60 seconds**, fault evaluation every **5 seconds**, and dashboard refresh every **10 seconds**. The experimental ESP32 keeps its approximately **1-second** sensor-acquisition timing. These Python cadences are recorded decisions; camera/monitor/dashboard scheduling is not implemented yet.

ESP32 startup configuration is deferred as a [future side note](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md#future-side-note--esp32-sampling-configuration-deferred). Laptop YAML does not currently control the ESP32 sampling rate.

## Environment and setup policy

The recorded working environment is **`env`**, with Python **3.10.12** on Ubuntu **22.04**. Requirements installation was reported successful; individual import/version checks remain pending. See the implementation plan for the current verification steps.

The legacy `setup_ubuntu.sh` was removed at the user's request. Continue using the existing approved environment; do not recreate that installer.

Use the exact course-prescribed versions. Obtain approval before selecting unspecified libraries, versions, algorithms, or procedures. Do not repeat completed environment setup.

## Sensor test limitations

The firmware and reader use the same JSON format and baud rate. They are experimental code, not proof of a working hardware integration. The sketch depends on Adafruit's BME680 library, which is not specified by the available course materials. Neither an ESP32 core version nor a BME680 library version has been approved in the recorded plan.

Confirm the board, breakout, toolchain, and missing course instructions before installing dependencies or flashing. Electrical guidance and manual pin assignments are in the reference.

Gas resistance is raw ohms, not calibrated AQI, CO2, or CO. This is a teaching prototype; patient-specific safe limits have not been defined.

## VIGIL reference and project-specific decisions

See [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for the verified manual-backed differences and authorized code-reuse scope. The current project name is **Room Environment Safety Control**; the repository remains `ES-II_SP1`.




