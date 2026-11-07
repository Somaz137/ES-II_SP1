# SAFE-ROOM — Implementation Plan and Current Status

**Updated:** 7 November 2026  
**Project:** Idea 8, Room Environment Safety Monitor.  
**Platform:** Ubuntu 22.04 laptop + ESP32 over USB serial.

This file owns current progress and decisions. The [manual reference](SAFE_ROOM_MANUAL_REFERENCE.md) owns course facts and source citations. The [README](../README.md) is the short entry point; [requirements.txt](../requirements.txt) owns executable Python pins.

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

- `firmware/safe_room_bme680.ino` uses Adafruit BME680, GPIO21 SDA/GPIO22 SCL, addresses 0x76 then 0x77, and JSON at 115200 baud approximately once per second.
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

- User requested VibeWise for this project and Impeccable when building the dashboard.
- At the latest availability check, neither was exposed among available tools/skills; VibeWise plugin search returned no match.
- Recheck availability before relevant work. Do not claim either was used unless it was actually loaded.

## Next information needed

1. Whether Arduino IDE 2.3.10 is installed; exact ESP32 and BME680 breakout models.
2. Whether Modules 4.2/4.3 can be supplied.
3. Environment verification output from the existing `env`.

## Source pointers

- Assignment: Idea Book pp. 21–22.
- Python pins/checks: Module 3.2 pp. 3–4, 35–36.
- ESP32/IDE/serial/camera: Module 3.3 pp. 3–8, 14–20.
- Environment: Module 2.2 pp. 8–10.
- Flask/SQLite/configuration/testing architecture: Module 3.4 and VIGIL ZIP.
- Full extraction: [manual reference](SAFE_ROOM_MANUAL_REFERENCE.md). Original PDFs/ZIP are absent from this repository.
