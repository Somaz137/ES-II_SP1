# Room Environment Safety Control - Project 8

This project monitors one room using a laptop, an ESP32 board, a BME680, a Sharp dust sensor, and a camera for occupancy.
The selected board changed to an ESP32-S3 on 15 November 2026. See [Selected hardware](#selected-hardware).

## Current status

This branch adds the room software: SQLite storage, patient limits, sustained-breach alerts, camera occupancy, a local dashboard, and a Sharp dust sensor path.
These parts exist in software. They are verified only by automated tests and the simulator.
On 17 November 2026 the ESP32-S3 was flashed. The serial link and the alarm protocol were checked with no sensors attached.
On 20 November 2026 the board, still on firmware `1c74995`, was checked on the bench with the BME680, the dust sensor and the onboard RGB LED. The alarm replies, the LED, the link-lost blink, the dust fault through the monitor, the dashboard pages and the BME680 temperature, humidity and pressure passed. Dust failed and the gas reading is suspect. See the [firmware hardware checklist](firmware/README.md#hardware-checklist). No buzzer or camera check has taken place.
The Bosch calibration (BSEC) state is now saved on the laptop and sent back at board start (20 November 2026). It is compiled and host-tested. It is not yet checked on hardware: the board still runs `1c74995`, from before this firmware. See [Bosch calibration state](#bosch-calibration-state).
The local alarm is implemented on the host and in the sketch. It is checked with the simulator, host C++ tests, a compilation for the ESP32-S3, and the board's serial replies to `ALARM` commands (17 November). On 20 November the onboard RGB LED was off or white as commanded. No buzzer has been driven. The dashboard redesign is implemented on this branch as five pages: Overview, Trends, Events, Patient limits and System. It is checked with the simulator and screenshots, not on hardware. 7-day reading retention is implemented.
Opt-in view-only online access is implemented (19 November): a Cloudflare quick tunnel to a second, view-only origin, with a password for controls. One real tunnel run on 19 November 2026 loaded the pages and refused control requests without sign-in. A signed-in control request through the real tunnel has not been tried.
The [local alarm design](docs/superpowers/specs/2026-11-15-local-alarm-design.md) defines the alarm levels, the serial command, silence and reachability.
The [dashboard data contract](docs/superpowers/specs/2026-11-15-dashboard-data-contract-design.md) defines the dashboard response, alert text, events, timing settings, and retention.

Read the [17 November verification record](reference_files/LINUX_VERIFICATION_2026-11-17.md) for the first flash and serial link check.
Read the [15 November verification record](reference_files/LINUX_VERIFICATION_2026-11-15.md) for the current software results.
Read the [8 November verification record](reference_files/LINUX_VERIFICATION_2026-11-08.md) for the earlier virtual-serial and compilation results.

| Check | Recorded result |
|---|---|
| Python test suite, this branch | 462 passed, exit code 0, no skips, also with `-W error` (15 November, after the ESP32-S3 port). |
| Python test suite, `feature/bsec-state` | 752 passed (23 November, after the BSEC state save). |
| BSEC state save and restore | Four firmware host test programs passed with no warnings. The sketch compiled with the 16 MB options and `CDCOnBoot=default`, no warnings (20 November). Not flashed. Not checked on hardware. |
| Bench check, firmware `1c74995` | Pass: alarm replies in about 10 ms, `ALARM,9` no reply, onboard RGB LED off or white as commanded, link-lost blink after 30 s, dust fault at 120 s with level 1 confirmed, all five dashboard pages and `/api/room` HTTP 200, BME680 temperature, humidity and pressure every 3.000 s. Fail: dust (`dust_input_at_zero` on every reading). Suspect: gas (20 November). |
| Python test suite, `main` | 301 passed, exit code 0 (15 November). |
| Firmware message formatting | Built with no warnings and passed (15 November). |
| Firmware alarm command core | `firmware/tests/test_alarm_command.cpp` built with `g++ -std=c++11 -Wall -Wextra -pedantic` with no warnings and passed (15 November, after the ESP32-S3 port). |
| Firmware dust sample rule | `firmware/tests/test_sharp_dust_limits.cpp` built the same way with no warnings and passed (15 November). |
| Local alarm demo | With `--demo`, the simulated board confirmed level 2 during the limit alert, level 1 after "Silence alarm", and level 0 after the alert ended (15 November). No LED or buzzer was driven. |
| Software demo | Monitor and dashboard ran together. The simulated limit alert started and ended as expected (15 November). |
| Complete firmware compilation | The current sketch, with dust code and alarm, compiled for the ESP32-S3 with the 8 MB options then assumed (N8R2), `CDCOnBoot=default` and `CDCOnBoot=cdc`, no warnings (15 November). Compilation only. |
| First flash, ESP32-S3 | Compiled with no warnings and uploaded with every hash verified. Clean boot. With no BME680, `bsec_initialization_failed` every 3 s (17 November). |
| Alarm protocol on the board | `ALARM,0`, `ALARM,1`, `ALARM,2`, `ALARM,0` each got the matching reply in about 10 ms. `ALARM,9` got none. `monitor.py` ran 60 s with the alarm confirmed at level 0. Serial replies only; nothing was wired to the LED or buzzer pins (17 November). |
| Online access, real tunnel | Pages loaded through a real quick tunnel. Control requests without sign-in were refused. No signed-in control request was sent through the tunnel (19 November). |
| Missing communication | Monitor raised the communication alert and retained previous measurements (8 November). |
| Communication recovery | Fresh readings resumed. The outstanding communication alert remained active (8 November). |
| Repeated sensor errors | Communication stayed active while the sensor alert became active (8 November). |
| Sensor-error recovery | A valid reading cleared the sensor alert (8 November). |
| Simulated gas-status changes | Warm-up and calibration labels changed as expected (8 November). |

The runtime checks used a virtual serial port, a simulator, and artificial messages.
They do not establish physical sensor accuracy, calibration, camera detection, USB behavior, or room safety.

## Start here

- [Human guide](README_HUMAN.md): project purpose and behavior.
- Verification records: [8 November](reference_files/LINUX_VERIFICATION_2026-11-08.md), [15 November](reference_files/LINUX_VERIFICATION_2026-11-15.md) and [17 November](reference_files/LINUX_VERIFICATION_2026-11-17.md): completed checks and remaining work.
- [Room software design](docs/superpowers/specs/2026-11-15-room-software-design.md): storage, rules, occupancy, and dashboard as built.
- [Sharp dust integration](docs/SHARP_DUST_INTEGRATION.md): dust wiring, calibration, and checks.
- [Implementation plan](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md): decisions and milestones.
- [Linux handoff](reference_files/LINUX_AI_HANDOFF.md): continuation guidance.
- [Manual reference](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md): course requirements and source pointers.
- [Firmware guide](firmware/README.md): sketch structure and hardware checks.
- [Python requirements](requirements.txt): required package versions.

Older preparation notes and component checklists describe the state before the recorded Linux session.
Do not repeat completed checks without a change, failure, or specific unresolved concern.

## Selected hardware

The board is an ESP32-S3 (QFN56, revision v0.2) with 16 MB quad flash and 8 MB embedded PSRAM, an N16R8-type module. esptool read these facts from the connected board on 17 November 2026. The documents assumed an N8R2 module (8 MB flash, 2 MB PSRAM) until then. The user selected the ESP32-S3 on 15 November 2026. It supersedes the DOIT ESP32 DevKit V1.
The board's USB port goes through a CH343 USB-UART bridge (USB 1a86:55d3). Linux names it `/dev/ttyACM0`.
Pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO5, dust LED drive GPIO4, and buzzer module GPIO7. The alarm LED is the onboard RGB LED (GPIO48 by default). It lit white as commanded on the bench on 20 November 2026. No buzzer is connected now, so GPIO7 drives nothing.
The firmware uses these pins. They are not checked against the physical board. The exact development board model is not identified.
The user confirmed a 3.3 V sensor supply.
The board header stores the pins, buzzer polarity, serial speed, supply selection, and reporting intervals.
The chip check rejects every chip except the ESP32-S3. It cannot identify the physical development board.
The firmware compiles with ESP32 core 3.3.12, BSEC2 1.10.2610 and BME68x 1.3.40408. The [firmware guide](firmware/README.md) has the build commands, the serial (CDC On Boot) choice and the hardware checklist.
The board was flashed on 17 November 2026 with `esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default`. `CDCOnBoot=default` matches the CH343 bridge. PSRAM is disabled because the firmware does not use it. The serial link and the alarm replies were checked without sensors. See the [17 November verification record](reference_files/LINUX_VERIFICATION_2026-11-17.md).

The sketch uses Bosch BSEC2 and Bosch BME68x.
The Python requirements do not install Arduino libraries.
Breakout wiring, actual pressure units, and physical readings remain unchecked.

## Main components

The application now uses seventeen Python files in the main folder.
Related settings, measurements, and state updates share files.
See the [Python file guide](reference_files/PYTHON_FILE_GUIDE.md) for every application, tool, and test file.
The test filenames remain unchanged so their original test cases are easy to track.

| File | Purpose |
|---|---|
| monitor.py | Starts the monitor with an explicit serial port, or with `--demo` for simulated input. Connects storage, rules, camera, acknowledgment and silence requests, and the local alarm. |
| serial_transport.py | Reads complete lines, handles partial input, and retries the selected port after connection errors. |
| monitoring_loop.py | Routes input and checks faults during silence. |
| status_output.py | Reports retained readings, reading age, estimated receipt time, faults, gas status, and dust status. |
| room_store.py | Stores status, readings, and events in SQLite. Loads, validates, and saves the patient profile file. |
| room_session.py | Applies patient limits, sustained-breach timing, and occupancy gating. Logs alert and fault events. |
| occupancy.py | Checks the camera at the configured interval (60 seconds) with OpenCV's default people detector. Saves no frames. |
| simulated_input.py | Supplies simulated BME680 and dust records for `--demo`. |
| dust.py | Classifies Sharp dust records and reports dust status. Tracks the clean-air baseline and calculates the dust estimate. |
| dashboard.py | Serves the local dashboard on 127.0.0.1. Reads SQLite. Saves patient limits, acknowledgment requests and alarm silence requests. |
| alarm.py | Decides the local alarm level (0 off, 1 LED, 2 LED and buzzer), silence, and whether the board confirmed the level. No I/O. |
| templates/, static/ | Dashboard pages (shared layout and five pages), script, charts, and style. |
| `settings.py` | Loads both YAML settings files and checks their values. |
| config/runtime.yaml | Stores host polling, retry, and fault-check intervals, the reading gap, dashboard staleness and refresh, camera interval, reading retention, and the alarm confirmation timeout. |
| config/alerts.yaml | Stores the communication and sensor-error timeouts. |
| communication_fault.py | Tracks missing communication and alert acknowledgment. |
| sensor_fault.py | Tracks repeated sensor errors and valid-reading recovery. |
| `measurements.py` | Checks measurements and retains the last complete reading and its receipt time. |
| serial_parser.py | Classifies readings, errors, incomplete records, and ignored input. |
| `monitoring_state.py` | Stores the combined state and applies incoming messages to readings and fault trackers. |
| gas_readiness.py | Interprets reported Bosch warm-up and calibration status and keeps the reported air-quality index. |
| air_quality.py | Decides whether the Bosch index is current or calibrating and picks its display word. |
| firmware/room_environment_safety_control_bme680.ino | Reads the sensor and sends JSON measurements or error records. |
| firmware/bsec_board_config.h | Stores board pins, buzzer polarity and settings. Validates chip (ESP32-S3) and supply selections. |
| firmware/bsec_serial_format.h | Formats measurements and Bosch status as JSON. |
| firmware/sharp_dust.h | Experimental Sharp dust acquisition and raw voltage reports. Compiled for the ESP32-S3. Not hardware-checked. |
| firmware/sharp_dust_limits.h | Pure dust sample rule: timing window, ADC limit and divider. |
| firmware/tests/test_sharp_dust_limits.cpp | Tests `sharp_dust_limits.h` with g++ on Linux. |
| tools/check_setup.py | Reports environment metadata. It does not prove full application operation. |
| tools/read_sensor.py | Prints records from a selected serial port as a separate diagnostic. |
| tests/ | Contains the automated Python tests. |
| firmware/tests/test_bsec_serial_format.cpp | Contains the separate portable C++ formatting test. |
| bsec_state_store.py | Keeps the board's BSEC calibration state in `<database name>.bsec_state.json`, answers the board's state requests, and reports saves and restores as events and a status block. |
| firmware/host_command.h | Reads the host lines `ALARM,<0|1|2>`, `BSEC_STATE,<hex>` and `BSEC_STATE,NONE` with a fixed buffer, formats the BSEC state as hex, and holds the state-save rule. |
| firmware/tests/test_host_command.cpp | Tests `host_command.h` with g++ on Linux. |
| firmware/alarm_command.h | Parses `ALARM,<0|1|2>` commands with a fixed buffer, reads `Serial` with a byte bound, maps the level to LED and buzzer, and formats the reply. |
| firmware/tests/test_alarm_command.cpp | Tests `alarm_command.h` with g++ on Linux. |

## Run the software demo

Run both entry points in your existing project environment, in separate terminals:

```text
python monitor.py --demo
python dashboard.py --demo
```

Open http://127.0.0.1:5000. The demo uses its own SQLite database. It simulates an occupied room, BME680 readings, and Sharp dust voltage at three-second intervals. On a fresh demo database the temperature crosses the example limit at 18 seconds, raises a caregiver alert at about 27 seconds, and returns to range at about 60 seconds. Patient limits are saved beside the database in a `.profile.yaml` file. Valid changes take effect on the next monitor update. If the file is invalid, the monitor keeps its last valid profile and shows a profile error. The example values apply only to the simulator.

The dashboard refreshes every ten seconds. It shows the last monitor update, sensor readings, occupancy, 24-hour trends, caregiver alerts with limit, value, and duration, pending breaches, the latest 50 events, a patient limits form, the communication acknowledgment control, and the local alarm state with a "Silence alarm" button. Trend points are one-minute averages with minimum and maximum. Gas resistance and dust voltage are charted as system details and have no limit. Air quality (Bosch index) and the dust estimate are shown with a word and an "estimate" label, and charted while current. `GET /api/room` returns all of this in one response. The dashboard accepts requests only for `localhost` and `127.0.0.1` and rejects cross-site form posts. The dashboard can be closed while monitoring continues. Readings and event history stay in local SQLite files. The 24-hour chart is a display window. The monitor deletes readings older than 7 days. Events are kept.

On the real serial path, supply the existing serial port argument and the `--camera` index option when physical testing resumes. Both programs accept `--db` and must use the same file. OpenCV checks at one-minute intervals. A detected person gives occupied status. Failed capture, no detection, and expired observations give unknown status. Frames are processed locally and never saved. Physical validation is still pending.

## Online access (opt-in, view-only)

Monitoring, alerts and the local alarm never depend on the internet. Online access starts only on request. Install `cloudflared` separately, then set the online password once (it is stored as a hash in the git-ignored `config/online_secret.yaml`):

```text
python dashboard.py --set-password
python dashboard.py --online
```

`--online` also serves a view-only origin on 127.0.0.1:5001 and starts a Cloudflare quick tunnel to it. The random `trycloudflare.com` link changes on each start and appears on the System page (with Copy link) on this computer. Anyone with the link can view. Saving limits, silencing and acknowledging online need the password; on this computer they need no sign-in. Without a password or without `cloudflared`, the local dashboard still runs and the System page says why online access is off or failed. Stop online access by stopping `dashboard.py`. Port, program path and sign-in lifetime are in `config/runtime.yaml`. Design: [online access](docs/superpowers/specs/2026-11-19-online-access-design.md).

## Sharp dust sensor

The experimental GP2Y1010AU0F path adds independent dust voltage and status. A stale dust report raises a dust fault. The host converts the voltage to an estimated concentration in µg/m³ with Sharp's typical sensitivity and an automatic clean-air baseline (the lowest voltage in the last 24 hours, after 10 minutes of unbroken fresh records). The old `--dust-baseline-mv` and `--dust-sensitivity` options are removed. See [wiring, plan, calibration, and verification](docs/SHARP_DUST_INTEGRATION.md). The decided ESP32-S3 dust pins are GPIO5 (analog input) and GPIO4 (LED drive), swapped on 20 November 2026 to match the wiring. Firmware compilation and hardware timing remain pending.

## Local alarm

The host commands a local alarm on the ESP32 over the serial link: `ALARM,0` (off), `ALARM,1` (LED only) or `ALARM,2` (LED and buzzer). The board replies `{"type":"alarm","state":<n>}` after applying a command.

- Level 2: at least one limit alert (patient or system limit) that has not been silenced.
- Level 1: a silenced limit alert, or an active communication, BME680 or dust alert. The buzzer stays off.
- Level 0: otherwise. The board starts at level 0.

The host sends on every change and again at each fault check, so a board reset is corrected. The dashboard shows the alarm as confirmed, pending, or unreachable (port not connected, write failed, or no reply within `alarm_confirm_timeout_s`, default 2 seconds). "Silence alarm" stops the buzzer for the limit alerts shown. The LED stays on. The monitor applies the silence at its next fault check and logs it. A new limit alert sounds again. Alarm failures never delay readings, fault checks or the status.

The sketch reads commands without blocking, at most 64 bytes per loop pass, drives the alarm LED, which is the onboard RGB LED (GPIO48 by default), and GPIO7 (buzzer module) with a steady level, and replies after each command and once at start-up. The buzzer polarity is one constant, `ROOM_BUZZER_ACTIVE_HIGH`, default active high, not verified. No buzzer is connected now (20 November 2026). In the demo the simulated board echoes each command. On 20 November 2026 the onboard RGB LED was off or white as commanded. No buzzer has been driven.

Link-lost fallback: when the board gets no valid `ALARM` command for 30 s, the LED blinks, 1 s on and 1 s off. The buzzer keeps its last commanded state. Only a valid command resets the timer, and the next one ends the blink. The host normally sends a command every 5 s. Implemented on 20 November 2026. On the bench the same day the user saw the blink start after 30 s with no command and saw the next command stop it.

## Bosch calibration state

Bosch's BSEC library learns the room's normal air over hours. Its IAQ accuracy goes from 0 to 3. The board keeps this learned state only in RAM, so a reset or a power cut loses it. The laptop now keeps a copy in a file (user decision, 20 November 2026). See the [design](docs/superpowers/specs/2026-11-20-bsec-state-on-laptop-design.md).

- Save: the board sends its state only at IAQ accuracy 3. It sends the first time accuracy reaches 3 after start, then every 6 hours while accuracy is 3. Six hours is Bosch's standard interval, from Bosch's example sketch `basic_config_state.ino` (`STATE_SAVE_PERIOD`, 360 minutes).
- File: the monitor writes `<database name>.bsec_state.json` next to the database, for example `room.bsec_state.json` or `room-demo.bsec_state.json`. It writes a temporary file and renames it, so a crash never leaves a half-written file.
- Restore: at start the board asks for the state after `setConfig` and before it subscribes to outputs (Bosch's example order). It waits up to 10 s and still applies `ALARM` commands. The monitor replies `BSEC_STATE,<hex>` when the file exists and its BSEC version matches the board's. Otherwise it replies `BSEC_STATE,NONE` and logs the reason: no saved state, version mismatch, or file damaged. With no reply in 10 s the board starts without a state.
- If the board cannot read its state to save it, it prints the error `bsec_state_save_failed` and tries again on the next loop pass. The monitor logs it as a `bsec_state_save_failed` event, not as a sensor error.
- Events: `bsec_state_saved`, `bsec_state_sent`, `bsec_state_not_sent`, `bsec_state_restored`, `bsec_state_restore_failed` and `bsec_state_save_failed`. The Events page shows them under "Bosch calibration".
- The System page has a "Bosch calibration" row: "Bosch calibration saved: <time>, accuracy 3" or "Bosch calibration not saved yet", with the result of the last board request.
- In `--demo` the simulated board asks for the state at start and sends one stand-in state (not a real Bosch state) after 60 s.

Status: compiled and host-tested (four firmware host test programs and the Python suite). Not checked on hardware. The board on the bench still runs firmware `1c74995`, from before this feature. A new flash and a bench check are needed: run to accuracy 3, wait for a save, power-cycle, and confirm the restore.
Opening the CH343 port does not reset the board (20 November 2026), so starting `monitor.py` does not cause a restore. The board asks only when it starts.

## Behavior to preserve

The monitor loads technical settings at startup.
The initial communication wait begins when the monitor starts.
Recognized readings and sensor errors both count as communication.
Incomplete readings retain the previous complete measurements and their original receipt time.
Ignored input does not reset communication timing.
Alarm replies do not count as communication. The host asks for them, so they must not hide a stopped measurement stream.
The BSEC state lines (`bsec_state`, `bsec_state_request`, `bsec_state_restored` and the `bsec_state_save_failed` error) do not count as communication either.

Missing communication raises a communication alert.
Communication recovery clears the timeout but does not dismiss that alert.
A person must acknowledge the alert on the dashboard after contact recovers.
The dashboard cannot acknowledge during an outage.
The monitor applies the acknowledgment at its next fault check. The event history records the acknowledgment and the cleared alert.
Restarting the program is not a recorded acknowledgment.

Repeated sensor errors do not restart the sensor-error waiting period.
A valid reading clears the sensor alert automatically.
Sensor-error time pauses when communication times out.
The program retains separate communication and sensor alert states.

Bosch controls the selected three-second low-power acquisition interval.
Python does not use a fixed warm-up countdown.
Warm-up and calibration labels describe Bosch reports.
They do not establish certified calibration or room safety.
Gas status becomes unavailable during communication loss or invalid current measurements.
Raw gas resistance is not a calibrated pollution concentration or air-quality index.

## Air quality, dust estimate and system limits

Decision of 15 November 2026. It replaces the earlier rule that gas resistance and dust voltage are raw signals only. Raw gas resistance and dust voltage stay stored and shown as system details.

- Air quality is Bosch's BSEC index (0 to 500), labelled "Bosch estimate", with a word band. It shows as calibrating, with no value, while Bosch's accuracy is 0 or 1.
- Dust is an estimated concentration in µg/m³ with a word level, labelled "estimate". It shows "establishing baseline", with no value, until the baseline exists.
- `dust.disconnected_below_mv` (default 100 mV) is a required key in `config/system.yaml`. A dust voltage below it, a 0 mV reading, or the board's `dust_input_at_zero` report all count as "no reading". After 120 s (the sensor timeout) with no reading at or above it, the page says not connected.
- Their limits are system setup in `config/system.yaml`, not dashboard controls. Each has an upper limit and a hold time. The shipped file leaves both off; the project supplies no values. The word bands and levels there are display defaults, not health standards. The Bosch bands and the Sharp sensitivity are not checked against a datasheet on this machine.
- Their alerts follow the patient-limit rule (sustained, occupied, current reading), sound the buzzer and can be silenced. A calibrating index or a missing baseline pauses that check, with a stated reason.
- `monitor.py --demo` uses demonstration limits (air quality 150 for 30 s, dust 100 µg/m³ for 30 s) so the simulator shows both alerts. They are not recommendations.
- The patient profile has an optional short label, for example "Bed 3", set in the limits form. No patient name is stored.
- The BSEC calibration state is saved on the laptop and sent back at board start, so a reset need not lose it. See [Bosch calibration state](#bosch-calibration-state). Compiled and host-tested; not checked on hardware.

See the [design](docs/superpowers/specs/2026-11-15-air-quality-dust-label-design.md).

Patient limits apply to temperature, humidity, and pressure. Each enabled measurement has a lower and upper limit. One sustained duration applies to all.
The project supplies no patient limits. The demo example limit applies only to the simulator.
A patient-limit alert starts when a breach lasts the sustained duration. One in-range reading ends it.
Patient-limit alerts require occupied status and a fresh BME680 reading at most six seconds old (`reading_gap_limit_s`).
Unknown occupancy, a stale reading, or a gap of more than six seconds between readings restarts the timer.
A changed profile restarts all timers. An invalid profile file keeps the last valid profile and shows a profile fault.
Communication, BME680, dust, and profile fault alerts do not depend on occupancy.

Fault checks use the selected five-second interval.
Camera processing uses sixty seconds. An observation older than sixty-five seconds becomes unknown.
The dashboard refreshes every ten seconds and treats a status older than fifteen seconds as overdue.
These values are optional keys in `config/runtime.yaml`. An older three-key file still loads with these defaults. Demo mode uses the same defaults. The dashboard reads the effective values from the monitor status.
Laptop YAML does not control ESP32 acquisition timing.
Firmware configuration commands remain future work. The BSEC calibration state is kept on the laptop. See [Bosch calibration state](#bosch-calibration-state).

## Known limitations

- The occupancy detector is OpenCV's default people detector, trained on upright pedestrians. It can miss seated, lying, or occluded people. Unknown occupancy suppresses patient-limit alerts. It has not been checked with a camera.
- In serial mode without `--camera`, occupancy is always unknown, so patient-limit alerts never start.
- Readings older than 7 days are deleted hourly. Events are never deleted. The event list shows the latest 50 events and pages to older ones.
- The independent notification path is a local LED and buzzer on the ESP32, commanded by the host over USB. The sketch drives the onboard RGB LED (GPIO48 by default) as the alarm LED and GPIO7 for the buzzer. The LED lit as commanded on 20 November 2026. No buzzer is connected now. GPIO7 and the buzzer polarity are not checked on hardware.
- When the USB link is down the host cannot command the LED or buzzer. The dashboard then shows the alarm as unreachable. After 30 s without a valid command the board blinks the LED and keeps the buzzer in its last state. The blink was seen on the bench on 20 November 2026. The buzzer part is not checked.
- The dust estimate uses a typical sensitivity and an automatic baseline. It is not PM2.5, an official index, or a calibrated concentration. It is not checked against a reference instrument.
- The air-quality index is Bosch's estimate. It is not a gas concentration and is not checked against a reference.

## Decisions (15 November 2026)

- Board: ESP32-S3 with an N8R2 module. Correction, 17 November 2026: esptool shows the connected board is an N16R8-type module (16 MB flash, 8 MB embedded PSRAM), not an N8R2. Pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7. Implemented and compiled on 15 November; not checked on hardware. Correction, 20 November 2026: the dust pins were swapped to match the wiring: dust analog input GPIO5, dust LED drive GPIO4. Correction, 20 November 2026: the alarm LED is now the onboard RGB LED (GPIO48 by default, not checked on the board), not GPIO6.
- Completion work builds on this branch. The dust sensor stays.
- Primary dashboard viewer: a caregiver at a desk screen.
- Notification: a local ESP32 buzzer and LED. Host side and sketch wiring implemented on 15 November; not checked on hardware. The buzzer sounds for limit alerts only (patient limits and the air-quality and dust system limits). System faults light the LED and show on the dashboard without sound.
- A dashboard "Silence alarm" button stops the buzzer for that alert. The LED stays on until the condition clears. The silence is logged. A new alert sounds again.
- Buzzer part: a 3-pin buzzer module driven from one GPIO (GPIO7 on the ESP32-S3). The alarm LED uses GPIO6. Correction, 20 November 2026: no external alarm LED and no buzzer are connected. The alarm LED is the onboard RGB LED (GPIO48 by default, not checked on the board). GPIO7 drives nothing for now.
- Raw readings will be kept for 7 days. Event history is kept regardless. Implemented on 15 November.
- The dashboard will be redesigned. The current page is a first draft. Implemented on this branch: five pages (Overview, Trends, Events, Patient limits, System), checked with the simulator and screenshots, not on hardware.
- Air quality is shown as Bosch's index and dust as an estimated concentration, both with words; their limits are system setup; the profile has a short label. Implemented on 15 November with tests and the simulator only. This replaces the earlier raw-signals-only rule.

## Remaining work

1. Identify the ESP32-S3 board model. Run the rest of the hardware checklist in the [firmware guide](firmware/README.md). The board was flashed and the serial link and alarm protocol were checked on 17 November 2026 without sensors.
2. Obtain the hardware and complete physical BME680, dust, and USB checks.
3. Check camera capture and the occupancy detector with seated, lying, and occluded people.
4. Agree on real patient limits for any demonstration.
5. Check the local alarm on the real board: GPIO7 free, buzzer polarity once a buzzer is connected and whether it needs a tone. Done on 20 November 2026: the replies, the onboard RGB LED (off or white as commanded) and the link-lost LED blink. The host side, the sketch wiring and the "Silence alarm" control exist.
6. Check the five-page dashboard with the real board and sensors. It is checked only with the simulator and screenshots.
7. Check the Bosch word bands and the Sharp sensitivity against the datasheets. (Saving the BSEC calibration state is decided and implemented: see item 11.)
8. Demonstrate the complete system with actual hardware.
9. Dust disconnect: the host now applies a floor rule. A dust voltage below `dust.disconnected_below_mv` (100 mV), a 0 mV reading, or the board's `dust_input_at_zero` report all count as "no reading". With no reading at or above the floor for the sensor timeout (120 s) the dust status is "not connected" and the dust fault is raised. Bench check pending: with the 2:1 divider wired and no sensor, confirm that the input reads below 100 mV (on 17 November, with nothing wired, the floating input read about 870 to 930 mV) and that a connected sensor reads above it.
10. Online access: send a signed-in control request (save limits, silence, acknowledge) through a real tunnel. Online access is implemented. One real tunnel run on 19 November 2026 loaded the pages and refused control requests without sign-in.
11. BSEC state save and restore on the board. It is compiled and host-tested only. Flash the new firmware (the board still runs `1c74995`). Then run to IAQ accuracy 3, wait for a save, power-cycle, and confirm the restore.
12. Open items from the 20 November 2026 bench check (firmware `1c74995`, cable on the CH343 port):
    - Dust: FAIL. Every reading was `dust_input_at_zero` (GPIO5 reads 0 V). The code reads the right pin. The cause is likely the wiring or the sensor power. Check with a meter: Vcc 5 V on sensor pins 6 and 1, ground on pins 2 and 4, Vo on pin 5, and the divider midpoint to GPIO5.
    - Gas: SUSPECT. `gas_ohms` was 12917166.00 in every reading for about 15 minutes. Inference, not measured: by the BME68x formula this is a raw gas ADC of 0 at range 0 with the valid bits still set. The gas part may be faulty or not genuine. The IAQ values are then not meaningful.
    - Not done: the start-up line after a reset-button press (the window was missed), and the 10-minute gas run.

Follow the course requirements and approved project decisions.
Preserve the existing environment and required dependencies.
Do not recreate the removed setup installer.
Ask before adding unspecified dependencies, algorithms, services, or hardware procedures.
Use the [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for verified reference behavior.
The original course PDFs and VIGIL archive are not included in this repository.
