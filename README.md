# Room Environment Safety Control - Project 8

This project monitors one room using a laptop, an ESP32 board, a BME680, a Sharp dust sensor, and a camera for occupancy.
The selected board changed to an ESP32-S3 on 15 November 2026. See [Selected hardware](#selected-hardware).

## Current status

This branch adds the room software: SQLite storage, patient limits, sustained-breach alerts, camera occupancy, a local dashboard, and a Sharp dust sensor path.
These parts exist in software. They are verified only by automated tests and the simulator.
No physical ESP32, BME680, dust sensor, or camera check has taken place.
The local alarm, data retention, and dashboard redesign are decided but not implemented.

Read the [15 November verification record](reference_files/LINUX_VERIFICATION_2026-11-15.md) for the current software results.
Read the [8 November verification record](reference_files/LINUX_VERIFICATION_2026-11-08.md) for the earlier virtual-serial and compilation results.

| Check | Recorded result |
|---|---|
| Python test suite, this branch | 317 passed, exit code 0, no skips (15 November). |
| Python test suite, `main` | 301 passed, exit code 0 (15 November). |
| Firmware message formatting | Built with no warnings and passed (15 November). |
| Software demo | Monitor and dashboard ran together. The simulated limit alert started and ended as expected (15 November). |
| Complete firmware compilation | Arduino Verify succeeded for the DOIT board on 8 November, before `sharp_dust.h` existed. The current sketch has not been compiled. |
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

**Board change, 15 November 2026:** The user selected an ESP32-S3 with an N8R2 module (8 MB flash, 2 MB PSRAM).
This supersedes the DOIT ESP32 DevKit V1. The decision is not implemented.
The firmware still requires the classic ESP32 chip and refuses to compile for an ESP32-S3.
GPIO22 and GPIO25 do not exist on the ESP32-S3. GPIO34 is not an analog input on it. The DOIT pins therefore do not carry over.
The user decided these ESP32-S3 pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7.
The pins are not implemented in the firmware and not checked against the physical board. The exact development board model is not identified.
This machine is being set up to match the recorded versions: ESP32 core 3.3.12, BSEC2 1.10.2610, and BME68x 1.3.40408. That setup is in progress.
Nothing has been compiled for or flashed to an ESP32-S3. No ESP32-S3 has been connected.
The rest of this section records the earlier DOIT selection.

The earlier board was DOIT ESP32 DEVKIT V1 with the classic ESP32 chip.
Sensor SDA uses GPIO21. Sensor SCL uses GPIO22.
The user confirmed a 3.3 V sensor supply.
The board header stores the pins, serial speed, supply selection, and reporting intervals.
The chip check rejects other ESP32 chip types. It cannot identify the physical development board.

The sketch uses Bosch BSEC2 and Bosch BME68x.
The Python requirements do not install Arduino libraries.
Firmware compilation succeeded with the user's installed packages on 8 November. That build did not include `sharp_dust.h`.
Upload, breakout wiring, actual pressure units, and physical readings remain unchecked.

## Main components

The application now uses seventeen Python files in the main folder.
Related settings, measurements, and state updates share files.
See the [Python file guide](reference_files/PYTHON_FILE_GUIDE.md) for every application, tool, and test file.
The test filenames remain unchanged so their original test cases are easy to track.

| File | Purpose |
|---|---|
| monitor.py | Starts the monitor with an explicit serial port, or with `--demo` for simulated input. Connects storage, rules, camera, and acknowledgment requests. |
| serial_transport.py | Reads complete lines, handles partial input, and retries the selected port after connection errors. |
| monitoring_loop.py | Routes input and checks faults during silence. |
| status_output.py | Reports retained readings, reading age, estimated receipt time, faults, gas status, and dust status. |
| room_store.py | Stores status, readings, and events in SQLite. Loads, validates, and saves the patient profile file. |
| room_session.py | Applies patient limits, sustained-breach timing, and occupancy gating. Logs alert and fault events. |
| occupancy.py | Checks the camera every 60 seconds with OpenCV's default people detector. Saves no frames. |
| simulated_input.py | Supplies simulated BME680 and dust records for `--demo`. |
| dust.py | Classifies Sharp dust records and reports dust status. Calculates a dust estimate only with user calibration. |
| dashboard.py | Serves the local dashboard on 127.0.0.1. Reads SQLite. Saves patient limits and acknowledgment requests. |
| templates/, static/ | Dashboard page, script, and style. |
| `settings.py` | Loads both YAML settings files and checks their values. |
| config/runtime.yaml | Stores host polling, retry, and fault-check intervals. |
| config/alerts.yaml | Stores the communication and sensor-error timeouts. |
| communication_fault.py | Tracks missing communication and alert acknowledgment. |
| sensor_fault.py | Tracks repeated sensor errors and valid-reading recovery. |
| `measurements.py` | Checks measurements and retains the last complete reading and its receipt time. |
| serial_parser.py | Classifies readings, errors, incomplete records, and ignored input. |
| `monitoring_state.py` | Stores the combined state and applies incoming messages to readings and fault trackers. |
| gas_readiness.py | Interprets reported Bosch warm-up and calibration status. |
| firmware/room_environment_safety_control_bme680.ino | Reads the sensor and sends JSON measurements or error records. |
| firmware/bsec_board_config.h | Stores board settings and validates chip and supply selections. |
| firmware/bsec_serial_format.h | Formats measurements and Bosch status as JSON. |
| firmware/sharp_dust.h | Experimental Sharp dust acquisition and raw voltage reports. Not compiled or hardware-checked. |
| tools/check_setup.py | Reports environment metadata. It does not prove full application operation. |
| tools/read_sensor.py | Prints records from a selected serial port as a separate diagnostic. |
| tests/ | Contains the automated Python tests. |
| firmware/tests/test_bsec_serial_format.cpp | Contains the separate portable C++ formatting test. |

## Run the software demo

Run both entry points in your existing project environment, in separate terminals:

```text
python monitor.py --demo
python dashboard.py --demo
```

Open http://127.0.0.1:5000. The demo uses its own SQLite database. It simulates an occupied room, BME680 readings, and Sharp dust voltage at three-second intervals. On a fresh demo database the temperature crosses the example limit at 18 seconds, raises a caregiver alert at about 27 seconds, and returns to range at about 60 seconds. Patient limits are saved beside the database in a `.profile.yaml` file. Valid changes take effect on the next monitor update. If the file is invalid, the monitor keeps its last valid profile and shows a profile error. The example values apply only to the simulator.

The dashboard refreshes every ten seconds. It shows the last monitor update, sensor readings, occupancy, 24-hour trends, caregiver alerts, the latest 50 events, a patient limits form, and the communication acknowledgment control. Trend points are one-minute averages. The dashboard accepts requests only for `localhost` and `127.0.0.1` and rejects cross-site form posts. The dashboard can be closed while monitoring continues. Readings and event history stay in local SQLite files. The 24-hour chart is a display window. There is no automatic database pruning yet.

On the real serial path, supply the existing serial port argument and the `--camera` index option when physical testing resumes. Both programs accept `--db` and must use the same file. OpenCV checks at one-minute intervals. A detected person gives occupied status. Failed capture, no detection, and expired observations give unknown status. Frames are processed locally and never saved. Physical validation is still pending.

## Sharp dust sensor

The experimental GP2Y1010AU0F path adds independent dust voltage and status. A stale dust report raises a dust fault. No dust limit exists. `--dust-baseline-mv` and `--dust-sensitivity` together enable a user-calibrated estimate. See [wiring, plan, calibration, and verification](docs/SHARP_DUST_INTEGRATION.md). Its wiring table uses the superseded DOIT pins. The decided ESP32-S3 dust pins are GPIO4 (analog input) and GPIO5 (LED drive). Firmware compilation and hardware timing remain pending.

## Behavior to preserve

The monitor loads technical settings at startup.
The initial communication wait begins when the monitor starts.
Recognized readings and sensor errors both count as communication.
Incomplete readings retain the previous complete measurements and their original receipt time.
Ignored input does not reset communication timing.

Missing communication raises a communication alert.
Communication recovery clears the timeout but does not dismiss that alert.
A person must acknowledge the alert on the dashboard after contact recovers.
The dashboard cannot acknowledge during an outage.
The monitor applies the acknowledgment at its next fault check. The event history records the cleared alert.
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
Patient-limit alerts require occupied status and a fresh BME680 reading at most six seconds old.
Unknown occupancy, a stale reading, or a gap of more than six seconds between readings restarts the timer.
A changed profile restarts all timers. An invalid profile file keeps the last valid profile and shows a profile fault.
Communication, BME680, dust, and profile fault alerts do not depend on occupancy.

Fault checks use the selected five-second interval.
Camera processing uses sixty seconds. An observation older than sixty-five seconds becomes unknown.
The dashboard refreshes every ten seconds and treats a status older than fifteen seconds as overdue.
The six-second gap, camera interval, refresh, and staleness limits are constants in code, not YAML settings.
Laptop YAML does not control ESP32 acquisition timing.
Firmware configuration commands and calibration-state storage remain future work.

## Known limitations

- The occupancy detector is OpenCV's default people detector, trained on upright pedestrians. It can miss seated, lying, or occluded people. Unknown occupancy suppresses patient-limit alerts. It has not been checked with a camera.
- In serial mode without `--camera`, occupancy is always unknown, so patient-limit alerts never start.
- No database pruning exists. The event list shows the latest 50 events.
- Alert text names the measurement and direction only. It does not state the limit, value, or duration.
- No independent notification path exists. Caregiver alerts stay inside the dashboard.
- Dust output is a raw sensor voltage. It is not PM2.5, AQI, or a calibrated concentration.

## Decided, not implemented (15 November 2026)

- Board: ESP32-S3 with an N8R2 module. Pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7. The firmware still targets the classic ESP32 and must change.
- Completion work builds on this branch. The dust sensor stays.
- Primary dashboard viewer: a caregiver at a desk screen.
- Notification: a local ESP32 buzzer and LED. The buzzer sounds for patient-limit alerts only. System faults light the LED and show on the dashboard without sound.
- A dashboard "Silence alarm" button stops the buzzer for that alert. The LED stays on until the condition clears. The silence is logged. A new alert sounds again.
- Buzzer part: a 3-pin buzzer module driven from one GPIO (GPIO7 on the ESP32-S3). The alarm LED uses GPIO6.
- Raw readings will be kept for 7 days. Event history is kept regardless.
- The dashboard will be redesigned. The current page is a first draft.

## Remaining work

1. Identify the ESP32-S3 board model. Finish the toolchain setup. Adapt the chip check and pins, and compile the firmware, including the dust code.
2. Obtain the hardware and complete physical BME680, dust, and USB checks.
3. Check camera capture and the occupancy detector with seated, lying, and occluded people.
4. Agree on real patient limits for any demonstration.
5. Implement the local buzzer and LED alarm and the "Silence alarm" control.
6. Implement 7-day reading retention.
7. Redesign the dashboard and state the limit, value, and duration in alert text.
8. Demonstrate the complete system with actual hardware.

Follow the course requirements and approved project decisions.
Preserve the existing environment and required dependencies.
Do not recreate the removed setup installer.
Ask before adding unspecified dependencies, algorithms, services, or hardware procedures.
Use the [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for verified reference behavior.
The original course PDFs and VIGIL archive are not included in this repository.
