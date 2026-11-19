# Room Environment Safety Control

**Linux checks recorded:** See the [8 November verification record](reference_files/LINUX_VERIFICATION_2026-11-08.md), the [15 November verification record](reference_files/LINUX_VERIFICATION_2026-11-15.md) and the [17 November verification record](reference_files/LINUX_VERIFICATION_2026-11-17.md).
On 8 November the user completed Python test execution, firmware formatting, compilation, and the listed virtual-serial scenarios.
On 15 November the full suite on this branch reported 317 passed, and the software demo ran without errors. After the dashboard data contract it reported 401 passed. After the local alarm host side it reported 461 passed, also with `-W error`. After the ESP32-S3 port it reported 462 passed, also with `-W error`, and the sketch compiled for the ESP32-S3.
On 17 November the ESP32-S3 was flashed. The serial link and the alarm protocol were checked with no sensors attached.
Physical BME680, dust sensor, LED, buzzer, and camera operation remains unverified.
The 8 November Linux build used ESP32 core 3.3.12, Bosch BSEC2 1.10.2610, and Bosch BME68x 1.3.40408 for the DOIT board. It did not include the dust code.
These records supersede earlier pending-test statements in historical preparation notes and design checklists.


## Guide for people

This guide explains the project for students, reviewers, and future team members.
It describes the project purpose, current code, and planned behavior.
It contains no instructions for an AI assistant.

**Current status:** The repository contains the monitor, SQLite storage, patient-limit rules, camera occupancy, a local dashboard, and a Sharp dust path.
These parts exist in software. Automated tests and a simulator verify them. On 17 November 2026 the monitor ran for 60 s against the flashed board with no sensors attached. No part has run with sensors or a real camera.
The local alarm is implemented on the host and in the sketch. It is checked with the simulator, host C++ tests, a compilation for the ESP32-S3, and the board's serial replies to `ALARM` commands (17 November). No LED or buzzer has been driven. The dashboard redesign is decided but not implemented. 7-day reading retention is implemented.

## What the project does

The project aims to monitor the environment of an occupied room.
Python compares temperature, humidity, and pressure with limits in the patient profile.
The dashboard shows measurements, occupancy, faults, and alerts.
The project supplies no patient limits. The demo example limit applies only to the simulator.

The prototype uses one room, one ESP32-S3 board, one BME680, one Sharp dust sensor, and one camera.
The board is an ESP32-S3 with 16 MB flash and 8 MB embedded PSRAM, an N16R8-type module. esptool read these facts from the connected board on 17 November 2026. The documents assumed an N8R2 module until then. The user selected the ESP32-S3 on 15 November 2026. It supersedes the DOIT ESP32 DevKit V1.
The pins are I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7.
The firmware uses these pins. They are not checked against the physical board. The exact development board model is not identified.
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
| BME680 | Measures temperature, humidity, pressure, and gas resistance | Experimental firmware exists. Physical operation remains unverified. |
| Sharp GP2Y1010AU0F | Supplies a raw dust voltage | Experimental firmware exists. Compiled for the ESP32-S3. Not hardware-checked. |
| ESP32-S3 | Reads the sensors, drives the local alarm and sends records through USB serial | Flashed on 17 November 2026. Serial link and alarm replies checked without sensors. LED, buzzer and sensor inputs not checked. |
| Laptop | Runs the monitor, rules, storage, and dashboard | Implemented in software. Verified by tests and the simulator. |
| Camera | Supplies frames for occupancy detection | OpenCV people detector implemented. Not checked with a camera. |
| Dashboard | Shows room status, trends, events, limits and the local alarm state, and accepts communication acknowledgments and alarm silence requests | Local first draft implemented. Checked only with simulated data. A redesign is decided. |
| Local alarm | Buzzer and LED on the ESP32 | Host side and sketch implemented. Checked with the simulator, host C++ tests and a compilation. Alarm LED GPIO6, buzzer GPIO7, buzzer polarity and pins not checked on the board. |

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
That physical behavior still needs a check.

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
The independent notification path is a local LED and buzzer on the ESP32. The monitor sends `ALARM,<level>` over USB serial and the board confirms it. Level 2 (LED and buzzer) means an unsilenced patient-limit alert. Level 1 (LED only) means a silenced limit alert or a communication, BME680 or dust alert. Level 0 is off. The dashboard shows whether the board confirmed the level. The sketch does not yet act on the command, so this path is simulated only.
The listed automated, virtual-serial, and simulator checks completed on Linux. Real ESP32 and sensor operation remains pending.

## Software demo

Run both entry points in the existing project environment, in separate terminals:

```text
python monitor.py --demo
python dashboard.py --demo
```

Open http://127.0.0.1:5000. The demo uses its own SQLite database. It simulates an occupied room, BME680 readings, and Sharp dust voltage at three-second intervals.
On a fresh demo database the temperature crosses the example limit at 18 seconds. A caregiver alert starts at about 27 seconds. The temperature returns to range at about 60 seconds.
The example values apply only to the simulator. They are not patient limits.

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
Compilation succeeded on Linux. Hardware checks remain pending.
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
The BSEC calibration state is not saved across power loss. After each board start the index calibrates again.

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
Its wiring table uses the ESP32-S3 dust pins: GPIO4 (analog input) and GPIO5 (LED drive). The code compiles. Hardware timing remains pending.

## Settings and timing

| Setting | Selected behavior | Current state |
|---|---|---|
| Communication timeout | 120 seconds | Exists in `config/alerts.yaml`. |
| Sensor error timeout | 120 seconds | Exists in `config/alerts.yaml`. |
| BME680 sampling | Every three seconds | BSEC low-power mode compiled. Physical acquisition remains unverified. |
| Camera processing | Every 60 seconds | `camera_interval_s` in `config/runtime.yaml`. Not checked with a camera. |
| Fault checks | Every 5 seconds | Implemented in source. Listed virtual-serial checks completed on Linux. |
| Dashboard refresh | Every 10 seconds | `dashboard_refresh_s` in `config/runtime.yaml`. Must not exceed the staleness limit. |
| Dashboard staleness | 15 seconds | `status_stale_after_s` in `config/runtime.yaml`. Must exceed the fault check plus the poll interval. |
| BME680 reading gap | 6 seconds | `reading_gap_limit_s` in `config/runtime.yaml`. Restarts sustained timers. |
| Patient profiles | Apply valid changes during monitoring | Implemented as a YAML file beside the database. Checked in tests and the simulator. |
| Sustained duration | Set in the patient profile | Implemented. No value is selected for real use. |
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

The application now uses eighteen Python files in the main folder.
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
| `occupancy.py` | Checks the camera for a person at the configured interval. |
| `simulated_input.py` | Supplies simulated records for the demo. |
| `dust.py` | Reads Sharp dust records and reports dust status. |
| `dashboard.py`, `templates/`, `static/` | Serve the local dashboard. |
| `firmware/sharp_dust.h` | Experimental dust acquisition. Compiled for the ESP32-S3. |
| `firmware/sharp_dust_limits.h` | Dust sample rule shared with a host test. |
| `firmware/alarm_command.h` | Alarm command parsing, bounded serial reading, LED and buzzer mapping, and reply formatting. Tested on Linux with g++. Used by the sketch. |
| `firmware/room_environment_safety_control_bme680.ino` | Prepares BSEC low-power readings and gas status reports. |
| `firmware/README.md` | Explains firmware configuration and remaining hardware checks. |
| `tools/read_sensor.py` | Prints JSON records from a selected serial port. It does not connect the monitoring components. |
| `tools/check_setup.py` | Reports environment metadata. It does not prove that the application works. |
| `tests/` | Contains sixteen Python test files. The suite reported 462 passed on 15 November, after the ESP32-S3 port. See the verification records. |
| `reference_files/` | Contains the course reference, implementation plan, Linux handoff, and VIGIL comparison. |
| `docs/superpowers/` | Contains detailed component designs and implementation checklists. |
| `docs/SHARP_DUST_INTEGRATION.md` | Describes dust wiring, calibration, and checks. |

## Known limitations

- Every new part is verified only with tests and the simulator.
- The occupancy detector can miss seated, lying, or occluded people. Unknown occupancy suppresses patient-limit alerts.
- Raw readings older than 7 days are deleted. Events are never deleted. The dashboard shows the latest 50 events and pages to older ones.
- Timing settings apply at monitor startup. The dashboard uses the values in the latest monitor status.
- The sketch drives the alarm LED on GPIO6 and the buzzer module on GPIO7 with a steady level. Pins and buzzer polarity are not checked on hardware. The polarity default is active high.
- When the USB link is down the host cannot command the LED or buzzer. The dashboard then shows the alarm as unreachable. A firmware fallback is an open decision.
- The dust value is an estimate with a typical sensitivity and an automatic baseline. It is not PM2.5, an official index, or a calibrated concentration.
- The air-quality index is a Bosch estimate. Its word bands are not checked against the Bosch datasheet.
- Air-quality and dust alerts sound the buzzer like patient-limit alerts. No limit values are supplied; the demo uses demonstration values only.

## Decisions recorded on 15 November 2026

These decisions are not implemented, except where an entry says so.

- The board is an ESP32-S3 with an N8R2 module. Correction, 17 November 2026: esptool shows the connected board is an N16R8-type module (16 MB flash, 8 MB embedded PSRAM), not an N8R2. The pins are I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7. The firmware uses them and compiles (15 November). They are not checked on hardware.
- Completion work builds on the current branch. The dust sensor stays.
- The primary dashboard viewer is a caregiver at a desk screen.
- The notification channel is a local alarm on the ESP32: a buzzer and an LED. The host side, the "Silence alarm" control and the sketch wiring were implemented on 15 November.
- The buzzer sounds for limit alerts only: patient limits, and the air-quality and dust system limits. System faults light the LED and show on the dashboard without sound.
- A dashboard "Silence alarm" button stops the buzzer for that alert. The LED stays on until the condition clears. The silence is logged. A new alert sounds again.
- The buzzer is a 3-pin buzzer module driven from one GPIO.
- Raw readings will be kept for 7 days. Event history is kept regardless. Implemented on 15 November.
- The dashboard will be redesigned. The current page is a first draft.
- Air quality is Bosch's BSEC index and dust is an estimated concentration, both with words and an "estimate" label. Their limits are system setup. The profile has a short label. This replaces the raw-signals-only rule. Implemented on 15 November; tests and simulator only.

## What remains

1. Identify the ESP32-S3 board model. Run the rest of the hardware checklist in the [firmware guide](firmware/README.md).
2. Done on 17 November 2026: the USB port is the CH343 bridge, `/dev/ttyACM0`, with `CDCOnBoot=default`.
3. Obtain the hardware. Check the wiring and the 3.3 V sensor supply.
4. Check real readings with the laptop monitor. The firmware was uploaded on 17 November 2026, and the serial link and alarm protocol were checked without sensors.
5. Check physical USB reconnection, sensor failures, units, and actual BSEC status transitions.
6. Check dust timing with an oscilloscope and measure a clean-air baseline.
7. Check the camera and the occupancy detector with seated, lying, and occluded people.
8. Check the local alarm on the real board: the LED, the buzzer polarity, and that GPIO6 and GPIO7 are free.
9. Redesign the dashboard.
10. Demonstrate normal operation, faults, and recovery with actual hardware.
11. Decide how to detect a disconnected dust sensor. With no dust sensor attached, the dust input reads about 870 to 930 mV and is accepted as a fresh dust record, most likely because the ADC pin floats. A disconnected dust sensor cannot currently be told apart from a working one. Candidate fixes: a pull-down resistor on the dust input, or a firmware check that compares the signal with the sensor LED on and off. The user will choose when wiring.

The project contains a rule engine, occupancy detector, database, and dashboard in software. Its local alarm exists on the host and in the sketch. No LED or buzzer has been driven yet.
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
See the [implementation plan](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md) for detailed project status.

## Reading note

This guide uses short sentences and consistent terms inspired by Simplified Technical English.
It does not claim certified ASD-STE100 compliance.
