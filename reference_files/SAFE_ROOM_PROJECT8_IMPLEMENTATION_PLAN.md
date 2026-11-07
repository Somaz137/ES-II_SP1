# SAFE-ROOM — Project 8 Implementation Plan and Current Status

**Date:** 7 November 2026  
**Project:** Case-study idea 8, *Room Environment Safety Monitor* (SAFE-ROOM).  
**Platform agreed with user:** Ubuntu **22.04** laptop + **ESP32** (USB serial) + BME680/environment camera concept.  
**Reference authority:** uploaded lecture manuals and VIGIL source ZIP **only**. See companion `SAFE_ROOM_MANUAL_REFERENCE.md` for version sources, hardware restrictions and exact PDF page pointers.

## Mandatory approval policy

- **Do not recommend or execute commands outside the uploaded manuals without asking the user first and waiting for approval.**
- **Never choose an unspecified library/board-core version yourself.** Ask first; missing Modules 4.2 and 4.3 are especially important.
- Do not install extra packages, change working versions, replace OpenCV distributions, run a new setup script, flash new firmware, create production services or expose a network dashboard without the corresponding decision and approval.
- If uncertain what the manual specifies, reopen the source PDF rather than guessing.
- Everything below is a **plan**, not authorization to implement an unspecified step.

## 1. Project goal and definition of done

Build a laptop-based environmental safety-monitoring demonstration that:

1. Acquires BME680 room measurements (temperature, humidity, pressure, air-quality information).
2. Uses a webcam to determine whether the room is occupied.
3. Lets a clinician/supervisor set **patient-specific** safe ranges via a form.
4. Detects a **sustained** excursion beyond those limits, avoiding transient false alarms.
5. Creates a readable caregiver alert indicating the condition and duration.
6. Persists measurements/alerts locally, with a **24-hour trend view**.
7. Keeps sensor monitoring and local safety decisions functioning even if remote notification is slow/unavailable.
8. Can be demonstrated/tested with safe, simulated situations rather than dangerous conditions.

*Source: Healthcare Case-Study Idea Book, pp. 21–22. Teaching prototype only — not a medical device.*

## 2. What is already complete (do not redo)

| Step | Status | Evidence |
|---|---|---|
| Ubuntu 22.04 laptop selected | **DONE / USER CONFIRMED** | User chose Ubuntu 22.04 + ESP32 |
| Python package/environment problem addressed | **DONE / USER CONFIRMED** | Initial generic `python3-venv` APT mismatch; manually documented `python3.10-venv` installation succeeded |
| Python 3 virtual environment created and activated | **DONE / USER CONFIRMED** | User reported venv works, environment named **`env`** |
| Python version | **DONE / USER CONFIRMED** | **3.10.12** |
| `requirements.txt` installed | **REPORTED INSTALLED** | User says installation succeeded; no individual version-import output yet |
| Arduino IDE 2.3.10 present | **UNKNOWN** | Not yet answered |
| ESP32 board attached/serial detected | **UNKNOWN** | No port output supplied |
| BME680 connected/reading | **NOT VERIFIED** | Missing driver/firmware specification |
| Camera detected/occupancy software | **NOT VERIFIED** | Need hardware/software decisions |
| Flask/SQLite dashboard, rule engine, tests | **NOT BUILT** | No SAFE-ROOM code implementation exists in course uploads |

**Exact six-item Python baseline assembled from manual versions:**

```text
numpy==1.26.4
opencv-python==4.11.0.86
pyserial==3.5
Flask==3.0.3
PyYAML==6.0.1
pytest==8.2.0
```

SQLite is part of Python 3.10; no separate pip package. This combined file is project-specific compilation of pins from Modules 3.2, 3.3, and 3.4/VIGIL, **not an official SAFE-ROOM lockfile**. Preserve it pending actual import checks.

## 3. Selected system layout

```text
      [BME680]                       [Webcam]
        | I²C                           | USB/V4L2/OpenCV
        v                               v
  [ESP32 DevKit] ---- USB serial ----> [Ubuntu laptop / Python 3.10]
                  115200 baud                 |
                                   +---------+-------------------+
                                   |         |                   |
                                [Rule &  [SQLite:             [Flask:
                               config]   history, alerts]       dashboard]
                                   |
                             [non-blocking alerts]
                                   |
                        [optional LED/buzzer via ESP32]
```

**Source-to-adaptation distinction:** Jetson is the device shown in Project 8. The laptop + ESP32 replacement follows Module 3.3's teaching method; the sensor protocol/driver is **not documented** in the uploaded set.

## 4. Stepwise implementation plan with approval gates

### Phase A — Verify Python environment (next immediate action)

**Goal:** Make sure already-installed packages are importable before proceeding to firmware or new code.

- Keep `env` activated.
- Use only the exact manual-documented version checks below:

  ```bash
  python3 --version
  python3 -c "import numpy as np; print('NumPy', np.__version__)"
  python3 -c "import cv2; print(cv2.__version__)"
  ```

- Expected based on manual/confirmed system: Python **3.10.12**, NumPy **1.26.4**, `cv2` **4.11.0**.
- The six requirements were reportedly installed. The installed versions of `serial`, Flask, PyYAML and pytest have not yet been individually verified; consult the manual-approved check method before adding extra commands.
- **Exit condition:** Import checks succeed; no unsupported package changes needed.

### Phase B — Establish ESP32 toolchain and USB serial

**Goal:** Verify Arduino IDE, actual board model and port before doing sensor integration.

1. Ask user: **Is Arduino IDE 2.3.10 already installed? Which ESP32 board is physically available?**
2. If not installed, follow Module 3.3 **pp. 4–6** exactly (IDE AppImage **2.3.10** and its manual-provided install steps).
3. Module 3.3 says install `esp32` by Espressif Systems in Boards Manager, but **does not pin a board-core version**. **STOP and ask user** before selecting/installing any core version.
4. Once connected, identify the actual serial port using the manual command:

   ```bash
   ls /dev/ttyUSB*
   ```

5. Module 3.3 **p. 5** documents (if required) `sudo usermod -a -G dialout $USER`, with **logout/login** to apply; user must approve before system changes.
6. The original `gpio_bridge.ino` serial protocol sends LED/SEG/BAR commands at **115200** and acknowledges with `OK`; its two-second host connection delay is documented on **p. 8**.
7. **Critical pin conflict:** the demo firmware drives **GPIO21 / GPIO22** as seven-segment/bar-LED outputs, whereas Module 3.3 **p. 4** reserves **GPIO21 SDA / GPIO22 SCL** for BME680 I²C. Never reuse demo bridge firmware **unchanged** when the BME680 is attached.
8. **Exit condition:** approved board core, known board/port, functional basic USB serial link.

### Phase C — Acquire BME680 sensor measurements

**Goal:** Read a real environmental record through ESP32 → USB → Python.

**Blocking missing information:** Project 8 references **Module 4.3**; Module 3.3 defers sensors to **Module 4.2**. Neither was uploaded. No course-prescribed Arduino BME680 library/version, initialization code, sensor sampling protocol or full wiring diagram is available.

**Required approvals/information before work:**
- Request the missing Module 4.2 and/or Module 4.3 first, if the user has them.
- Confirm the exact BME680 breakout model, supply requirements, I²C pin labels, actual ESP32 model.
- If the missing manuals remain unavailable, **ask user whether external manufacturer documentation and an unpinned Arduino sensor library may be used**. Explain the proposed choices **before commands or firmware edits**.

**Manual-provided electrical baseline:** 3.3 V GPIO; **GPIO21 SDA, GPIO22 SCL**; unplug before wiring; do not use 5 V on ESP32 GPIO. **Do not equate generic air-quality wording with an independently calibrated medical pollution measurement.**

**Exit condition:** stable time-stamped measurements, units and failure states demonstrated with physical sensor.

### Phase D — Validate webcam and choose occupancy algorithm

**Goal:** Produce a meaningful occupied/unoccupied status without using unsupported assumptions.

- Module 3.3 **pp. 14–16** teaches `cv2.VideoCapture(0)`, `cap.read()`, processing with OpenCV and cleanup with `cap.release()`.
- Module 3.3 **p. 20** describes motion detection with `cv2.absdiff` only as an exercise. **Stationary occupant detection is not specified.**
- Ask user/instructor whether occupancy should use a particular classroom technique or whether selecting a new method is authorized. Do not add MediaPipe solely because VIGIL uses it; the current six packages intentionally exclude MediaPipe.
- Define what to do when camera fails or occupancy cannot be determined; do not falsely classify a failure as an empty room.

**Exit condition:** tested occupancy behavior under representative conditions, subject to approved algorithm.

### Phase E — Safety rules and editable configuration

**Goal:** Implement explainable, testable patient-specific safety logic.

- Project 8 requires a **form** to edit safe limits per patient and a **sustained** period outside range.
- PyYAML **6.0.1** is already in requirements, justified by VIGIL's `config.yaml` approach.
- Keep configuration separate from safety evaluation; VIGIL's `alarm.py`/`test_safety.py` show separable, hardware-free logic as a pattern.
- **Do not copy VIGIL's `8`-frame debounce or `60`-second cooldown into SAFE-ROOM as mandatory values.** Those are for bed posture states, not air safety.
- **User/instructor must define:** safe limit values and units, whether pressure is just logged or alerted, duration of sustained breach, when a breach resets, how occupancy gates an alert, and recovery behavior.
- Project book's '10 minutes' alert is a **worked example**, not a prescribed global duration.

**Exit condition:** documented threshold definitions and tests for transient versus persistent excursions.

### Phase F — Local history and dashboard

**Goal:** Live display, patient settings form, 24h trends, event/alert history.

- Use **Flask==3.0.3** and Python standard-library `sqlite3` as documented in Module 3.4/VIGIL.
- Keep monitoring independent from the web server, following VIGIL's `monitor.py` vs `server.py` separation.
- Persist timestamped environmental data and alerts; chart **24-hour** history (explicit Project 8 requirement).
- Database schema, chart implementation, data retention and access controls are **not fixed** by the Project 8 source. Agree on these before implementing beyond source-described behavior.
- Prefer processing camera frames on-device; avoid storing/transmitting recognizable patient imagery, based on VIGIL's privacy design.

**Exit condition:** locally accessible, consistent dashboard; monitoring continues while dashboard is closed.

### Phase G — Non-blocking alert path, optional local alarm

**Goal:** Alert caregivers without delaying measurements or safety checks.

- Per Project 8 p. 21, delayed email/notification **must not block** the monitoring loop.
- Confirm the notification channel: dashboard-only, local buzzer/LED, email, or other. **Do not assume any service/provider or credentials.**
- If using ESP32 LED/buzzer, select pins without conflicting with I²C GPIO21/GPIO22; get approval for wiring/firmware modifications.
- Cloudflare Tunnel and `systemd` from Module 3.4 are VIGIL deployment examples, **not required Project 8 defaults**; do not enable without explicit approval.

**Exit condition:** simulated slow alert delivery does not stop monitoring; optional local signaling behaves as approved.

### Phase H — Safety tests and demonstration

**Goal:** Show the project meets the brief reproducibly.

- Use `pytest==8.2.0` from Module 3.4/VIGIL.
- Build tests (once approved/defined) for: brief threshold spike **no alert**, sustained breach **alert**, recovery, occupancy inactive/uncertain, serial sensor error/stale reading, dashboard failure, and slow/offline notification.
- Follow Module 3.4's pattern of testing pure safety logic without hardware. Do not run hazardous real-world experiments on vulnerable people.
- Demonstrate: actual sensor input, configurable limits, camera occupancy, local history/24h view and independent alert path.

**Exit condition:** all agreed tests pass, limitations documented, demonstration complete.

## 5. Dependencies already chosen versus decisions still blocked

| Topic | Status | Do not change without approval |
|---|---|---|
| Ubuntu 22.04 + Python 3.10.12 | **Fixed / confirmed** | OS and interpreter version |
| `env` virtual environment | **Fixed / confirmed** | Environment creation method |
| Six pinned Python requirements | **Installed per user** | Any wheel, version or new dependency |
| SQLite | **Built-in Python module** | Do not add separate pip package |
| Arduino IDE | **2.3.10 per manual**, status unknown | No IDE substitute/new version |
| ESP32 board-core | **No manual version** | User approval required before selection |
| BME680 driver/firmware | **Missing Module 4.2/4.3** | User approval required for any new library or code path |
| Camera/occupancy implementation | **Undecided** | No unapproved detection model or new vision package |
| Patient thresholds/time settings | **Undefined** | No clinical defaults invented |
| Notifications/remote access | **Undefined/optional** | No credentials/services/tunnels |
| Buzzer/LED | **Optional** | No conflicting ESP32 pin assignments |

## 6. Suggested source-controlled project structure (PROPOSED — not prescribed)

The book defines features but not a folder layout. **Do not create this structure without the user's approval**. It is a discussion aid illustrating the separation already present in VIGIL:

```text
SAFE-ROOM/
  requirements.txt             # user-installed six fixed package versions
  env/                         # already exists; do not commit to source control
  config.yaml                  # proposed patient-specific limits
  sensor_reader.py             # proposed host ESP32 serial interface
  occupancy.py                 # proposed webcam/person-presence interface
  rules.py                     # proposed sustained-breach safety logic
  monitor.py                   # proposed independent monitoring loop
  db.py                        # proposed SQLite persistence
  server.py                    # proposed Flask dashboard + config form
  templates/                   # proposed dashboard view
  tests/                       # proposed pytest cases
  firmware/                    # proposed ESP32 sensor firmware (requires approval)
```

These module names are an **organizational proposal** by the assistant, **not filenames or prescribed APIs from Project 8**. The user's approval policy applies before writing them.

## 7. What to ask the user next (minimum necessary)

**Immediate question:** Is **Arduino IDE 2.3.10** already installed, and which exact ESP32 board model do you have?

Then ask for the missing **Module 4.2/4.3** material, if available, before proposing a BME680 library or firmware. Do **not** select third-party versions from online documentation without approval.

Do not repeat already answered questions: target is Ubuntu 22.04 laptop + ESP32, Python is **3.10.12**, venv `env` works, and requirements file has been installed.

## 8. Companion reference and source basis

- Detailed extracted source instructions: **`SAFE_ROOM_MANUAL_REFERENCE.md`**.
- Assignment: `Healthcare_Case_Study_Idea_Book_Complete_1-18.pdf`, pp. 21–22.
- Python exact versions: `Module_3_2a_Python_Libraries_for_Jetson_Development_v1.0.pdf`, pp. 3–4, 35–36.
- ESP32/IDE/serial/camera: `Module_3_3a_Interfacing_with_Peripherals_ESP32_v1.0.pdf`, pp. 3–8, 14–20.
- venv and OS package guidance: `Module_2_2a_Package_Management_on_Jetson_v1.0.pdf`, pp. 8–10.
- Flask/SQLite/PyYAML/pytest and system architecture pattern: `Module_3.4_Healthcare_Case_Study_1_v0.8.pdf`, pp. 3–7 and 12–19; `vigil_v0.8.zip`.

**Status summary:** **Python environment is prepared; hardware and SAFE-ROOM code are not yet validated or implemented.** The next approved action is version verification and confirmation of the Arduino/ESP32 hardware state, not installing an unspecified BME680 library.
