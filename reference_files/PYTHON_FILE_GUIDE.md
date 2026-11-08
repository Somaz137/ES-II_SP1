# Python file guide

This guide explains the current files in simple terms.
The main folder contains eleven application Python files.
The project also contains two Python tools and eleven Python test files.
The total is twenty-four Python files.

## Application files

| File | Purpose |
|---|---|
| `monitor.py` | Starts the program. Reads command options, loads settings, and starts monitoring. |
| `settings.py` | Reads both YAML settings files. Rejects missing or invalid settings. |
| `serial_transport.py` | Opens the selected serial port. Collects complete lines and retries the connection after errors. |
| `serial_parser.py` | Reads each text message. Identifies a valid reading, sensor error, incomplete reading, or ignored message. |
| `measurements.py` | Checks the four measurement values. Retains the last complete reading, its receipt time, and the latest input condition. |
| `communication_fault.py` | Tracks messages from the ESP32. Raises an alert when communication stops and handles acknowledgment. |
| `sensor_fault.py` | Tracks repeated measurement errors. Raises a sensor alert after the waiting period and clears it after a valid reading. |
| `gas_readiness.py` | Checks the Bosch status fields. Reports gas warm-up and calibration status. |
| `monitoring_state.py` | Keeps the reading, fault states, and gas status together. Applies each message to the correct parts. |
| `monitoring_loop.py` | Repeats serial reads and fault checks. Continues checking faults when no messages arrive. |
| `status_output.py` | Prepares the terminal report. Includes measurements, reading age, receipt time, connection state, alerts, and gas status. |

The state means the program's current stored information.
The serial parser identifies the message type.
The monitoring state code then updates the stored information.
The monitoring loop decides when those actions occur.

Communication faults and sensor faults remain separate because their recovery rules differ.
A sensor error message proves that communication continues.
A valid reading clears a sensor alert automatically.
Communication recovery does not dismiss an outstanding communication alert.

## Tools

| File | Purpose |
|---|---|
| `tools/check_setup.py` | Reports Python package versions and visible devices. It does not prove that the complete application works. |
| `tools/read_sensor.py` | Opens a selected serial port and prints received JSON records. It is a separate diagnostic tool. |

## Test files

| File | Purpose |
|---|---|
| `tests/test_config.py` | Checks alert settings and actual YAML loading. |
| `tests/test_runtime_settings.py` | Checks host polling, retry, and fault-check settings. |
| `tests/test_measurement_validation.py` | Checks valid and invalid measurement values. |
| `tests/test_reading_state.py` | Checks stored readings, original receipt times, and incomplete input. |
| `tests/test_serial_parser.py` | Checks how the program classifies incoming text messages. |
| `tests/test_communication_fault.py` | Checks communication timeout, recovery, acknowledgment, and repeated alerts. |
| `tests/test_sensor_fault.py` | Checks sensor-error timing, pauses, recovery, and alert clearing. |
| `tests/test_gas_readiness.py` | Checks valid, missing, and invalid Bosch status fields. |
| `tests/test_message_router.py` | Checks that parsed messages update readings, faults, and gas status together. |
| `tests/test_serial_transport.py` | Checks line assembly, invalid input, connection retry, and connection cleanup. |
| `tests/test_monitoring_loop.py` | Checks the running loop with controlled time and simulated serial input. |

The test filenames describe the behavior under test.
They do not require an application file with the same name.
The original test filenames and all 301 test cases remain unchanged.
Only their module imports changed.

## Other important files

| File or folder | Purpose |
|---|---|
| `config/alerts.yaml` | Stores communication and sensor-error waiting periods. |
| `config/runtime.yaml` | Stores host polling, connection retry, and periodic fault-check intervals. |
| `requirements.txt` | Lists the required Python packages and versions. |
| `firmware/room_environment_safety_control_bme680.ino` | Runs on the ESP32. Reads the sensor and sends measurements or errors. |
| `firmware/bsec_board_config.h` | Stores the selected board settings, pins, supply, and reporting intervals. |
| `firmware/bsec_serial_format.h` | Converts firmware measurements and Bosch status into JSON text. |
| `firmware/tests/test_bsec_serial_format.cpp` | Checks firmware message formatting on a computer without the sensor. |
| `tests/fixtures/bsec_reading.json` | Supplies an example reading for tests. It is not a physical measurement. |
| `README.md` | Gives the project entry point and current status. |
| `README_HUMAN.md` | Explains the system and its behavior for people. |
| `reference_files/` | Stores the manual reference, project plan, handoff, comparisons, and verification records. |
| `docs/superpowers/` | Stores detailed component designs and implementation checklists. |

## Effect of the merge

Related functions now share files. Their behavior remains unchanged.
Function and class names remain unchanged.
The program still starts with monitor.py and an explicitly selected serial port.
The two settings files remain separate.
No dependency versions, firmware files, or alert rules changed.
The merge does not add camera processing, patient rules, a dashboard, or notifications.

Run the existing suite from the project folder with the approved environment active:

```bash
python3 -m pytest
```

The original eleven test files still contain 301 cases.
Hardware operation requires separate physical checks.
