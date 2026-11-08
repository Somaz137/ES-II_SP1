# Room Environment Safety Control - Project 8

This project monitors one room using a laptop, a DOIT ESP32 DevKit V1, a BME680, and a planned camera input.

## Current status

The user completed the listed Linux software checks.
The complete room-safety application is not implemented.
Physical ESP32 and BME680 operation remains unverified.

Read the [Linux verification record](reference_files/LINUX_VERIFICATION_2026-11-08.md) for results and evidence limits.
That record supersedes older statements that these completed checks are pending.

| Check | Recorded result |
|---|---|
| Python test suite | 301 tests collected. All displayed cases completed without reported failures. |
| Firmware message formatting | User reported success. |
| Complete firmware compilation | Arduino Verify succeeded for the selected DOIT board. |
| Missing communication | Monitor raised the communication alert and retained previous measurements. |
| Communication recovery | Fresh readings resumed. The outstanding communication alert remained active. |
| Repeated sensor errors | Communication stayed active while the sensor alert became active. |
| Sensor-error recovery | A valid reading cleared the sensor alert. |
| Simulated gas-status changes | Warm-up and calibration labels changed as expected. |

The runtime checks used a virtual serial port and artificial messages.
They do not establish physical sensor accuracy, calibration, USB behavior, or room safety.
The supplied pytest output did not include its final summary line or process exit code.

## Start here

- [Human guide](README_HUMAN.md): project purpose and behavior.
- [Verification record](reference_files/LINUX_VERIFICATION_2026-11-08.md): completed checks and remaining work.
- [Implementation plan](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md): decisions and milestones.
- [Linux handoff](reference_files/LINUX_AI_HANDOFF.md): continuation guidance.
- [Manual reference](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md): course requirements and source pointers.
- [Firmware guide](firmware/README.md): sketch structure and hardware checks.
- [Python requirements](requirements.txt): required package versions.

Older preparation notes and component checklists describe the state before the recorded Linux session.
Do not repeat completed checks without a change, failure, or specific unresolved concern.

## Selected hardware

The selected board is DOIT ESP32 DEVKIT V1 with the classic ESP32 chip.
Sensor SDA uses GPIO21. Sensor SCL uses GPIO22.
The user confirmed a 3.3 V sensor supply.
The board header stores the pins, serial speed, supply selection, and reporting intervals.
The chip check rejects other ESP32 chip types. It cannot identify the physical development board.

The sketch uses Bosch BSEC2 and Bosch BME68x.
The Python requirements do not install Arduino libraries.
Firmware compilation succeeded with the user's installed packages.
Upload, breakout wiring, actual pressure units, and physical readings remain unchecked.

## Main components

The application now uses eleven Python files in the main folder.
Related settings, measurements, and state updates share files.
See the [Python file guide](reference_files/PYTHON_FILE_GUIDE.md) for every application, tool, and test file.
The test filenames remain unchanged so their original test cases are easy to track.

| File | Purpose |
|---|---|
| monitor.py | Starts the terminal monitor with an explicitly selected serial port. |
| serial_transport.py | Reads complete lines, handles partial input, and retries the selected port after connection errors. |
| monitoring_loop.py | Routes input and checks faults during silence. |
| status_output.py | Reports retained readings, reading age, estimated receipt time, faults, and gas status. |
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
| tools/check_setup.py | Reports environment metadata. It does not prove full application operation. |
| tools/read_sensor.py | Prints records from a selected serial port as a separate diagnostic. |
| tests/ | Contains the automated Python tests. |
| firmware/tests/test_bsec_serial_format.cpp | Contains the separate portable C++ formatting test. |

## Behavior to preserve

The monitor loads technical settings at startup.
The initial communication wait begins when the monitor starts.
Recognized readings and sensor errors both count as communication.
Incomplete readings retain the previous complete measurements and their original receipt time.
Ignored input does not reset communication timing.

Missing communication raises a communication alert.
Communication recovery clears the timeout but does not dismiss that alert.
A person must acknowledge the alert. The terminal interface has no acknowledgment control yet.
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

Fault checks use the selected five-second interval.
Camera processing remains planned at sixty seconds.
Dashboard refresh remains planned at ten seconds.
Laptop YAML does not control ESP32 acquisition timing.
Firmware configuration commands and calibration-state storage remain future work.

## Remaining work

1. Obtain the ESP32 and BME680 and complete physical hardware checks.
2. Check camera capture and agree on an occupancy method.
3. Define patient profiles, environmental limits, sustained-breach timing, and occupancy gating.
4. Add storage, history, the dashboard, and the agreed notification method.
5. Demonstrate the complete system with actual hardware.

Follow the course requirements and approved project decisions.
Preserve the existing environment and required dependencies.
Do not recreate the removed setup installer.
Ask before adding unspecified dependencies, algorithms, services, or hardware procedures.
Use the [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for verified reference behavior.
The original course PDFs and VIGIL archive are not included in this repository.
