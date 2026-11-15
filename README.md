# Room Environment Safety Control - Project 8

This project monitors one room using a laptop, an ESP32 board, a BME680, a Sharp dust sensor, and a camera for occupancy.
The selected board changed to an ESP32-S3 on 15 November 2026. See [Selected hardware](#selected-hardware).

## Current status

This branch adds the room software: SQLite storage, patient limits, sustained-breach alerts, camera occupancy, a local dashboard, and a Sharp dust sensor path.
These parts exist in software. They are verified only by automated tests and the simulator.
No physical ESP32, BME680, dust sensor, or camera check has taken place.
The local alarm is implemented on the host and in the sketch. It is checked only with the simulator, host C++ tests and a compilation for the ESP32-S3. No LED or buzzer has been driven. The dashboard redesign is decided but not implemented. 7-day reading retention is implemented.
The [local alarm design](docs/superpowers/specs/2026-11-15-local-alarm-design.md) defines the alarm levels, the serial command, silence and reachability.
The [dashboard data contract](docs/superpowers/specs/2026-11-15-dashboard-data-contract-design.md) defines the dashboard response, alert text, events, timing settings, and retention.

Read the [15 November verification record](reference_files/LINUX_VERIFICATION_2026-11-15.md) for the current software results.
Read the [8 November verification record](reference_files/LINUX_VERIFICATION_2026-11-08.md) for the earlier virtual-serial and compilation results.

| Check | Recorded result |
|---|---|
| Python test suite, this branch | 462 passed, exit code 0, no skips, also with `-W error` (15 November, after the ESP32-S3 port). |
| Python test suite, `main` | 301 passed, exit code 0 (15 November). |
| Firmware message formatting | Built with no warnings and passed (15 November). |
| Firmware alarm command core | `firmware/tests/test_alarm_command.cpp` built with `g++ -std=c++11 -Wall -Wextra -pedantic` with no warnings and passed (15 November, after the ESP32-S3 port). |
| Firmware dust sample rule | `firmware/tests/test_sharp_dust_limits.cpp` built the same way with no warnings and passed (15 November). |
| Local alarm demo | With `--demo`, the simulated board confirmed level 2 during the limit alert, level 1 after "Silence alarm", and level 0 after the alert ended (15 November). No LED or buzzer was driven. |
| Software demo | Monitor and dashboard ran together. The simulated limit alert started and ended as expected (15 November). |
| Complete firmware compilation | The current sketch, with dust code and alarm, compiled for the ESP32-S3 N8R2 with `CDCOnBoot=default` and `CDCOnBoot=cdc`, no warnings (15 November). Compilation only; nothing was flashed. |
| Missing communication | Monitor raised the communication alert and retained previous measurements (8 November). |
| Communication recovery | Fresh readings resumed. The outstanding communication alert remained active (8 November). |
| Repeated sensor errors | Communication stayed active while the sensor alert became active (8 November). |
| Sensor-error recovery | A valid reading cleared the sensor alert (8 November). |
| Simulated gas-status changes | Warm-up and calibration labels changed as expected (8 November). |

The runtime checks used a virtual serial port, a simulator, and artificial messages.
They do not establish physical sensor accuracy, calibration, camera detection, USB behavior, or room safety.

## Start here

- [Human guide](README_HUMAN.md): project purpose and behavior.
- Verification records: [8 November](reference_files/LINUX_VERIFICATION_2026-11-08.md) and [15 November](reference_files/LINUX_VERIFICATION_2026-11-15.md): completed checks and remaining work.
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

The board is an ESP32-S3 with an N8R2 module (8 MB flash, 2 MB PSRAM). The user selected it on 15 November 2026. It supersedes the DOIT ESP32 DevKit V1.
Pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7.
The firmware uses these pins. They are not checked against the physical board. The exact development board model is not identified.
The user confirmed a 3.3 V sensor supply.
The board header stores the pins, buzzer polarity, serial speed, supply selection, and reporting intervals.
The chip check rejects every chip except the ESP32-S3. It cannot identify the physical development board.
The firmware compiles with ESP32 core 3.3.12, BSEC2 1.10.2610 and BME68x 1.3.40408. The [firmware guide](firmware/README.md) has the build commands, the serial (CDC On Boot) choice and the hardware checklist.
Nothing has been flashed to an ESP32-S3. No ESP32-S3 has been connected.

The sketch uses Bosch BSEC2 and Bosch BME68x.
The Python requirements do not install Arduino libraries.
Upload, breakout wiring, actual pressure units, and physical readings remain unchecked.

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
| dust.py | Classifies Sharp dust records and reports dust status. Calculates a dust estimate only with user calibration. |
| dashboard.py | Serves the local dashboard on 127.0.0.1. Reads SQLite. Saves patient limits, acknowledgment requests and alarm silence requests. |
| alarm.py | Decides the local alarm level (0 off, 1 LED, 2 LED and buzzer), silence, and whether the board confirmed the level. No I/O. |
| templates/, static/ | Dashboard page, script, and style. |
| `settings.py` | Loads both YAML settings files and checks their values. |
| config/runtime.yaml | Stores host polling, retry, and fault-check intervals, the reading gap, dashboard staleness and refresh, camera interval, reading retention, and the alarm confirmation timeout. |
| config/alerts.yaml | Stores the communication and sensor-error timeouts. |
| communication_fault.py | Tracks missing communication and alert acknowledgment. |
| sensor_fault.py | Tracks repeated sensor errors and valid-reading recovery. |
| `measurements.py` | Checks measurements and retains the last complete reading and its receipt time. |
| serial_parser.py | Classifies readings, errors, incomplete records, and ignored input. |
| `monitoring_state.py` | Stores the combined state and applies incoming messages to readings and fault trackers. |
| gas_readiness.py | Interprets reported Bosch warm-up and calibration status. |
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
| firmware/alarm_command.h | Parses `ALARM,<0|1|2>` commands with a fixed buffer, reads `Serial` with a byte bound, maps the level to LED and buzzer, and formats the reply. |
| firmware/tests/test_alarm_command.cpp | Tests `alarm_command.h` with g++ on Linux. |

## Run the software demo

Run both entry points in your existing project environment, in separate terminals:

```text
python monitor.py --demo
python dashboard.py --demo
```

Open http://127.0.0.1:5000. The demo uses its own SQLite database. It simulates an occupied room, BME680 readings, and Sharp dust voltage at three-second intervals. On a fresh demo database the temperature crosses the example limit at 18 seconds, raises a caregiver alert at about 27 seconds, and returns to range at about 60 seconds. Patient limits are saved beside the database in a `.profile.yaml` file. Valid changes take effect on the next monitor update. If the file is invalid, the monitor keeps its last valid profile and shows a profile error. The example values apply only to the simulator.

The dashboard refreshes every ten seconds. It shows the last monitor update, sensor readings, occupancy, 24-hour trends, caregiver alerts with limit, value, and duration, pending breaches, the latest 50 events, a patient limits form, the communication acknowledgment control, and the local alarm state with a "Silence alarm" button. Trend points are one-minute averages with minimum and maximum. Gas resistance is charted but has no limit. `GET /api/room` returns all of this in one response. The dashboard accepts requests only for `localhost` and `127.0.0.1` and rejects cross-site form posts. The dashboard can be closed while monitoring continues. Readings and event history stay in local SQLite files. The 24-hour chart is a display window. The monitor deletes readings older than 7 days. Events are kept.

On the real serial path, supply the existing serial port argument and the `--camera` index option when physical testing resumes. Both programs accept `--db` and must use the same file. OpenCV checks at one-minute intervals. A detected person gives occupied status. Failed capture, no detection, and expired observations give unknown status. Frames are processed locally and never saved. Physical validation is still pending.

## Sharp dust sensor

The experimental GP2Y1010AU0F path adds independent dust voltage and status. A stale dust report raises a dust fault. No dust limit exists. `--dust-baseline-mv` and `--dust-sensitivity` together enable a user-calibrated estimate. See [wiring, plan, calibration, and verification](docs/SHARP_DUST_INTEGRATION.md). Its wiring table uses the superseded DOIT pins. The decided ESP32-S3 dust pins are GPIO4 (analog input) and GPIO5 (LED drive). Firmware compilation and hardware timing remain pending.

## Local alarm

The host commands a local alarm on the ESP32 over the serial link: `ALARM,0` (off), `ALARM,1` (LED only) or `ALARM,2` (LED and buzzer). The board replies `{"type":"alarm","state":<n>}` after applying a command.

- Level 2: at least one patient-limit alert that has not been silenced.
- Level 1: a silenced limit alert, or an active communication, BME680 or dust alert. The buzzer stays off.
- Level 0: otherwise. The board starts at level 0.

The host sends on every change and again at each fault check, so a board reset is corrected. The dashboard shows the alarm as confirmed, pending, or unreachable (port not connected, write failed, or no reply within `alarm_confirm_timeout_s`, default 2 seconds). "Silence alarm" stops the buzzer for the limit alerts shown. The LED stays on. The monitor applies the silence at its next fault check and logs it. A new limit alert sounds again. Alarm failures never delay readings, fault checks or the status.

The sketch reads commands without blocking, at most 64 bytes per loop pass, drives GPIO6 (LED) and GPIO7 (buzzer module) with a steady level, and replies after each command and once at start-up. The buzzer polarity is one constant, `ROOM_BUZZER_ACTIVE_HIGH`, default active high, not verified. In the demo the simulated board echoes each command. No LED or buzzer has been driven.

## Behavior to preserve

The monitor loads technical settings at startup.
The initial communication wait begins when the monitor starts.
Recognized readings and sensor errors both count as communication.
Incomplete readings retain the previous complete measurements and their original receipt time.
Ignored input does not reset communication timing.
Alarm replies do not count as communication. The host asks for them, so they must not hide a stopped measurement stream.

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
Firmware configuration commands and calibration-state storage remain future work.

## Known limitations

- The occupancy detector is OpenCV's default people detector, trained on upright pedestrians. It can miss seated, lying, or occluded people. Unknown occupancy suppresses patient-limit alerts. It has not been checked with a camera.
- In serial mode without `--camera`, occupancy is always unknown, so patient-limit alerts never start.
- Readings older than 7 days are deleted hourly. Events are never deleted. The event list shows the latest 50 events and pages to older ones.
- The independent notification path is a local LED and buzzer on the ESP32, commanded by the host over USB. The sketch drives GPIO6 and GPIO7. Pins and buzzer polarity are not checked on hardware.
- When the USB link is down the host cannot command the LED or buzzer. The dashboard then shows the alarm as unreachable. A firmware fallback is an open decision.
- Dust output is a raw sensor voltage. It is not PM2.5, AQI, or a calibrated concentration.

## Decisions (15 November 2026)

- Board: ESP32-S3 with an N8R2 module. Pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7. Implemented and compiled on 15 November; not checked on hardware.
- Completion work builds on this branch. The dust sensor stays.
- Primary dashboard viewer: a caregiver at a desk screen.
- Notification: a local ESP32 buzzer and LED. Host side and sketch wiring implemented on 15 November; not checked on hardware. The buzzer sounds for patient-limit alerts only. System faults light the LED and show on the dashboard without sound.
- A dashboard "Silence alarm" button stops the buzzer for that alert. The LED stays on until the condition clears. The silence is logged. A new alert sounds again.
- Buzzer part: a 3-pin buzzer module driven from one GPIO (GPIO7 on the ESP32-S3). The alarm LED uses GPIO6.
- Raw readings will be kept for 7 days. Event history is kept regardless. Implemented on 15 November.
- The dashboard will be redesigned. The current page is a first draft.

## Remaining work

1. Identify the ESP32-S3 board model. Run the hardware checklist in the [firmware guide](firmware/README.md) before and after the first flash.
2. Obtain the hardware and complete physical BME680, dust, and USB checks.
3. Check camera capture and the occupancy detector with seated, lying, and occluded people.
4. Agree on real patient limits for any demonstration.
5. Check the local alarm on the real board: GPIO6 and GPIO7 free, buzzer polarity and whether it needs a tone, LED resistor, replies. The host side, the sketch wiring and the "Silence alarm" control exist.
6. Redesign the dashboard.
7. Demonstrate the complete system with actual hardware.

Follow the course requirements and approved project decisions.
Preserve the existing environment and required dependencies.
Do not recreate the removed setup installer.
Ask before adding unspecified dependencies, algorithms, services, or hardware procedures.
Use the [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for verified reference behavior.
The original course PDFs and VIGIL archive are not included in this repository.
