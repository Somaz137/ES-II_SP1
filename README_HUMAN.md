# Room Environment Safety Control

## Guide for people

This guide explains the project for students, reviewers, and future team members.
It describes the project purpose, current code, and planned behavior.
It contains no instructions for an AI assistant.

**Current status:** The repository contains separate components, but it does not contain a complete monitoring application.
Hardware operation and the full test suite still need checks in the approved Linux environment.

## What the project does

The project aims to monitor the environment of an occupied room.
Python will compare environmental measurements with limits in the selected patient profile.
The dashboard will show measurements, occupancy, faults, and alerts.
Patient limits and environmental alert rules still need agreement.

The current prototype uses one room, one ESP32, one BME680, and one camera.
Expansion to several rooms remains a future option.
The name does not imply automatic control of fans, heaters, or other equipment.
The project does not yet define those control functions.

## Hardware and software roles

| Part | Role | Current state |
|---|---|---|
| BME680 | Measures temperature, humidity, pressure, and gas resistance | Experimental firmware exists. Physical operation remains unverified. |
| ESP32 | Reads the BME680 and sends measurements through USB serial | Experimental firmware exists. |
| Laptop | Runs the Python monitoring logic | Separate components exist. Their integration remains future work. |
| Camera | Supplies images for occupancy detection | Connection and detection method remain undecided. |
| Dashboard | Shows room status and accepts alert acknowledgments | Not implemented. |

The laptop performs the main project logic.
The ESP32 provides the connection to the environmental sensor.
This prototype does not use an NVIDIA Jetson Nano.

## How measurements will move through the system

1. The ESP32 reads the BME680.
2. The ESP32 sends a JSON record through USB serial.
3. Python classifies the record and checks its measurement fields.
4. Python updates communication status and sensor status.
5. Python retains the last complete reading and its measurement time.
6. Python applies the agreed patient rules when measurements are suitable.
7. The dashboard shows the resulting status.

The firmware experiment, input classification, retained readings, and fault routing exist today.
The complete sequence does not run yet.
The future design keeps monitoring independent from dashboard refreshes.

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
The actual serial loop does not call this router yet.

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
A person must acknowledge that alert.
Acknowledgment during an outage dismisses the alert and starts another two-minute wait.
Continued silence causes another alert after that wait.
Acknowledgment does not change the actual last-contact time.

## Missing or incomplete readings

Before the first complete reading, the state contains no values or measurement time.
The initial status is waiting for the first measurement.
Recognized errors change the input status even when no complete reading exists.
The normal communication timeout still starts immediately.

An incomplete reading must not replace the last complete reading.
The future dashboard will retain the previous values and their original timestamp.
It will also indicate that the latest input is incomplete.
The dashboard must not present retained values as fresh measurements.

A recognized incomplete reading counts as communication and as a sensor error.
The sensor alert still waits for the configured error duration.
The parser already identifies incomplete readings.
The new state and router modules retain readings and update the fault trackers.
The dashboard remains future work.

## Gas warm-up and calibration

The selected design uses status reports from Bosch BSEC software.
Python does not declare readiness after a fixed waiting period.
The new Python module can read these reports.
The current ESP32 firmware does not yet send them.
Gas status therefore remains unknown with the current firmware.

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
The dashboard and environmental gas rules remain future work.
The new code does not calculate an air quality index from raw resistance.

The firmware integration still needs a sampling decision.
Bosch describes one-second BSEC operation for short-term testing.
Its low-power mode updates every three seconds.
The earlier project choice was continuous one-second sampling.
The existing firmware keeps that timing until the user selects the BSEC operating mode.

Initial sensor conditioning remains separate from this software status handling.
See the [BSEC integration design](docs/superpowers/specs/2026-11-08-bsec-status-design.md) for the protocol and manufacturer references.

## Settings and timing

| Setting | Selected behavior | Current state |
|---|---|---|
| Communication timeout | 120 seconds | Exists in `config/alerts.yaml`. |
| Sensor error timeout | 120 seconds | Exists in `config/alerts.yaml`. |
| BME680 sampling | Approximately once per second | Fixed in experimental ESP32 firmware. |
| Camera processing | Every 60 seconds | Planned. |
| Fault checks | Every 5 seconds | Planned. |
| Dashboard refresh | Every 10 seconds | Planned. |
| Patient profiles | Apply valid changes during monitoring | Planned. Format and validation remain undecided. |
| Technical settings | Apply changes at program startup | Loader exists. Startup integration remains future work. |

Laptop YAML does not currently control the ESP32 sampling interval.
That configuration mechanism remains deferred.
Patient profiles will contain individual limits, but the project does not yet define those limits.

A five-second fault check can detect a timeout almost five seconds after its duration expires.
Processing delays can add more time.
Dashboard refreshes and camera observations have their own intervals.

## Main files

| File or folder | Purpose |
|---|---|
| `config/alerts.yaml` | Stores the two technical fault durations. |
| `config_loader.py` | Reads the YAML settings. |
| `config_validation.py` | Checks the required settings and values. |
| `communication_fault.py` | Tracks communication timeout and acknowledgment. |
| `sensor_fault.py` | Tracks persistent measurement errors and recovery. |
| `reading_state.py` | Retains complete values, receipt time, and the latest input status. |
| `monitoring_state.py` | Combines reading state and both fault trackers. |
| `message_router.py` | Connects decoded serial input to those states. |
| `gas_readiness.py` | Checks reported Bosch warm-up and calibration status. |
| `serial_parser.py` | Classifies a decoded serial line. |
| `measurement_validation.py` | Checks the four required measurement fields. |
| `firmware/room_environment_safety_control_bme680.ino` | Contains the experimental ESP32 sensor reader. |
| `tools/read_sensor.py` | Prints JSON records from a selected serial port. It does not connect the monitoring components. |
| `tools/check_setup.py` | Reports environment metadata. It does not prove that the application works. |
| `tests/` | Contains eight test files. Test execution remains deferred to Linux. |
| `reference_files/` | Contains the course reference, implementation plan, Linux handoff, and VIGIL comparison. |
| `docs/superpowers/` | Contains detailed component designs and implementation checklists. |

## What remains

1. Execute the existing tests in the approved Linux environment.
2. Connect the new routing layer to the actual serial reader.
3. Select BSEC sampling and firmware dependencies.
4. Add serial recovery, periodic checks, and the BSEC firmware connection.
5. Check real sensor operation and select the camera method.
6. Define patient profiles and environmental alert rules.
7. Add storage, event history, and the dashboard.
8. Add the agreed notification method.
9. Demonstrate normal operation, faults, and recovery with actual hardware.

The project does not yet contain a complete rule engine, occupancy detector, database, dashboard, or notification worker.
It remains an educational prototype.

## How this project differs from VIGIL

VIGIL is the reference program for camera-based bed posture and fall monitoring.
This project monitors room conditions and uses a camera for occupancy.

| Topic | VIGIL reference | This project |
|---|---|---|
| Main input | Camera posture classifications | BME680 measurements and planned occupancy observations |
| Uncertain input | Occlusion preserves the last committed state | Incomplete readings will preserve the last complete values and timestamp |
| Configuration | Loads settings at startup | Technical settings load at startup. Patient profiles will support changes during monitoring. |
| Gas warm-up | No equivalent feature | Python reads Bosch status. Firmware integration remains future work. |
| Communication acknowledgment | Records acknowledgment in the database | Acknowledgment during silence starts another timeout period |
| Monitoring and dashboard | Separate monitor and web components | Same separation planned |

See the [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for source findings and differences.
See the [implementation plan](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md) for detailed project status.

## Reading note

This guide uses short sentences and consistent terms inspired by Simplified Technical English.
It does not claim certified ASD-STE100 compliance.
