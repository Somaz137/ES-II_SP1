# Room Environment Safety Control — Implementation Plan and Current Status

**Updated:** 8 November 2026  
**Project:** Idea 8, Room Environment Safety Monitor.  
**Platform:** Ubuntu 22.04 laptop + ESP32 over USB serial.

This file owns current progress and decisions. The [manual reference](ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md) owns course facts and source citations. The [README](../README.md) is the short entry point; [requirements.txt](../requirements.txt) owns executable Python pins.

## Operating constraints

- Follow the uploaded manuals and user-approved decisions. Ask before introducing unspecified commands, dependencies, versions, algorithms, or implementation choices.
- Do not redo completed setup or replace the working `env`.
- Do not run the legacy `setup_ubuntu.sh` automatically: it creates `.venv`, installs system packages, and upgrades pip.
- Missing Modules 4.2/4.3 leave the BME680 driver and sensor procedure unspecified. Existing experimental code does not establish approval.
- Obtain the relevant decision before system changes, firmware flashing, services, or remote exposure.
- This is an educational prototype. Do not invent patient limits or claim clinical safety.

## Current status

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
| Automated tests | None present |

## Existing sensor test

- `firmware/room_environment_safety_control_bme680.ino` uses Adafruit BME680, GPIO21 SDA/GPIO22 SCL, addresses 0x76 then 0x77, and JSON at 115200 baud approximately once per second.
- `tools/read_sensor.py` prints parsed records. It does not store data, validate measurement fields, reconnect after USB loss, or apply safety rules.
- Firmware does not retry initialization after a sensor is missing at boot.
- Adafruit library choice, sampling settings, and JSON schema are starter adaptations, not prescribed by the available manuals.
- Earlier README proposals of ESP32 core 3.3.12 and Adafruit BME680 2.0.6 were external, unapproved suggestions. They are not selected dependencies.

## Implementation sequence

### A — Verify the existing environment

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
- Use VIGIL as a reference and reuse appropriate code snippets after inspecting them. Do not transfer its posture logic, defaults, dependencies, or deployment unchanged. See [comparison](VIGIL_COMPARISON.md).

## Confirmed fault-monitoring design

- Store communication and sensor-error timeouts in a separate YAML file; both are initially 120 seconds. Filename, exact keys, validation and loading/reloading policy await agreement.
- Track last recognized ESP32 communication separately from last successful measurement. A recognized sensor-error message resets the communication timer but does not make measurements fresh.
- After 120 seconds without recognized communication, raise a communication alert while the application continues running. Display last successful measurement time.
- Communication alerts require acknowledgment even when messages resume. If acknowledged while communication is still missing, dismiss the alert and wait another 120 seconds; alert again if communication is still missing. Acknowledgment does not modify actual last-contact or last-measurement times.
- A sensor-error episode begins on a sensor-error message. Further error messages do not restart its timer. Persistent errors trigger a separate alert after 120 seconds.
- A valid measurement resets the sensor-error waiting period and automatically clears that alert. Sensor-error recovery does not remove the separate communication-alert acknowledgment requirement.
- Track the start of the current sensor-error episode as well as last communication and last successful measurement.
- Startup, recognized/valid message criteria, clock mechanism and mixed silence/error episodes remain unresolved. No fault-monitoring application code has been implemented or approved for implementation yet.

## Next information needed

1. Whether Arduino IDE 2.3.10 is installed; exact ESP32 and BME680 breakout models.
2. Whether Modules 4.2/4.3 can be supplied.
3. Environment verification output from the existing `env`, when the user returns to Ubuntu; do not block current Windows design work on it.
4. Whether YAML changes apply on restart or during monitoring (pending learner decision).

## Source pointers

- Assignment: Idea Book pp. 21–22.
- Python pins/checks: Module 3.2 pp. 3–4, 35–36.
- ESP32/IDE/serial/camera: Module 3.3 pp. 3–8, 14–20.
- Environment: Module 2.2 pp. 8–10.
- Flask/SQLite/configuration/testing architecture: Module 3.4 and VIGIL ZIP.
- Full extraction: [manual reference](ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md). Original PDFs/ZIP are absent from this repository.
