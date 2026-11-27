# Room Environment Safety Control

**Linux checks recorded:** See the [8 November verification record](reference_files/LINUX_VERIFICATION_2026-11-08.md), the [15 November verification record](reference_files/LINUX_VERIFICATION_2026-11-15.md) and the [17 November verification record](reference_files/LINUX_VERIFICATION_2026-11-17.md).
On 8 November the user completed Python test execution, firmware formatting, compilation, and the listed virtual-serial scenarios.
On 15 November the full suite on this branch reported 317 passed, and the software demo ran without errors. After the dashboard data contract it reported 401 passed. After the local alarm host side it reported 461 passed, also with `-W error`. After the ESP32-S3 port it reported 462 passed, also with `-W error`, and the sketch compiled for the ESP32-S3.
On 17 November the ESP32-S3 was flashed. The serial link and the alarm protocol were checked with no sensors attached.
On 20 November the board, still on firmware `1c74995`, was checked on the bench with the BME680, the dust sensor and the onboard RGB LED. The alarm replies, the LED, the link-lost blink, the dust fault through the monitor, the dashboard pages and the BME680 temperature, humidity and pressure passed. Dust failed (every reading `dust_input_at_zero`) and the gas reading is suspect. See the [firmware hardware checklist](firmware/README.md#hardware-checklist).
On 25 November the dust fault was found and fixed: the dust LED is wired directly to GPIO4 and turns on when GPIO4 is LOW. With firmware `49029f2` the dust sensor reads 892.7 to 1135.0 mV. The gas reading fails at the Bosch heater temperature; the fix is an open decision. See the [25 November verification record](reference_files/LINUX_VERIFICATION_2026-11-25.md) and the main [README](README.md#hardware-and-status-25-november-2026). Where older lines below say that dust fails, the 25 November result replaces them.
Buzzer and camera operation remains unverified.
On 23 November the full suite on branch `feature/bsec-state` reported 752 passed, after the BSEC state save.
The 8 November Linux build used ESP32 core 3.3.12, Bosch BSEC2 1.10.2610, and Bosch BME68x 1.3.40408 for the DOIT board. It did not include the dust code.
These records supersede earlier pending-test statements in historical preparation notes and design checklists.


## Guide for people

This guide explains the project for students, reviewers, and future team members.
It describes the project purpose, current code, and planned behavior.
It contains no instructions for an AI assistant.

**Current status:** The repository contains the monitor, SQLite storage, patient-limit rules, camera occupancy, a local dashboard, and a Sharp dust path.
These parts exist in software. Automated tests and a simulator verify them. On 17 November 2026 the monitor ran for 60 s against the flashed board with no sensors attached. On 20 November 2026 the monitor and dashboard ran against the board on the bench with the BME680 and the dust sensor wired. BME680 temperature, humidity and pressure passed. On 25 November 2026, with firmware `49029f2`, the dust sensor passed (892.7 to 1135.0 mV) and the dust estimate became current. The gas reading fails at the Bosch heater temperature (open decision). The Bosch index reached accuracy 3, but it has no meaning while the gas reading is stuck. The BME680 dropped off the I2C bus twice; the firmware bus restart recovered it once. No part has run with a real camera.
The local alarm is implemented on the host and in the sketch. It is checked with the simulator, host C++ tests, a compilation for the ESP32-S3, and the board's serial replies to `ALARM` commands (17 November). On 20 November the onboard RGB LED was off or white as commanded. On 25 November the monitor raised the BME680 alert and the board confirmed level 1. No buzzer has been driven. The dashboard redesign is implemented on this branch as five pages: Overview, Trends, Events, Patient limits and System. It is checked with the simulator and screenshots, and on 20 November with the board (pages and `/api/room` HTTP 200). 7-day reading retention is implemented.
Opt-in view-only online access is implemented (19 November): a Cloudflare quick tunnel to a second, view-only origin, with a password for controls. One real tunnel run on 19 November 2026 loaded the pages and refused control requests without sign-in. On 20 November 2026 a signed-in user saved patient limits, silenced the alarm and acknowledged a communication alert through a real quick tunnel. The same requests without sign-in were refused.

## What the project does

The project aims to monitor the environment of an occupied room.
Python compares temperature, humidity, and pressure with limits in the patient profile.
The dashboard shows measurements, occupancy, faults, and alerts.
The project supplies no patient limits. The demo example limit applies only to the simulator.

The prototype uses one room, one ESP32-S3 board, one BME680, one Sharp dust sensor, and one camera.
The board is an ESP32-S3 with 16 MB flash and 8 MB embedded PSRAM, an N16R8-type module. esptool read these facts from the connected board on 17 November 2026. The documents assumed an N8R2 module until then. The user selected the ESP32-S3 on 15 November 2026. It supersedes the DOIT ESP32 DevKit V1.
The pins are I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO5, dust LED drive GPIO4, and buzzer module GPIO7.
The alarm LED is the onboard RGB LED (GPIO48 by default). It lit white as commanded on the bench on 20 November 2026. No buzzer is connected now, so GPIO7 drives nothing.
The firmware uses these pins. On 20 November 2026 the BME680 readings arrived over GPIO8 and GPIO9 and the onboard RGB LED worked. On 25 November 2026 the dust pins were confirmed: GPIO4 drives sensor pin 3 directly (LOW turns the LED on), and GPIO5 reads the sensor through the divider. GPIO7 is not checked. The exact development board model is not identified.
The user confirmed a 3.3 V sensor supply.
The firmware configuration uses that value.
The firmware compiles for the ESP32-S3. It was flashed on 17 November 2026. The board answered the alarm commands over USB. No sensor, LED, or buzzer was attached.
See the [firmware guide](firmware/README.md) for the remaining setup checks.
Expansion to several rooms remains a future option.
The name does not imply automatic control of fans, heaters, or other equipment.
The project does not yet define those control functions.

## Hardware and software roles

| Part | Role | Current state |
|---|---|---|
| BME680 | Measures temperature, humidity, pressure, and gas resistance | Experimental firmware exists. On 20 November 2026 temperature, humidity and pressure came every 3.000 s with plausible values. Gas is suspect: `gas_ohms` stayed at 12917166.00 for about 15 minutes. On 25 November 2026 a heater sweep showed real gas values at 200 to 260 °C. Most readings fail at 280 and 300 °C, and all fail at 320 °C. The Bosch index does not work with this module as it is (open decision). It reached accuracy 3 in a monitor run on 25 November, but on a stuck gas reading, so it has no meaning. The module dropped off the I2C bus twice that day. |
| Sharp GP2Y1010AU0F | Supplies a raw dust voltage | Experimental firmware exists. On 20 November 2026 every reading was `dust_input_at_zero` (the input read 0 V). Cause, found on 25 November 2026: the LED polarity. With firmware `49029f2` the sensor reads 892.7 to 1135.0 mV. |
| ESP32-S3 | Reads the sensors, drives the local alarm and sends records through USB serial | Flashed on 17 November 2026. Serial link and alarm replies checked without sensors. On 20 November 2026 (firmware `1c74995`) the onboard RGB LED, the link-lost blink and the BME680 input were checked on the bench. Since 25 November 2026 it runs `49029f2`: readings and dust pass; the I2C bus restart recovered the BME680 once and failed the second time. No buzzer is connected, so it is not checked. |
| Laptop | Runs the monitor, rules, storage, and dashboard | Implemented in software. Verified by tests and the simulator. On 20 November 2026 the monitor ran against the board on the bench: it raised the dust fault at 120 s and the board confirmed level 1. All five dashboard pages and `/api/room` returned HTTP 200. |
| Camera | Supplies frames for occupancy detection | OpenCV people detector implemented. Not checked with a camera. |
| Dashboard | Shows room status, trends, events, limits and the local alarm state, and accepts communication acknowledgments and alarm silence requests | Five pages implemented: Overview, Trends, Events, Patient limits and System. Checked with the simulator and screenshots, and on 20 November 2026 with the board (pages and `/api/room` HTTP 200). |
| Local alarm | Buzzer and LED on the ESP32 | Host side and sketch implemented. Checked with the simulator, host C++ tests and a compilation. Alarm LED: the onboard RGB LED (GPIO48 by default), off or white as commanded on the bench on 20 November 2026. Buzzer GPIO7: no buzzer is connected now. Buzzer polarity and GPIO7 not checked on the board. |

The laptop performs the main project logic.
The ESP32 provides the connection to the environmental sensor.
This prototype does not use an NVIDIA Jetson Nano.

## How measurements move through the system

1. The ESP32 reads the BME680.
2. The ESP32 sends a JSON record through USB serial.
3. Python classifies the record and checks its measurement fields.
4. Python updates communication status and sensor status.
5. Python retains the last complete reading and its measurement time.
6. Python applies the patient limits when the reading is fresh and the room is occupied.
7. Python stores the status, readings, and events in SQLite.
8. The dashboard reads SQLite and shows the resulting status.

All eight steps exist in source. Steps 3 through 8 ran with simulated input. Real operation still needs checks.
Monitoring stays independent from dashboard refreshes. Closing the dashboard does not stop monitoring.

## Monitor

The monitor connects serial input to the parser, fault trackers, patient rules, and storage.
It requires an explicitly selected ESP32 port, or `--demo` for simulated input.
It retries that port after connection errors.
A retry does not reset the two-minute communication timer.
Opening the port can reset some ESP32 boards.
On this board, opening the CH343 port does not reset it (checked on 20 November 2026).

The terminal shows JSON records with the last complete reading, its age, and its receipt time.
The calendar time is an estimate based on the computer clock at startup.
It is not the time when the ESP32 measured the room.
Old readings keep their original receipt time.
Gas warm-up and calibration show unavailable when communication or current measurements fail.

Fault checks continue during silence, even if the port cannot open.
The default check interval is five seconds.
Output can also change when a new record arrives.
Each published record also goes to SQLite for the dashboard.

The monitor checks the camera when `--camera` is given. Without it, occupancy is unknown in serial mode, so patient-limit alerts never start.
The monitor reads acknowledgment and alarm silence requests from the dashboard at each fault check.
The independent notification path is a local LED and buzzer on the ESP32. The monitor sends `ALARM,<level>` over USB serial and the board confirms it. Level 2 (LED and buzzer) means an unsilenced patient-limit alert. Level 1 (LED only) means a silenced limit alert or a communication, BME680 or dust alert. Level 0 is off. The dashboard shows whether the board confirmed the level. The sketch acts on the command: it sets the alarm LED and the buzzer output and replies. On 20 November 2026 the board replied to `ALARM,0`, `ALARM,1` and `ALARM,2`, and the onboard RGB LED was off or white as commanded. No buzzer is connected, so the buzzer output is not checked.
The listed automated, virtual-serial, and simulator checks completed on Linux. Real ESP32 and sensor operation was partly checked on the bench on 20 and 25 November 2026: the alarm path, the LED, the BME680 temperature, humidity and pressure, and the dust sensor passed. The gas reading fails at the Bosch heater temperature, and the buzzer is not connected.

## Software demo

Run both entry points in the existing project environment, in separate terminals:

```text
python monitor.py --demo
python dashboard.py --demo
```

Open http://127.0.0.1:5000. The demo uses its own SQLite database. It simulates an occupied room, BME680 readings, and Sharp dust voltage at three-second intervals.
On a fresh demo database the temperature crosses the example limit at 18 seconds. A caregiver alert starts at about 27 seconds. The temperature returns to range at about 60 seconds.
The example values apply only to the simulator. They are not patient limits.

## Online access (opt-in, view-only)

Monitoring, alerts and the local alarm never depend on the internet. Online access starts only on request. Install `cloudflared` separately, then set the online password once (it is stored as a hash in the git-ignored `config/online_secret.yaml`):

```text
python dashboard.py --set-password
python dashboard.py --online
```

`--online` also serves a view-only origin on 127.0.0.1:5001 and starts a Cloudflare quick tunnel to it. The random `trycloudflare.com` link changes on each start and appears on the System page (with Copy link) on this computer. Anyone with the link can view. Saving limits, silencing and acknowledging online need the password; on this computer they need no sign-in. Without a password or without `cloudflared`, the local dashboard still runs and the System page says why online access is off or failed. Stop online access by stopping `dashboard.py`. Port, program path and sign-in lifetime are in `config/runtime.yaml`. Design: [online access](docs/superpowers/specs/2026-11-19-online-access-design.md).

## Patient limits and occupancy

The patient profile is a YAML file beside the database, for example `room.profile.yaml`.
It holds a lower and upper limit for each enabled measurement and one sustained duration.
Temperature, humidity, and pressure can have patient limits. Gas resistance and dust voltage cannot.
The profile can also hold a short label, for example "Bed 3". It has at most 40 characters and no line breaks. It is not a patient name.
Air quality and dust have system limits instead. They are set in `config/system.yaml`, not on the dashboard.
The dashboard form saves the profile. Valid changes take effect on the next monitor update.
An invalid file keeps the last valid profile and raises a profile fault.

| Condition | Behavior |
|---|---|
| A reading is outside a limit | Start the sustained timer at that reading. |
| The breach lasts the sustained duration | Start a patient-limit alert and log it. |
| One reading returns inside the limits | End the alert and log it with the limit, value, and duration. |
| Occupancy is unknown | Clear the timers. No patient-limit alert can start. An active alert ends with a logged reason. |
| The last reading is older than the reading-gap limit (six seconds), or two readings are further apart | Restart the timer. |
| The profile changes | Restart all timers. |

The camera check runs every 60 seconds by default. It uses OpenCV's default people detector.
A detected person gives occupied status. No detection, failed capture, and an observation older than the interval plus 5 seconds give unknown status.
There is no absent status. Frames stay in memory and are never saved.
The detector is trained on upright pedestrians. It can miss seated, lying, or occluded people. It has not been checked with a camera.

Fault alerts for communication, the BME680, dust, and the profile do not depend on occupancy.
Alert text states the measurement, direction, configured limit, value, and duration. A breach that has not yet lasted the sustained duration shows as pending.
An alert that stops for another reason logs that reason: changed limits, unknown occupancy, or readings that are no longer current.

## Measurements and their meaning

| Field | Meaning | Unit |
|---|---|---|
| `temp_c` | Temperature | Degrees Celsius |
| `humidity_pct` | Relative humidity | Percent |
| `pressure_hpa` | Air pressure | Hectopascals |
| `gas_ohms` | Gas sensor resistance | Ohms |

The current validator requires all four fields as finite numbers.
It rejects missing values, numeric text, Boolean values, and nonfinite numbers.
This check establishes the record structure.
It does not establish patient safety or measurement accuracy.

Gas resistance is not a calibrated air quality index, carbon dioxide concentration, or carbon monoxide concentration.
The current firmware reports raw resistance.
The project still needs an agreed method for gas evaluation.

## Communication faults and sensor faults

Communication status answers: Does Python receive recognized messages from the ESP32?
Sensor status answers: Do those messages contain usable measurements?
A recognized error message proves communication, but it does not provide a fresh measurement.

The following table describes the agreed behavior.
The router now connects input classification, retained readings, and both fault components.
The new terminal loop calls this router and checks faults during silence.

| Event | Agreed behavior |
|---|---|
| No recognized message after program startup | Wait two minutes before raising a communication alert. |
| Recognized messages stop | Raise a communication alert after two minutes of silence. |
| A recognized error message arrives | Reset the communication timer and start or continue the sensor error period. |
| Sensor errors continue | Raise a sensor alert after two minutes of active error time. Repeated errors do not restart that period. |
| A valid measurement arrives | Reset the sensor error period and automatically clear the sensor alert. |
| Communication fails during sensor errors | Pause the sensor error period when communication times out. The communication tracker handles the outage. |
| Error messages resume | Continue the remaining sensor error period. |
| Unreadable or unknown input arrives | Ignore that input. Continue checking for communication timeout. |

Communication recovery does not dismiss an outstanding communication alert.
A person must acknowledge that alert on the dashboard.
The dashboard shows the acknowledgment button only after contact recovers and while the monitor status is current.
The monitor applies the acknowledgment at its next fault check. The event history records the acknowledgment and the cleared alert as separate entries.
The underlying tracker also supports acknowledgment during an outage: it dismisses the alert and starts another two-minute wait.
The dashboard does not offer that action.
Acknowledgment does not change the actual last-contact time.

## Missing or incomplete readings

Before the first complete reading, the state contains no values or measurement time.
The initial status is waiting for the first measurement.
Recognized errors change the input status even when no complete reading exists.
The normal communication timeout still starts immediately.

An incomplete reading must not replace the last complete reading.
The dashboard shows the previous values and the time of the last BME680 reading.
It labels the latest input status.
When the monitor status is older than the staleness limit (15 seconds), the dashboard labels the values as retained.
The dashboard must not present retained values as fresh measurements.

A recognized incomplete reading counts as communication and as a sensor error.
The sensor alert still waits for the configured error duration.
The parser already identifies incomplete readings.
The new state and router modules retain readings and update the fault trackers.

## Gas warm-up and calibration

The selected design uses status reports from Bosch BSEC software.
Python does not declare readiness after a fixed waiting period.
The new Python module can read these reports.
The new firmware source prepares these reports.
Compilation succeeded on Linux. On 20 November 2026 the BME680 ran on the bench, but the gas reading was stuck (the same `gas_ohms` value for about 15 minutes). On 25 November 2026 a heater sweep showed that the gas reading fails at the Bosch heater temperature. In a monitor run the same day the Bosch accuracy went to 2 and then 3. The dashboard then shows the index as current. The index has no meaning while the gas reading is stuck (open issue, no fix chosen). See the [25 November verification record](reference_files/LINUX_VERIFICATION_2026-11-25.md).
The earlier firmware reports no BSEC status, so Python shows unknown until the new firmware supplies valid reports.

BSEC reports initial stabilization and stabilization after power-on.
A zero flag means stabilization continues.
Both flags must equal one for the warmup_complete status.
This status does not prove that calibration finished or that the room is safe.

A separate IAQ accuracy value describes the calibration state.
The labels are stabilizing, calibration_required, calibrating, and calibrated.
These labels describe the algorithm report.
They do not certify measurement accuracy.

Missing or invalid status information produces unknown status.
A complete environmental reading remains usable even when its gas metadata is unknown.
Expected warm-up does not start a sensor error period.
Actual communication loss or measurement errors retain their normal fault rules.
Current gas status becomes unavailable when communication times out or the latest input contains measurement errors.

The program will continue during gas warm-up.
Temperature, humidity, and pressure still need their own validity and settling checks.
On 15 November 2026 the user decided that air quality is shown as Bosch's BSEC index. This replaces the earlier rule that gas resistance is a raw signal only.
The firmware sends the index with its accuracy. The page shows it with a word band and the label "Bosch estimate".
When Bosch's accuracy is 0 or 1 the page shows "calibrating" and no value. Bosch's library describes 0 as run-in ongoing and 1 as low accuracy.
The word bands are commonly cited Bosch bands. No Bosch document on this machine lists them, so they are unverified.
Raw gas resistance stays stored and shown as a system detail.

BSEC learns the room's normal air over hours. The learned calibration state lives in the board's RAM, so a reset or power cut loses it. Since 20 November 2026 the laptop keeps a copy (user decision).
The board sends its state only when the IAQ accuracy is 3: the first time after start, then every 6 hours while the accuracy stays 3. Six hours is Bosch's standard interval, from Bosch's example sketch `basic_config_state.ino` (`STATE_SAVE_PERIOD`, 360 minutes).
The monitor writes the state to a file next to the database, for example `room.bsec_state.json`. It writes a temporary file first and then renames it.
At start the board asks the laptop for the state and waits up to 10 seconds. The monitor sends the saved state if the file exists and the BSEC version matches. Otherwise it sends `BSEC_STATE,NONE` and logs why. Without a reply the board starts without a state.
If the board cannot read its state, it reports `bsec_state_save_failed` and tries again after 60 seconds. The monitor logs this as an event, not as a sensor error. The monitor also logs this event when the laptop cannot write the state file. The event message tells the two causes apart.
The System page shows "Bosch calibration saved: <time>, accuracy 3" or "not saved yet", and the result of the last restore. The Events page lists these events under "Bosch calibration".
This is compiled and host-tested. The board has run firmware with this feature since 25 November 2026. On 25 November the board reached accuracy 3 and saved its state (`bsec_state_saved`, 02:41:50), but on a stuck gas reading. After an I2C bus restart it restored the state from its RAM copy. A restore from the laptop file after a board start is not checked.

The user selected three-second BSEC low-power sampling.
The new firmware source uses that mode.
BSEC controls when the sensor acquires data.
The firmware sends each new measurement once.
Failures produce error messages instead of repeated old measurements.
The sensor supply is confirmed as 3.3 V.
The firmware compiled for the ESP32-S3 with the installed Bosch libraries and ESP32 board package. Hardware operation still needs checks.

Initial sensor conditioning remains separate from this software status handling.
See the [BSEC integration design](docs/superpowers/specs/2026-11-08-bsec-status-design.md) for the protocol and manufacturer references.

## Sharp dust sensor

The experimental GP2Y1010AU0F path adds an independent dust voltage and status.
Dust records count as communication. They do not replace BME680 readings.
BME680 silence for the sensor-error timeout while dust continues raises the BME680 alert.
Missing dust reports for the sensor-error timeout raise a dust alert.
The dashboard shows the raw voltage and its 24-hour trend as system details.
On 15 November 2026 the user decided that dust is shown as an estimated concentration in µg/m³ with a word level and the label "estimate".
The estimate uses Sharp's typical sensitivity, 0.5 V per 0.1 mg/m³. It is not checked against the datasheet on this machine.
The clean-air baseline is the lowest voltage of the last 24 hours. No estimate is shown until 10 minutes of unbroken fresh records exist.
A dust fault, a gap of more than six seconds, or a monitor restart starts the baseline again. The estimate is never negative.
The word levels (low, raised, high) are project display defaults, not official categories or health standards.
See [wiring, plan, calibration, and verification](docs/SHARP_DUST_INTEGRATION.md).
Its wiring table uses the ESP32-S3 dust pins: GPIO5 (analog input) and GPIO4 (LED drive, active LOW, direct wiring). History: on 20 November 2026 every dust reading on the bench was `dust_input_at_zero`, because the firmware drove the LED with the wrong polarity. After the fix, on 25 November 2026, the sensor read 892.7 to 1135.0 mV and the estimate became current. The LED timing on an oscilloscope remains pending.

## Settings and timing

| Setting | Selected behavior | Current state |
|---|---|---|
| Communication timeout | 120 seconds | Exists in `config/alerts.yaml`. |
| Sensor error timeout | 120 seconds | Exists in `config/alerts.yaml`. |
| BME680 sampling | Every three seconds | BSEC low-power mode compiled. On 20 November 2026 readings came every 3.000 s on the bench. |
| Camera processing | Every 60 seconds | `camera_interval_s` in `config/runtime.yaml`. Not checked with a camera. |
| Fault checks | Every 5 seconds | Implemented in source. Listed virtual-serial checks completed on Linux. |
| Dashboard refresh | Every 10 seconds | `dashboard_refresh_s` in `config/runtime.yaml`. Must not exceed the staleness limit. |
| Dashboard staleness | 15 seconds | `status_stale_after_s` in `config/runtime.yaml`. Must exceed the fault check plus the poll interval. |
| BME680 reading gap | 6 seconds | `reading_gap_limit_s` in `config/runtime.yaml`. Restarts sustained timers. |
| Patient profiles | Apply valid changes during monitoring | Implemented as a YAML file beside the database. Checked in tests and the simulator. |
| Sustained duration | Set in the patient profile | Implemented. No value is selected for real use. |
| BSEC state save | At IAQ accuracy 3: once after start, then every 6 hours | Fixed in the firmware (`ROOM_BSEC_STATE_SAVE_MS`). Bosch's standard interval. The first save happened on the board on 25 November 2026 (on a stuck gas reading). The 6-hour repeat is not checked. |
| BSEC state wait at board start | 10 seconds | Fixed in the firmware (`ROOM_BSEC_STATE_WAIT_MS`). Compiled; not checked on hardware. |
| Alarm confirmation | 2 seconds | `alarm_confirm_timeout_s` in `config/runtime.yaml`. Must exceed the poll interval. The alarm shows as unreachable after it. |
| Reading retention | 7 days | `readings_retention_days` in `config/runtime.yaml`, at least 1. The monitor prunes hourly. Events are kept. |
| Technical settings | Apply changes at program startup | The monitor loads both technical YAML files once. The six newer runtime keys are optional and default to the values above. Demo mode uses fixed values and the same defaults. The dashboard reads the effective values from the monitor status. |

Laptop YAML does not currently control the ESP32 sampling interval.
That configuration mechanism remains deferred.
Patient profiles contain individual limits, but the project does not define those limits.

A five-second fault check can detect a timeout almost five seconds after its duration expires.
Processing delays can add more time.
Dashboard refreshes and camera observations have their own intervals.
Unknown occupancy can delay a patient-limit alert until the next camera observation.

## Main files

The application now uses twenty-two Python files in the main folder.
Related settings, measurements, and state updates share files.
See the [Python file guide](reference_files/PYTHON_FILE_GUIDE.md) for every application, tool, and test file.
The test filenames remain unchanged so their original test cases are easy to track.

| File or folder | Purpose |
|---|---|
| `monitor.py` | Starts the monitor with a serial port or the simulator. |
| `serial_transport.py` | Reads complete serial lines and retries a lost connection. |
| `monitoring_loop.py` | Routes messages and checks faults during silence. |
| `status_output.py` | Formats readings, ages, and fault facts as JSON. |
| `config/runtime.yaml` | Sets host polling, retry, and fault-check intervals. |
| `settings.py` | Loads the three YAML settings files and checks their values. |
| `config/alerts.yaml` | Stores the two technical fault durations. |
| `communication_fault.py` | Tracks communication timeout and acknowledgment. |
| `sensor_fault.py` | Tracks persistent measurement errors and recovery. |
| `measurements.py` | Checks measurements and retains the last complete reading and its receipt time. |
| `monitoring_state.py` | Stores the combined state and applies incoming messages to readings and fault trackers. |
| `gas_readiness.py` | Checks reported Bosch warm-up and calibration status and keeps the reported index. |
| `air_quality.py` | Decides whether the Bosch index is current or calibrating and picks its word. |
| `config/system.yaml` | Air quality and dust limits (off as shipped), word bands, dust sensitivity and baseline rule. |
| `serial_parser.py` | Classifies a decoded serial line. |
| `room_store.py` | Stores status, readings, events, and the patient profile file. |
| `room_session.py` | Applies patient limits, sustained timing, and occupancy gating. Runs the local alarm after the limit state. |
| `alarm.py` | Decides the local alarm level, silence, and whether the board confirmed it. |
| `bsec_state_store.py` | Keeps the board's BSEC calibration state in a file next to the database and answers the board's state requests. |
| `occupancy.py` | Checks the camera for a person at the configured interval. |
| `simulated_input.py` | Supplies simulated records for the demo. |
| `dust.py` | Reads Sharp dust records and reports dust status. |
| `dashboard.py`, `templates/`, `static/` | Serve the local dashboard. |
| `firmware/sharp_dust.h` | Dust acquisition. Passed on the board on 25 November 2026 after the LED polarity fix. |
| `firmware/bus_recovery.h` | The I2C bus restart rule: restart after 10 s with no valid reading, at most every 30 s. Tested on Linux with g++. Used by the sketch. |
| `firmware/sharp_dust_limits.h` | Dust sample rule shared with a host test. |
| `firmware/host_command.h` | Reads the host lines (`ALARM`, `BSEC_STATE`) with a fixed buffer and holds the BSEC state-save rule. Tested on Linux with g++. Used by the sketch. |
| `firmware/alarm_command.h` | Alarm command parsing, bounded serial reading, LED and buzzer mapping, and reply formatting. Tested on Linux with g++. Used by the sketch. |
| `firmware/room_environment_safety_control_bme680.ino` | Prepares BSEC low-power readings and gas status reports. |
| `firmware/README.md` | Explains firmware configuration and remaining hardware checks. |
| `tools/read_sensor.py` | Prints JSON records from a selected serial port. It does not connect the monitoring components. |
| `tools/check_setup.py` | Reports environment metadata. It does not prove that the application works. |
| `tools/sensor_check.py` | Read-only bench check of the board: readings, gas change, dust input, Bosch accuracy and BSEC state lines. Stop the monitor first. |
| `tests/` | Contains twenty-four Python test files. The suite reported 798 passed on 25 November, on branch `fix/dust-led-i2c-restart`. See the verification records for earlier counts. |
| `reference_files/` | Contains the verification records (the newest is 25 November 2026), the Python file guide, the course reference, the historical implementation plan and Linux handoff, and the VIGIL comparison. |
| `docs/superpowers/` | Contains detailed component designs and implementation checklists. |
| `docs/SHARP_DUST_INTEGRATION.md` | Describes dust wiring, calibration, and checks. |

## Known limitations

- Every new part is verified with tests and the simulator, and partly on the bench on 20 and 25 November 2026 (see the hardware checklist in `firmware/README.md` and the [25 November verification record](reference_files/LINUX_VERIFICATION_2026-11-25.md)).
- The BME680 gas reading fails at the Bosch heater temperature. The Bosch index can show as current (accuracy 3) while it has no meaning. The fix is an open decision. See the [decision record](docs/superpowers/specs/2026-11-25-bme680-gas-heater-decision.md).
- The BME680 drops off the I2C bus at times. The firmware bus restart recovered it once and failed the second time (25 November 2026).
- The occupancy detector can miss seated, lying, or occluded people. Unknown occupancy suppresses patient-limit alerts.
- Raw readings older than 7 days are deleted. Events are never deleted. The dashboard shows the latest 50 events and pages to older ones.
- Timing settings apply at monitor startup. The dashboard uses the values in the latest monitor status.
- The sketch drives the alarm LED, which is the onboard RGB LED (GPIO48 by default), and the buzzer module on GPIO7 with a steady level. The LED lit as commanded on 20 November 2026. No buzzer is connected now. GPIO7 and the buzzer polarity are not checked on hardware. The polarity default is active high.
- When the USB link is down the host cannot command the LED or buzzer. The dashboard then shows the alarm as unreachable. The firmware has a link-lost fallback: after 30 s with no valid `ALARM` command the board blinks the LED (1 s on, 1 s off) and keeps the buzzer in its last state. The next valid command ends the blink. The user saw the blink start and stop on the bench on 20 November 2026.
- The dust value is an estimate with a typical sensitivity and an automatic baseline. It is not PM2.5, an official index, or a calibrated concentration.
- The air-quality index is a Bosch estimate. Its word bands are not checked against the Bosch datasheet.
- Air-quality and dust alerts sound the buzzer like patient-limit alerts. No limit values are supplied; the demo uses demonstration values only.

## Decisions recorded on 15 November 2026

These decisions are not implemented, except where an entry says so.

- The board is an ESP32-S3 with an N8R2 module. Correction, 17 November 2026: esptool shows the connected board is an N16R8-type module (16 MB flash, 8 MB embedded PSRAM), not an N8R2. The pins are I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7. The firmware uses them and compiles (15 November). They are not checked on hardware. Correction, 20 November 2026: the dust pins were swapped to match the wiring: dust analog input GPIO5, dust LED drive GPIO4. Correction, 20 November 2026: the alarm LED is now the onboard RGB LED (GPIO48 by default), not GPIO6. It lit as commanded on 20 November 2026. Correction, 25 November 2026: GPIO4 drives the dust LED directly (LOW turns it on). Dust readings passed on the board.
- Completion work builds on the current branch. The dust sensor stays.
- The primary dashboard viewer is a caregiver at a desk screen.
- The notification channel is a local alarm on the ESP32: a buzzer and an LED. The host side, the "Silence alarm" control and the sketch wiring were implemented on 15 November.
- The buzzer sounds for limit alerts only: patient limits, and the air-quality and dust system limits. System faults light the LED and show on the dashboard without sound.
- A dashboard "Silence alarm" button stops the buzzer for that alert. The LED stays on until the condition clears. The silence is logged. A new alert sounds again.
- The buzzer is a 3-pin buzzer module driven from one GPIO. Correction, 20 November 2026: no external alarm LED and no buzzer are connected. The alarm LED is the onboard RGB LED (GPIO48 by default). It lit as commanded on 20 November 2026. GPIO7 drives nothing for now.
- Raw readings will be kept for 7 days. Event history is kept regardless. Implemented on 15 November.
- The dashboard will be redesigned. The current page is a first draft. Implemented on this branch: five pages (Overview, Trends, Events, Patient limits, System), checked with the simulator and screenshots, and on 20 November 2026 with the board (HTTP 200).
- Air quality is Bosch's BSEC index and dust is an estimated concentration, both with words and an "estimate" label. Their limits are system setup. The profile has a short label. This replaces the raw-signals-only rule. Implemented on 15 November; tests and simulator only.

## What remains

For the current list, see [Remaining work in README.md](README.md#remaining-work). New items from 25 November 2026:

- BME680 gas: choose hardware option B or software option C. See the [decision record](docs/superpowers/specs/2026-11-25-bme680-gas-heater-decision.md). Decide what the dashboard shows while the index has no meaning.
- BME680 I2C drop-outs: the firmware bus restart is not always enough.

The older list below keeps its numbering. Items marked done or replaced are history.

1. Identify the ESP32-S3 board model. Run the rest of the hardware checklist in the [firmware guide](firmware/README.md).
2. Done on 17 November 2026: the USB port is the CH343 bridge, `/dev/ttyACM0`, with `CDCOnBoot=default`.
3. Obtain the hardware. Check the wiring and the 3.3 V sensor supply.
4. Check real readings with the laptop monitor. The firmware was uploaded on 17 November 2026, and the serial link and alarm protocol were checked without sensors.
5. Check physical USB reconnection, sensor failures, units, and actual BSEC status transitions.
6. Check dust timing with an oscilloscope. The automatic clean-air baseline formed on the board on 25 November 2026 (about 921.5 mV). It is not checked against a reference instrument.
7. Check the camera and the occupancy detector with seated, lying, and occluded people.
8. Check the local alarm on the real board: that GPIO7 is free, and the buzzer polarity once a buzzer is connected. Done on 20 November 2026: the onboard RGB LED was off or white as commanded, and the link-lost blink started and stopped.
9. Check the five-page dashboard with the real board and sensors. It is checked only with the simulator and screenshots.
10. Demonstrate normal operation, faults, and recovery with actual hardware.
11. Check a real dust disconnect on the bench. The monitor applies a floor rule: a dust voltage below `dust.disconnected_below_mv` (100 mV), a 0 mV reading, or the board's `dust_input_at_zero` report count as "no reading". After 120 s with no reading at or above the floor, the dust status is not connected and the dust fault is on. On 20 November every reading was `dust_input_at_zero` and the monitor raised the dust fault at 120 s. Still to check: with the divider wired and no sensor, the input reads below 100 mV, and a connected sensor reads above it.
12. Done 20 November 2026: online access with a signed-in control request through a real tunnel. Save limits, silence alarm and acknowledge were refused without sign-in (HTTP 403) and accepted after sign-in (HTTP 303).
13. BSEC state restore from the laptop file on the board. The firmware is flashed and a save happened on 25 November 2026 (on a stuck gas reading). Still to check, after a gas fix: power-cycle and confirm the restore from the file.
14. Items from the 20 November 2026 bench check (history; the 25 November results replace them):
    - Dust: failed on 20 November (every reading `dust_input_at_zero`). Fixed on 25 November 2026: the cause was the LED polarity, not the wiring or the power. Dust now passes.
    - Gas: stuck on 20 November (`gas_ohms` 12917166.00 for about 15 minutes). On 25 November a heater sweep showed real gas values at 200 to 260 °C and failures from 280 °C. Inference: the failure follows the heater drive (supply sag, or a contact or sensing layer that fails when hot). See the new BME680 gas item above.
    - Not done: the start-up line after a reset-button press (the window was missed), and the 10-minute gas run.

The project contains a rule engine, occupancy detector, database, and dashboard in software. Its local alarm exists on the host and in the sketch. The onboard LED was driven on the bench on 20 and 25 November 2026. No buzzer has been driven yet.
It remains an educational prototype.

## How this project differs from VIGIL

VIGIL is the reference program for camera-based bed posture and fall monitoring.
This project monitors room conditions and uses a camera for occupancy.

| Topic | VIGIL reference | This project |
|---|---|---|
| Main input | Camera posture classifications | BME680 and dust measurements, plus camera occupancy observations |
| Uncertain input | Occlusion preserves the last committed state | Incomplete readings will preserve the last complete values and timestamp |
| Configuration | Loads settings at startup | Technical settings load at startup. Patient profiles will support changes during monitoring. |
| Gas warm-up | No equivalent feature | Python reads Bosch status. Firmware source prepares the reports. Hardware operation is unverified. |
| Communication acknowledgment | Records acknowledgment in the database | The dashboard writes an acknowledgment request to SQLite. The monitor applies it. Acknowledgment during silence would start another timeout period, but the dashboard does not offer it. |
| Monitoring and dashboard | Separate monitor and web components | Same separation. The monitor writes SQLite and the dashboard reads it. |

See the [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for source findings and differences.
See [README.md](README.md) for the current project status. The [implementation plan](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md) is history (15 to 19 November 2026).

## Reading note

This guide uses short sentences and consistent terms inspired by Simplified Technical English.
It does not claim certified ASD-STE100 compliance.
