# Room Environment Safety Control — Implementation Plan and Current Status

> **Historical (15–19 November 2026).** Current state: [README.md](../README.md) and [reference_files/LINUX_VERIFICATION_2026-11-25.md](LINUX_VERIFICATION_2026-11-25.md).

**Linux checks recorded:** See the [8 November verification record](LINUX_VERIFICATION_2026-11-08.md).
The user completed Python test execution, firmware formatting, compilation, and the listed virtual-serial scenarios.
Physical ESP32 and BME680 operation remains unverified.
The successful Linux build used ESP32 core 3.3.12, Bosch BSEC2 1.10.2610, and Bosch BME68x 1.3.40408.
This record supersedes earlier pending-test statements in historical preparation notes and design checklists.

**Software checks recorded on 15 November 2026:** See the [15 November verification record](LINUX_VERIFICATION_2026-11-15.md). Branch `feature/sharp-dust-integration` reported 317 passed. The software demo ran. No hardware was used.

**Board change, 15 November 2026:** The ESP32-S3 (N8R2 module) supersedes the DOIT ESP32 DevKit V1. See [Decisions - 15 November 2026](#decisions---15-november-2026). Ported and compiled on branch `feature/esp32-s3-port` (15 November 2026).

**Board identity and first flash, 17 November 2026:** esptool shows the connected board is an N16R8-type module (16 MB quad flash, 8 MB embedded PSRAM, CH343 USB-UART bridge), not an N8R2. The firmware was flashed with `esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default`. The serial link and the alarm protocol were checked without sensors. See the [17 November verification record](LINUX_VERIFICATION_2026-11-17.md).


**Online access, 19 November 2026:** Opt-in view-only online access is implemented: a Cloudflare quick tunnel to a second, view-only origin, with a password for controls. One real tunnel run on 19 November 2026 loaded the pages and refused control requests without sign-in. On 20 November 2026 a signed-in user saved patient limits, silenced the alarm and acknowledged a communication alert through a real quick tunnel. The same requests without sign-in were refused. See the [online access design](../docs/superpowers/specs/2026-11-19-online-access-design.md).

**Updated:** 27 November 2026 (signed-in tunnel test of 20 November in the online access note); 19 November 2026 (online access note); 17 November 2026 (board identity, first flash, status table and open dust point); 15 November 2026 (status table and decisions); earlier sections 8 November 2026  
**Project:** Idea 8, Room Environment Safety Monitor.  
**Platform:** Ubuntu 22.04 laptop + ESP32 over USB serial.

**Current prototype scope:** one room, one BME680 and one camera. Earlier multi-room expansion and Jetson migration proposals are deferred.

This file owns current progress and decisions. The [manual reference](ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md) owns course facts and source citations. The [README](../README.md) is the short entry point; [requirements.txt](../requirements.txt) owns executable Python pins.


## Decisions - 15 November 2026

The user made these decisions on 15 November 2026. They are decided, not implemented, except where an entry says so.

- Completion work builds on branch `feature/sharp-dust-integration`. The Sharp dust sensor stays.
- Board: ESP32-S3 with an N8R2 module (8 MB flash, 2 MB PSRAM). Correction, 17 November 2026: esptool shows the connected board is an N16R8-type module (16 MB flash, 8 MB embedded PSRAM), not an N8R2. This supersedes the DOIT ESP32 DevKit V1. Implemented: `firmware/bsec_board_config.h` requires the ESP32-S3 chip. The exact development board model is not identified.
- ESP32-S3 pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, buzzer module GPIO7. Implemented in `firmware/bsec_board_config.h`. Not checked against the physical board. Correction, 20 November 2026: the dust analog input is GPIO5 (ADC1 channel 4) and the dust LED drive is GPIO4, swapped to match the wiring. The alarm LED is the onboard RGB LED (LED_BUILTIN, GPIO48 by default), not checked on the board. No buzzer is connected now; the sketch still drives GPIO7.
- Toolchain: arduino-cli 1.5.1 with ESP32 core 3.3.12, BSEC2 1.10.2610 and BME68x 1.3.40408. The sketch compiles for the ESP32-S3 with `CDCOnBoot=default` and `CDCOnBoot=cdc`. No board has been connected or flashed. See the [15 November verification record](LINUX_VERIFICATION_2026-11-15.md).
- Dashboard primary viewer: a caregiver at a desk screen.
- Notification channel: a local alarm on the ESP32, a buzzer and an LED. The buzzer sounds for limit alerts only (patient limits, and since the step below the air-quality and dust system limits). System faults light the LED and show on the dashboard without sound. Host side and sketch wiring implemented on 15 November. Not checked on hardware.
- A dashboard "Silence alarm" button stops the buzzer for that alert. The LED stays on until the condition clears. The silence is logged. A new alert sounds again.
- Buzzer part: a 3-pin buzzer module driven from one GPIO.
- Raw readings will be kept for 7 days. Event history is kept regardless.
- The dashboard will be redesigned. The current page is a first draft.
- Air quality is Bosch's BSEC index with a word band, labelled "Bosch estimate", and "calibrating" while Bosch's accuracy is 0 or 1. Dust is an estimated concentration with a word level and an automatic clean-air baseline, labelled "estimate". Their limits are system setup in `config/system.yaml` (off as shipped), with long hold times; their alerts sound the buzzer. The patient profile has a short label. This replaces the earlier rule that gas resistance and dust voltage are raw signals only; the raw values stay as system details. Implemented on 15 November; tests, simulator and compilation only. See the [design](../docs/superpowers/specs/2026-11-15-air-quality-dust-label-design.md).

The as-built software is described in the [room software design](../docs/superpowers/specs/2026-11-15-room-software-design.md).


## Moderate Python merge

The user approved the moderate file merge and a complete reference update.
The main folder now has eleven application Python files.
settings.py owns settings loading and validation.
measurements.py owns measurement validation and retained readings.
monitoring_state.py owns combined state and message routing.
The existing functions, classes, settings keys, and serial behavior remain unchanged.
Both YAML files and all eleven test files remain separate.
Imports in application code and tests use the current modules.
The original test filenames describe the tested behavior, not separate application modules.
See [PYTHON_FILE_GUIDE.md](PYTHON_FILE_GUIDE.md) for the current file list.


## DOIT board selection - 8 November 2026

**Superseded on 15 November 2026** by the ESP32-S3 decision below. This section is kept as history. Its pins do not carry over to the ESP32-S3.

The user selected DOIT ESP32 DevKit V1 with the classic ESP32 chip.
The user confirmed a 3.3 V sensor supply.
The firmware defaults to ROOM_BME680_SUPPLY_MV 3300.
It selects the Bosch BME680 3.3 V, three-second configuration.
Select DOIT ESP32 DEVKIT V1 in Arduino IDE 2.3.10.
The board identifier is esp32:esp32:esp32doit-devkit-v1.
SDA uses GPIO21. SCL uses GPIO22. Serial uses 115200 baud.
The board header stores these values and rejects other ESP32 chip types.
The chip check cannot identify the physical development board.
This decision supersedes earlier statements that the board or supply is unknown.
The user compiled with their installed ESP32 board package and both Bosch libraries.
Preserve the existing Python dependencies and gas readiness behavior.
Linux compilation, formatter execution, Python-suite execution, and listed virtual-serial checks are recorded. Physical checks remain pending.
See [firmware guidance](../firmware/README.md) for setup and checks.

## Operating constraints

- Follow the uploaded manuals and user-approved decisions. Ask before introducing unspecified commands, dependencies, versions, algorithms, or implementation choices.
- Do not redo completed setup or replace the working `env`.
- The legacy `setup_ubuntu.sh` was removed at the user's request; preserve the existing approved environment.
- Missing Modules 4.2/4.3 leave the BME680 driver and sensor procedure unspecified. Existing experimental code does not establish approval.
- Obtain the relevant decision before system changes, firmware flashing, services, or remote exposure.
- This is an educational prototype. Do not invent patient limits or claim clinical safety.

## Current status

PRs #1 through #10 are merged into main as of 8 November 2026. The user executed the Linux suite and supplied output with no reported failures. See [README.md](../README.md) for the overview (README_HUMAN.md was folded into it and removed 27 November 2026).

**Linux continuation:** Follow the Linux handoff (file removed 27 November 2026, now folded into [README.md](../README.md)) for the current branch, environment checks, configuration test command, remaining milestones and cleanup assessment. The user explicitly deferred all remaining testing to their Linux setup. No Windows environment or alternate Windows interpreter is selected.

| Area | Evidence and state |
|---|---|
| Ubuntu/Python | User previously confirmed Ubuntu 22.04 and Python 3.10.12 |
| Virtual environment | User confirmed working `env` |
| Requirements | Setup diagnostic reported all pinned package versions; Python suite and virtual-serial runtime executed. Camera and web features remain untested. |
| Diagnostics | `tools/check_setup.py` exists; checks distribution metadata, not package imports; mismatches print CHECK without causing failure |
| Arduino IDE | Manual specifies 2.3.10; installation status unknown |
| ESP32 and port | 17 November 2026: ESP32-S3, N16R8-type module, identified by esptool. CH343 USB-UART bridge at `/dev/ttyACM0`. ESP32 core 3.3.12. Flashed; the serial link and the alarm protocol work without sensors. See the [17 November verification record](LINUX_VERIFICATION_2026-11-17.md). The development board model is not identified |
| BME680 | Sketch compiled with the recorded Bosch libraries and ESP32 core, and uploaded on 17 November 2026. No BME680 was attached: the board reported `bsec_initialization_failed` every 3 s. Wiring and physical readings remain unverified |
| Webcam/occupancy | `occupancy.py` on this branch: OpenCV default HOG people detector, one frame every 60 seconds, frames never saved. Detection gives occupied; no detection, failure or an observation older than 65 seconds gives unknown. No absent state. Not checked with a camera. The detector is trained on upright pedestrians and can miss seated, lying or occluded people |
| Rules and configuration form | `room_session.py`, `room_store.py` and the dashboard form on this branch: low/high limits for temperature, humidity and pressure, one sustained duration, occupancy gating, six-second reading-gap reset, timer reset on profile change, live YAML profile reload. No patient limits are selected. Verified in tests and the simulator only |
| SQLite and dashboard | `room_store.py` and `dashboard.py` on this branch: SQLite status, readings and events; local-only Flask dashboard with live values, 24-hour trend, alerts, latest 50 events, limits form and communication acknowledgment. No pruning. First draft; redesign decided. Checked with simulated data only |
| Notifications/local alarm | Host side implemented on branch `feature/local-alarm` (15 November 2026), see the [local alarm design](../docs/superpowers/specs/2026-11-15-local-alarm-design.md): `alarm.py` level and reachability, `ALARM,<0|1|2>` serial command with confirmation, dashboard "Silence alarm" control, events and health entry. Firmware command core `firmware/alarm_command.h` tested with g++. The sketch reads the command (bounded, non-blocking) and drives GPIO6 and GPIO7 (branch `feature/esp32-s3-port`); compiled only. Pins and buzzer polarity not checked on hardware. Correction, 20 November 2026: the alarm LED is now the onboard RGB LED (LED_BUILTIN, GPIO48 by default) and no buzzer is connected; GPIO7 drives nothing. No firmware fallback when the USB link is down (open decision) |
| Technical alert settings | Implemented as `config/alerts.yaml`, `settings.py`; startup-only loading connected by the new terminal monitor; listed virtual-serial checks completed |
| Communication-fault tracker | `communication_fault.py` implements initialization, recognized-message receipt, periodic evaluation and acknowledgment; takes supplied times and is connected by terminal runtime source; UI remains absent |
| Sensor-fault tracker | `sensor_fault.py` accumulates error time, pauses on communication timeout, resumes the remaining wait and auto-clears on valid measurements; connected by terminal runtime source; UI remains absent |
| Serial parser / validator | `serial_parser.py` and `measurements.py` classify decoded lines and check four finite numeric fields; no hardware, tracker mutation or committed-reading storage yet |
| Bosch gas status | gas_readiness.py plus parser/router integration consumes status metadata. Legacy firmware reports no BSEC metadata, so gas remains unknown. No host warm-up timer. Firmware source now uses selected three-second LP. Installed dependency versions compiled successfully. The user confirmed a 3.3 V supply. Hardware operation remains unverified. |
| Reading state and router | measurements.py, monitoring_state.py retain complete values/time, expose initial waiting and latest input states, and connect parser classifications to both fault trackers. A new terminal runtime now supplies serial I/O, monotonic timing and periodic checks in source; listed virtual-serial checks completed; physical checks remain pending. |
| Automated tests | 15 November 2026: fourteen Python test files on this branch, 317 passed with exit code 0 and no skips; `main` 301 passed. Firmware formatter built with no warnings and passed. Earlier record: all eleven Python test files (configuration, communication, sensor, measurement validation, serial parser, retained readings, routing, gas status) written; Linux output supplied: 301 cases collected, all displayed cases completed, and no failures reported. Final summary and exit code were not supplied. Limited validator smoke and Python 3.10 grammar checks passed on the available Windows host |

## Terminal serial runtime prepared

The current feature adds monitor.py, monitoring_loop.py, serial_transport.py, status_output.py, settings.py and config/runtime.yaml from PR #9, now merged into main. It uses the existing dependency pins. It loads both YAML files once and keeps one monitoring state across connection failures/retries. Fault checks run every five seconds even with no open port. Retry interval (five seconds) and polling interval (0.05 seconds) are implementation settings, not extra fault delays or BME680 sampling controls.

The serial port must be explicit. Opening it may reset the ESP32. Bounded nonblocking reads preserve partial lines; overlong/invalid-UTF-8 input does not reset communication. Failed reads/open attempts close and retry the same selected device. No device auto-selection, permission edits or firmware commands occur. Missed periodic ticks use current monotonic time, without replaying timestamps. OS/port/output delays can postpone checks; this is not a real-time guarantee.

Terminal JSON reports original complete measurements, host receipt age and an explicitly estimated UTC receipt time. Both calibration and warm-up become unavailable when measurement/contact status fails. Reconnection alone never marks data fresh. This milestone has no runtime acknowledgment command, persistence, camera, safety rules, database, notifications or web UI. Communication alerts remain latched after recovery; do not treat restarting as a logged acknowledgment.

The user ran the Python suite on Linux and supplied output with no reported failures. The suite includes routing, retries, retained readings, silence, error/noise, delayed checks, byte framing, and cleanup. There are now eleven Python test files plus separate firmware C++ tests. The original implementation step did not run these checks. Later Linux results are recorded at the top of this file. Python grammar inspection is not runtime verification.

Linux continuation: select main without discarding local work. Use the recorded existing env. Repeat the suite only if code, dependencies, failures, or an unresolved concern justify it. After firmware/dependency/supply issues are settled separately, identify the actual port and close competing readers. Use `python3 monitor.py --port /dev/ttyUSB0` only if that is the verified device; substitute the actual path otherwise. Check initial empty state, fresh readings, retained values/time through USB disconnect, two-minute alerts, recovered contact with a latched communication alert, error-to-valid recovery and Ctrl+C cleanup. Do not perform live sensor rewiring without an agreed hardware procedure.

See the [runtime design](../docs/superpowers/specs/2026-11-08-serial-runtime-design.md) and [verification plan](../docs/superpowers/plans/2026-11-08-serial-runtime.md). VIGIL also separates monitoring from its dashboard; USB framing/reconnect is project-specific. The original BSEC firmware and all prior pure modules remain unchanged.

## BSEC firmware source prepared

The user approved three-second LP sampling. PR #8 added the firmware source and is now merged into main. BSEC controls sampling, only new callback data produces readings, and errors remain recognized communication. No fixed gas warm-up countdown is added. Camera processing stays60 seconds, fault checks5 seconds, dashboard10 seconds, and both host fault durations120 seconds.

Read [firmware/README.md](../firmware/README.md) before installation or compilation. The installed Bosch libraries compiled with the installed ESP32 board package. See the verification record for the observed build and remaining physical checks. Use the confirmed sensor supply setting, ROOM_BME680_SUPPLY_MV 3300. The user subsequently confirmed 3.3 V; the default is now 3300. Recheck the supply if the breakout changes. No firmware compilation, tests, flashing, service or hardware operation ran on Windows.

The inspected wrapper converts pressure to hPa before callback. The sketch uses that value without a second division. Recheck this contract if using a different wrapper and verify physical units. Do not copy generic raw-pressure units blindly. State persistence, automatic sensor reinitialization and custom temperature compensation remain future work.

Eleven Python test files now exist, with an added JSON fixture consumer case. A separate portable C++ formatter test is written in firmware/tests/test_bsec_serial_format.cpp. Execute it on Linux using an agreed available C++11 toolchain, then compile the sketch only after dependency/supply confirmation. The C++ test is separate from pytest. The user subsequently reported it passed on Linux.

## Approved gas readiness design

The user approved Bosch BSEC status integration on 8 November 2026, superseding the earlier host timer/YAML warm-up proposal. No gas_warmup_s field or fixed countdown is selected.

Python status handling is implemented: gas_readiness.py validates an optional bsec object with integer stabilization_status, run_in_status and iaq_accuracy. The parser/router retains a coherent immutable snapshot from each recognized record. Missing/invalid metadata becomes unknown without changing measurement validity or inventing sensor faults. Warm-up and IAQ calibration are separate descriptions. Current gas warm-up status is unavailable during communication timeout or bad measurement input. None of these labels establishes room safety or certified calibration.

New firmware source targets BSEC LP and emits recognized JSON measurements/errors plus gas metadata. Physical operation remains unverified. It compiled on Linux but is not flashed. Legacy firmware supplies no BSEC metadata. Bosch datasheet Revision 1.9 documents 1Hz CONT for short-term testing only and LP updates every three seconds. The user now approved three-second LP sampling. This supersedes continuous one-second sampling. New firmware compiled on Linux but is not flashed. Keep actual fault checks five seconds, camera processing sixty seconds, dashboard ten seconds, and both fault timeouts 120 seconds.

Candidate inspected wrapper: Bosch-BSEC2-Library release 1.10.2610, algorithm 2.6.1.0. The user subsequently installed both Bosch libraries. Firmware compiled with the installed ESP32 board package and the 3300 supply setting. No physical flashing or sensor operation occurred. Preserve course-pinned Arduino IDE and Python requirements. State persistence is a potential later integration, not implemented.

See [BSEC status design](../docs/superpowers/specs/2026-11-08-bsec-status-design.md) for the contract and manufacturer sources. VIGIL has no direct gas readiness equivalent.

## Selected execution intervals

Fault scheduling is implemented in the terminal loop source. Camera and dashboard scheduling remain planned.

| Operation | Selected interval | Current control/status |
|---|---|---|
| BME680 acquisition | 3 seconds | Selected BSEC LP mode in new source; hardware timing unverified |
| Camera occupancy processing | 60 seconds | Latest learner choice; supersedes the earlier 5-second proposal; Python scheduling not implemented |
| Fault evaluation | 5 seconds | Implemented in new terminal loop source; listed virtual-serial checks completed; physical checks pending |
| Dashboard refresh | 10 seconds | Selected for future dashboard |

**15 November 2026:** On branch `feature/sharp-dust-integration`, the 60-second camera interval and the 10-second dashboard refresh are implemented as constants in code, not YAML settings. So are the 6-second reading-gap limit and the 15-second dashboard staleness limit.

The future Python-side technical settings should load at startup. The camera processing interval does not select a capture frame rate or buffering policy; those remain open. Occupancy may reflect the previous observation until the next one-minute processing check. When five-second fault evaluation is integrated, timeout detection occurs on the next check, potentially almost five seconds after the duration expires plus scheduling/processing delay.

## Future side note — ESP32 sampling configuration (deferred)

The learner explicitly declined adding ESP32 startup configuration now and requested that the idea be kept for later.

Possible later extension: read a desired acquisition interval from laptop YAML and send it to the ESP32 over USB serial at startup, with agreed firmware handling and confirmation. No command format, firmware implementation, dependency version, or automatic action is selected or authorized by this note.

For the current prototype, the new BSEC firmware selects the approved three-second LP interval. Laptop-to-ESP32 sampling configuration remains deferred. Do not add a YAML field that appears to control actual acquisition without implementing the ESP32 path; changing Python read/poll delays would not change the sensor's firmware sampling interval. This defers actual YAML-to-ESP32 interval control, rather than implementing a misleading host-only setting.

## Existing sensor test

- `firmware/room_environment_safety_control_bme680.ino` now targets Bosch BSEC2/BME68x, GPIO8 SDA/GPIO9 SCL on the ESP32-S3 (GPIO21/GPIO22 on the earlier DOIT board), addresses 0x76 then 0x77, and JSON at 115200 baud at the selected three-second LP interval (not hardware-verified).
- `tools/read_sensor.py` prints parsed records. It does not store data, validate measurement fields, reconnect after USB loss, or apply safety rules.
- Firmware does not retry initialization after a sensor is missing at boot.
- Bosch integration and JSON schema are user-approved project adaptations, not prescribed by the available manuals.
- The installed ESP32 board package compiled successfully. The sketch uses Bosch BSEC2/BME68x. Adafruit BME680 is not a firmware dependency.

## Implementation sequence

### A - Verify the existing environment

Completed in the user's existing Linux environment. The setup diagnostic matched all required package versions. The user executed the Python suite and listed runtime checks. Preserve this environment.

Inside the existing activated `env`, the manual documents:

```bash
python3 --version
python3 -c "import numpy as np; print('NumPy', np.__version__)"
python3 -c "import cv2; print(cv2.__version__)"
```

The setup diagnostic matched all pinned package versions. Separate camera and web feature checks remain pending. Do not interpret metadata-only diagnostics as successful imports.

### B — Confirm toolchain and serial

Status, 17 November 2026: arduino-cli 1.5.1 with ESP32 core 3.3.12 built and uploaded the firmware. The port is `/dev/ttyACM0` through a CH343 bridge. The serial link was checked without sensors. Arduino IDE 2.3.10 is still unconfirmed.

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

Agree on the notification channel and offline behavior. Slow delivery must not stop sampling or local decisions. Optional ESP32 LED/buzzer wiring must avoid the I2C pins (GPIO8/GPIO9 on the ESP32-S3; GPIO21/22 on the earlier DOIT board). Do not enable tunnels or services by default.

Status, 15 November 2026: the channel is a local LED and buzzer on the ESP32. The host side, the silence control, the firmware command core and the sketch wiring exist. They are checked with tests, the simulator and a compilation. Tests show that a failing or silent alarm link does not delay readings, fault checks, limit alerts or the status. Remaining:

1. Done in the firmware port step: the sketch reads `Serial` without blocking (at most 64 bytes per loop pass), drives the alarm LED on GPIO6 and the buzzer module on GPIO7, starts at level 0, and replies after each applied command and once at start-up. Compiled only.
2. On 17 November 2026 the board answered `ALARM,0`, `ALARM,1`, `ALARM,2` and `ALARM,0` with the matching reply, ignored `ALARM,9`, and the monitor confirmed level 0. Nothing was wired to GPIO6 or GPIO7. Still to do on the real ESP32-S3: check the GPIO6 and GPIO7 wiring, the LED series resistor, the buzzer module polarity (`ROOM_BUZZER_ACTIVE_HIGH`, default true) and whether it needs a tone or a steady level. Correction, 20 November 2026: the alarm LED is now the onboard RGB LED (LED_BUILTIN, GPIO48 by default), so no GPIO6 wiring or series resistor is needed. No buzzer is connected now; the GPIO7 buzzer checks wait until one is fitted.
3. On the real board, check that reading `Serial` does not delay BSEC sampling. By design the read is bounded and the dust task has a higher priority.
4. Decide whether the board should light its LED by itself when it stops hearing from the host. Not implemented.

Air quality and dust estimate, 15 November 2026: done with tests, the simulator and a compilation. Remaining:

1. Decide whether to save the BSEC calibration state across power loss. Not implemented; the index calibrates again after each board start.
2. Check the Bosch word bands and the Sharp typical sensitivity against the datasheets. No copy is on this machine.
3. Decide whether `BSEC_OUTPUT_STATIC_IAQ` suits a fixed room device better. The local library documentation does not settle it.
4. Agree on real air-quality and dust limits and hold times if any are wanted. None are supplied.
5. Compare the dust estimate with a reference instrument if concentration matters.
6. Detect a disconnected dust sensor. With no dust sensor attached, the dust input reads about 870 to 930 mV and is accepted as a fresh dust record, most likely because the ADC pin floats. A disconnected dust sensor cannot currently be told apart from a working one. Candidate fixes: a pull-down resistor on the dust input, or a firmware check that compares the signal with the sensor LED on and off. Not decided; the user will choose when wiring. See the [17 November verification record](LINUX_VERIFICATION_2026-11-17.md).

### H — Verify and demonstrate

Use the pinned pytest dependency for hardware-free rule tests. Cover short spikes, sustained breaches, recovery, absent/uncertain occupancy, missing/stale sensor data, and delayed/offline notifications. Demonstrate real input and agreed dashboard behavior separately.

## Project workflow preferences

- Current name: **Room Environment Safety Control**, selected by the user on 8 November 2026. The repository name remains ES-II_SP1.
- Use VibeWise learning mode, Impeccable for dashboard design, and the requested GitHub, Superpowers, Computer, Browser, and Plugin Management capabilities where relevant. VibeWise's local learning skill has been read and is active; Impeccable is available.
- Continue from the existing Linux environment. Results are based on user-supplied terminal output reviewed in the conversation.
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
- Technical configuration, both pure fault trackers, serial classification and finite-field measurement validation are implemented; the user executed the Python tests on Linux. Recognized reading/error types, incomplete-field treatment and ignored input are selected. Committed-reading retention and routing now exist in separate modules. Runtime clock/scheduling, persistence/history and hardware integration remain future work.
- Implementation details: immutable snapshots; timeout equality uses >=; late communication preserves its elapsed fault before recording recovery; no-op acknowledgments do not extend waits. Sensor pauses begin when timeout status is supplied, not retroactively. Existing sensor alerts remain until a valid reading; an error with no remaining wait alerts on resume. These details are explicit in the designs and deferred tests.

## Selected serial-input handling

- Type=reading requires temp_c, humidity_pct, pressure_hpa and gas_ohms as finite numeric values, excluding bools/numeric strings. Missing/unusable values produce incomplete_reading with no partial values to commit.
- Incomplete readings preserve the last complete committed snapshot and original timestamp in the reading-state/router consumer, indicate incomplete current input immediately, and start/continue the existing sensor-error episode without restarting it. Explicit type=error is sensor_error and also contains no committable measurements.
- Decoder failures, non-object JSON and missing/unknown record types are ignored. They do not reset communication time or directly change sensor-error state; scheduled fault checks continue.
- Only valid_reading carries replacement measurements. Patient/physical range limits are not introduced by structural validation. Parser remains stateless. The new router connects it to reading/fault state, but is not wired into the experimental reader yet.
- Use fewer build checkpoints for routine choices, as requested. After each meaningful checkpoint response, compare verified VIGIL behavior. It has no BME680 serial parser; distinguish architectural analogy from a direct equivalent.

## Next information needed

1. Exact BME680 breakout model, exact ESP32-S3 development board model and hardware availability. The ESP32-S3 is selected. esptool identified it on 17 November 2026 as an N16R8-type module (16 MB flash, 8 MB PSRAM), not the N8R2 assumed before. The development board model is still not identified.
2. Whether Modules 4.2/4.3 can be supplied.
3. No repeat environment report is needed unless that environment changes. See the Linux verification record.
4. Technical YAML loading is decided: startup-only initially. Patient-profile live updates are selected as a future feature; their validation and effect on environmental breach timers still need agreement.

## Source pointers

- Assignment: Idea Book pp. 21–22.
- Python pins/checks: Module 3.2 pp. 3–4, 35–36.
- ESP32/IDE/serial/camera: Module 3.3 pp. 3–8, 14–20.
- Environment: Module 2.2 pp. 8–10.
- Flask/SQLite/configuration/testing architecture: Module 3.4 and VIGIL ZIP.
- Full extraction: [manual reference](ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md). Original PDFs/ZIP are absent from this repository.
