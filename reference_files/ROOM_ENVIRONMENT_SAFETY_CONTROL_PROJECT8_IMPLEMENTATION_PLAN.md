# Room Environment Safety Control — Implementation Plan and Current Status

**Updated:** 8 November 2026  
**Project:** Idea 8, Room Environment Safety Monitor.  
**Platform:** Ubuntu 22.04 laptop + ESP32 over USB serial.

**Current prototype scope:** one room, one BME680 and one camera. Earlier multi-room expansion and Jetson migration proposals are deferred.

This file owns current progress and decisions. The [manual reference](ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md) owns course facts and source citations. The [README](../README.md) is the short entry point; [requirements.txt](../requirements.txt) owns executable Python pins.

## Operating constraints

- Follow the uploaded manuals and user-approved decisions. Ask before introducing unspecified commands, dependencies, versions, algorithms, or implementation choices.
- Do not redo completed setup or replace the working `env`.
- The legacy `setup_ubuntu.sh` was removed at the user's request; preserve the existing approved environment.
- Missing Modules 4.2/4.3 leave the BME680 driver and sensor procedure unspecified. Existing experimental code does not establish approval.
- Obtain the relevant decision before system changes, firmware flashing, services, or remote exposure.
- This is an educational prototype. Do not invent patient limits or claim clinical safety.

## Current status

**Linux continuation:** Follow [LINUX_AI_HANDOFF.md](LINUX_AI_HANDOFF.md) for the current branch, environment checks, configuration test command, remaining milestones and cleanup assessment. The user explicitly deferred all remaining testing to their Linux setup. No Windows environment or alternate Windows interpreter is selected.

| Area | Evidence and state |
|---|---|
| Ubuntu/Python | User previously confirmed Ubuntu 22.04 and Python 3.10.12 |
| Virtual environment | User confirmed working `env` |
| Requirements | User reported successful installation; individual import/version verification pending |
| Diagnostics | `tools/check_setup.py` exists; checks distribution metadata, not package imports; mismatches print CHECK without causing failure |
| Arduino IDE | Manual specifies 2.3.10; installation status unknown |
| ESP32 and port | Actual board, board-core version, and working serial connection unconfirmed |
| BME680 | Experimental sketch and Python reader exist; dependency approval, compilation, wiring, and physical readings unverified |
| Webcam/occupancy | Not implemented; method and failure behavior undecided |
| Rules and configuration form | Not implemented; patient limits and timing undefined |
| SQLite and dashboard | Not implemented |
| Notifications/local alarm | Not implemented; channel and optional wiring undefined |
| Technical alert settings | Implemented as `config/alerts.yaml`, `config_loader.py`, and `config_validation.py`; startup-only loading, not yet connected to the sensor reader |
| Communication-fault tracker | `communication_fault.py` implements initialization, recognized-message receipt, periodic evaluation and acknowledgment; takes supplied times and is not connected to serial/UI yet |
| Sensor-fault tracker | `sensor_fault.py` accumulates error time, pauses on communication timeout, resumes the remaining wait and auto-clears on valid measurements; not connected to serial/UI yet |
| Serial parser / validator | `serial_parser.py` and `measurement_validation.py` classify decoded lines and check four finite numeric fields; no hardware, tracker mutation or committed-reading storage yet |
| Automated tests | All five test files (configuration, communication, sensor, measurement validation, serial parser) written; all remaining test execution deferred to Linux; pinned-environment pytest run and real PyYAML integration remain pending. Limited validator smoke and Python 3.10 grammar checks passed on the available Windows host |

## Selected execution intervals

These are design decisions, not an implemented monitoring loop.

| Operation | Selected interval | Current control/status |
|---|---|---|
| BME680 acquisition | Approximately 1 second | Existing experimental ESP32 firmware timing; actual hardware rate unverified |
| Camera occupancy processing | 60 seconds | Latest learner choice; supersedes the earlier 5-second proposal; Python scheduling not implemented |
| Fault evaluation | 5 seconds | Selected for future Python monitoring loop |
| Dashboard refresh | 10 seconds | Selected for future dashboard |

The future Python-side technical settings should load at startup. The camera processing interval does not select a capture frame rate or buffering policy; those remain open. Occupancy may reflect the previous observation until the next one-minute processing check. When five-second fault evaluation is integrated, timeout detection occurs on the next check, potentially almost five seconds after the duration expires plus scheduling/processing delay.

## Future side note — ESP32 sampling configuration (deferred)

The learner explicitly declined adding ESP32 startup configuration now and requested that the idea be kept for later.

Possible later extension: read a desired acquisition interval from laptop YAML and send it to the ESP32 over USB serial at startup, with agreed firmware handling and confirmation. No command format, firmware implementation, dependency version, or automatic action is selected or authorized by this note.

For the current prototype, leave the ESP32's approximately one-second acquisition timing in its firmware. Do not add a YAML field that appears to control actual acquisition without implementing the ESP32 path; changing Python read/poll delays would not change the sensor's firmware sampling interval. This defers actual YAML-to-ESP32 interval control, rather than implementing a misleading host-only setting.

## Existing sensor test

- `firmware/room_environment_safety_control_bme680.ino` uses Adafruit BME680, GPIO21 SDA/GPIO22 SCL, addresses 0x76 then 0x77, and JSON at 115200 baud approximately once per second.
- `tools/read_sensor.py` prints parsed records. It does not store data, validate measurement fields, reconnect after USB loss, or apply safety rules.
- Firmware does not retry initialization after a sensor is missing at boot.
- Adafruit library choice, sampling settings, and JSON schema are starter adaptations, not prescribed by the available manuals.
- Earlier README proposals of ESP32 core 3.3.12 and Adafruit BME680 2.0.6 were external, unapproved suggestions. They are not selected dependencies.

## Implementation sequence

### A - Verify the existing environment

The user is currently on Windows and authorized an isolated environment in `C:\Users\User\OneDrive\Desktop\ES-II_SP1`. That folder is outside this session's writable roots; do not install there until it is writable. Available Windows interpreters do not match the recorded Python 3.10.12 environment. Python.org provides no Windows installer for 3.10.12; do not substitute another version without user agreement. Keep the existing Ubuntu environment unchanged and defer its checks until available.

Inside the existing activated `env`, the manual documents:

```bash
python3 --version
python3 -c "import numpy as np; print('NumPy', np.__version__)"
python3 -c "import cv2; print(cv2.__version__)"
```

Expected: Python 3.10.12, NumPy 1.26.4, and cv2 4.11.0. Other package verification remains pending. Do not interpret metadata-only diagnostics as successful imports.

### B — Confirm toolchain and serial

Confirm Arduino IDE 2.3.10, the physical ESP32 board, and actual port. The manual gives no ESP32 core version: ask before selecting one. Follow the reference's serial-access procedure only when needed and approved.

### C — Validate BME680 input

Request Modules 4.2/4.3 if available. Otherwise obtain approval for external manufacturer guidance, the sensor library/version, and the existing test design. Confirm the exact breakout and wiring before flashing. Exit only after real readings, units, and failure records are demonstrated.

### D — Establish occupancy

Use the manual's OpenCV camera guidance. Agree on a detection method and handling of camera failure, uncertainty, and stationary occupants. Motion alone is not a reliable occupancy decision. Do not add a vision library without approval.

### E — Define and implement rules

Agree on patient limits/units, monitored metrics, sustained duration, reset/recovery behavior, occupancy gating, and any cooldown. The book's ten-minute example is not a default. Use editable configuration and a form as required by the brief.

### F — Add persistence and dashboard

Use the pinned Flask dependency and standard-library SQLite. Keep monitoring independent from the dashboard, following the VIGIL architectural pattern. Agree on schema, retention, chart approach, and configuration access before implementation. Required outputs: live values, patient settings, 24-hour trends, and alert/event history.

### G — Add independent alerts

Agree on the notification channel and offline behavior. Slow delivery must not stop sampling or local decisions. Optional ESP32 LED/buzzer wiring must avoid GPIO21/22. Do not enable tunnels or services by default.

### H — Verify and demonstrate

Use the pinned pytest dependency for hardware-free rule tests. Cover short spikes, sustained breaches, recovery, absent/uncertain occupancy, missing/stale sensor data, and delayed/offline notifications. Demonstrate real input and agreed dashboard behavior separately.

## Project workflow preferences

- Current name: **Room Environment Safety Control**, selected by the user on 8 November 2026. The repository name remains ES-II_SP1.
- Use VibeWise learning mode, Impeccable for dashboard design, and the requested GitHub, Superpowers, Computer, Browser, and Plugin Management capabilities where relevant. VibeWise's local learning skill has been read and is active; Impeccable is available.
- Develop from Windows for now; Ubuntu runtime checks are deferred. Requirements installation and specified versions are user-reported, not independently verified.
- Keep distinct responsibilities in small Python modules with focused functions; related helpers may share a module. A small main program connects components.
- Use VIGIL as a reference and reuse appropriate code snippets after inspecting them. The original local source was inspected on 8 November 2026; the comparison now records source-backed behavior and concrete reuse limitations. Do not transfer its posture logic, defaults, dependencies, or deployment unchanged. See [comparison](VIGIL_COMPARISON.md).

## Confirmed fault-monitoring design

- Store timeouts in `config/alerts.yaml` under `communication_timeout_s` and `sensor_error_timeout_s`, both initially 120 seconds. The loader validates a mapping with both finite, positive numeric values, rejecting bools and numeric strings. Technical settings load at startup initially; patient profiles will update while monitoring continues. Live patient-profile behavior remains a later feature.
- Track last recognized ESP32 communication separately from last successful measurement. A recognized sensor-error message resets the communication timer but does not make measurements fresh.
- After 120 seconds without recognized communication, raise a communication alert while the application continues running. Display last successful measurement time.
- Communication alerts require acknowledgment even when messages resume. If acknowledged while communication is still missing, dismiss the alert and wait another 120 seconds; alert again if communication is still missing. Acknowledgment does not modify actual last-contact or last-measurement times.
- A sensor-error episode begins on a sensor-error message. Further error messages do not restart its timer. Persistent errors trigger a separate alert after 120 seconds.
- A valid measurement resets the sensor-error waiting period and automatically clears that alert. Sensor-error recovery does not remove the separate communication-alert acknowledgment requirement.
- Track the start of the current sensor-error episode as well as last communication and last successful measurement.
- Technical configuration, both pure fault trackers, serial classification and finite-field measurement validation are implemented; tests are written but execution is deferred to Linux. Recognized reading/error types, incomplete-field treatment and ignored input are selected. Actual committed-reading retention/routing, runtime clock/scheduling, persistence/history and hardware integration remain future work.
- Implementation details: immutable snapshots; timeout equality uses >=; late communication preserves its elapsed fault before recording recovery; no-op acknowledgments do not extend waits. Sensor pauses begin when timeout status is supplied, not retroactively. Existing sensor alerts remain until a valid reading; an error with no remaining wait alerts on resume. These details are explicit in the designs and deferred tests.

## Selected serial-input handling

- Type=reading requires temp_c, humidity_pct, pressure_hpa and gas_ohms as finite numeric values, excluding bools/numeric strings. Missing/unusable values produce incomplete_reading with no partial values to commit.
- Incomplete readings preserve the last complete committed snapshot and original timestamp at the future consumer, indicate incomplete current input immediately, and start/continue the existing sensor-error episode without restarting it. Explicit type=error is sensor_error and also contains no committable measurements.
- Decoder failures, non-object JSON and missing/unknown record types are ignored. They do not reset communication time or directly change sensor-error state; scheduled fault checks continue.
- Only valid_reading carries replacement measurements. Patient/physical range limits are not introduced by structural validation. Parser is stateless and not wired into the experimental reader yet.
- After every checkpoint response, compare verified VIGIL behavior. It has no BME680 serial parser; distinguish architectural analogy from a direct equivalent.

## Next information needed

1. Whether Arduino IDE 2.3.10 is installed; exact ESP32 and BME680 breakout models.
2. Whether Modules 4.2/4.3 can be supplied.
3. Environment verification output from the existing `env`, when the user returns to Ubuntu; do not block current Windows design work on it.
4. Technical YAML loading is decided: startup-only initially. Patient-profile live updates are selected as a future feature; their validation and effect on environmental breach timers still need agreement.

## Source pointers

- Assignment: Idea Book pp. 21–22.
- Python pins/checks: Module 3.2 pp. 3–4, 35–36.
- ESP32/IDE/serial/camera: Module 3.3 pp. 3–8, 14–20.
- Environment: Module 2.2 pp. 8–10.
- Flask/SQLite/configuration/testing architecture: Module 3.4 and VIGIL ZIP.
- Full extraction: [manual reference](ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md). Original PDFs/ZIP are absent from this repository.




