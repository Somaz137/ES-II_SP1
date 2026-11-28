# Python file guide

This guide explains the current files in simple terms.
The main folder contains twenty-two application Python files.
The project also contains three Python tools and twenty-four Python test files.
The total is forty-nine Python files (counted on 25 November 2026, branch `fix/dust-led-i2c-restart`).
The six newest application files and three newest test files are on branch `feature/sharp-dust-integration`.
They are verified only with automated tests and the simulator.
The local alarm added `alarm.py`, `tests/test_alarm.py` and `tests/test_alarm_link.py` on branch `feature/local-alarm`. It is also verified only with tests and the simulator.
The air-quality and dust-estimate step added `air_quality.py`, `tests/test_air_quality.py` and `tests/test_system_limits.py` on branch `feature/air-quality-dust-label`. It is verified only with tests and the simulator.
The BSEC state save added `bsec_state_store.py` and `tests/test_bsec_state.py` on branch `feature/bsec-state` (20 November 2026). It is verified with tests and the simulator. The firmware side is compiled and host-tested. On the board (25 November 2026) it reached accuracy 3 and saved its state, but on a stuck gas reading. A restore from the laptop file after a board start is not checked. See the [25 November verification record](LINUX_VERIFICATION_2026-11-25.md).
The sensor check tool added `tools/sensor_check.py` and `tests/test_sensor_check.py` (25 November 2026). It ran on the board on 25 November 2026.
The occupancy work on branch `feature/occupancy` (27 November 2026, not yet merged to `main`) added `person_detector.py`, `occupancy_rule.py`, `occupancy_override.py`, `tools/get_person_model.py`, `tools/occupancy_bench.py`, `tools/mediapipe_person.py` and five test files. It also changed `occupancy.py`. On that branch the main folder has 25 application Python files, `tools/` has six, and `tests/` has 29 Python files.

## Application files

| File | Purpose |
|---|---|
| `monitor.py` | Starts the program with a serial port or `--demo`. Reads command options, loads settings, and starts monitoring. Connects storage, patient rules, the camera, dashboard acknowledgment and silence requests, the local alarm, and the BSEC state keeper (`bsec_state_store.py`), which answers the board's state requests through the same send path as alarm commands. |
| `settings.py` | Reads the three YAML settings files. Rejects missing or invalid settings and unworkable timing combinations. Holds the timing defaults, the system defaults and the demonstration system values. Imports PyYAML only when it reads a file. |
| `serial_transport.py` | Opens the selected serial port. Collects complete lines and retries the connection after errors. Sends alarm commands with a write limited to about 20 ms; a failed send is reported, never raised. |
| `serial_parser.py` | Reads each text message. Identifies a valid reading, sensor error, incomplete reading, alarm reply, BSEC state line (`bsec_state`, `bsec_state_request`, `bsec_state_restored`), the board's `bsec_state_save_failed` error, or ignored message. The `bsec_state_save_failed` error is its own kind, not a sensor error. |
| `measurements.py` | Checks the four measurement values. Retains the last complete reading, its receipt time, and the latest input condition. |
| `communication_fault.py` | Tracks messages from the ESP32. Raises an alert when communication stops and handles acknowledgment. |
| `sensor_fault.py` | Tracks repeated measurement errors. Raises a sensor alert after the waiting period and clears it after a valid reading. |
| `gas_readiness.py` | Checks the Bosch status fields. Reports gas warm-up and calibration status. Keeps the reported Bosch air-quality index, 0 to 500, or none. |
| `air_quality.py` | Decides whether the Bosch index is current, calibrating or unavailable (current from accuracy 2), and picks its display word. |
| `monitoring_state.py` | Keeps the reading, fault states, and gas status together. Applies each message to the correct parts. Keeps the board's latest alarm reply, which is not a reading and not communication contact. Keeps the latest BSEC state line of each kind with a running count; these lines are not communication contact either. |
| `monitoring_loop.py` | Repeats serial reads and fault checks. Continues checking faults when no messages arrive. |
| `status_output.py` | Prepares the status report. Includes measurements, reading age, receipt time, connection state, alerts, gas status, and dust status. |
| `dust.py` | Reads Sharp dust records. Reports dust voltage, age, and status. Tracks the clean-air baseline (lowest recent voltage) and calculates the dust estimate. |
| `room_store.py` | Stores status, readings, and events in SQLite. Loads, checks, and saves the patient profile file, including its optional short label. |
| `room_session.py` | Applies patient limits and the sustained duration, and the air-quality and dust system limits with their own hold times. Requires occupied status and a fresh reading. Publishes the air-quality and dust-estimate states. Logs alert, fault and profile-change events. Runs the local alarm after the limit state is built and logs silence and alarm reachability events. |
| `alarm.py` | Decides the local alarm level (0 off, 1 LED, 2 LED and buzzer), applies silence to the limit alerts shown, and tracks whether the board confirmed the level. Has no I/O. |
| `bsec_state_store.py` | Keeps the board's Bosch BSEC calibration state in `<database name>.bsec_state.json` next to the database. Writes a temporary file and renames it. Answers each board request with one line: `BSEC_STATE,<hex>` when the file exists and the BSEC version matches, otherwise `BSEC_STATE,NONE` with the reason (no saved state, version mismatch, file damaged). Reports saves, replies and restore results as events and a status block for the System page. |
| `occupancy.py` | Camera worker on branch `feature/occupancy`. Checks one camera frame every 10 seconds with the YOLOX person detector (`person_detector.py`), feeds the result to the occupancy rule, and records a failed check once with its reason. Saves no frames. |
| `person_detector.py` | YOLOX person detector on `cv2.dnn` (OpenCV zoo model, Apache 2.0). Checks the model file and its pinned SHA-256, letterboxes the frame, decodes the output, keeps class 0 (person) above the confidence after non-maximum suppression. Keeps no frame. |
| `occupancy_rule.py` | Pure rule: check results with times in, automatic state out. Entry needs 75 % sightings in a full 120 s window. The hold lasts 900 s from the last sighting. Reports occupied, not seen or unknown, with the confirmation progress. No I/O and no clock reads. |
| `occupancy_override.py` | The manual occupancy setting: parses the stored request, applies it until 900 s after it was set, logs set, cleared and expired events, and tells the camera rule about a manual "Occupied" so the hold starts. |
| `simulated_input.py` | Produces simulated BME680 records with a Bosch index (calibrating at start, then a scripted episode) and dust records with a scripted episode for `--demo` and echoes alarm commands like the board would. Like the firmware it asks for the BSEC state at start, confirms a `BSEC_STATE,<hex>` reply, and sends one stand-in state line (not a real Bosch state) after 60 s. Tests can make it silent or failing. It is not a hardware driver. |
| `dashboard.py` | Serves the local dashboard on 127.0.0.1. Reads SQLite. Saves patient limits, acknowledgment requests, and alarm silence requests. Reports alarm health and the Bosch calibration row (saved time and accuracy, or not saved yet, and the last request result). With `--online` also serves the view-only online origin (sign-in, CSRF, protective headers) and starts the tunnel; `--set-password` writes the online password hash. |
| `online_auth.py` | Writes and reads the git-ignored online password file (werkzeug hash and session key), limits failed sign-ins in memory, and makes and compares CSRF tokens. |
| `online_tunnel.py` | Starts `cloudflared` without a shell, reads the quick-tunnel link from its output, reports off, starting, active or failed, restarts it at most twice, and stops it on exit. |

The state means the program's current stored information.
The serial parser identifies the message type.
The monitoring state code then updates the stored information.
The monitoring loop decides when those actions occur.

Communication faults and sensor faults remain separate because their recovery rules differ.
A sensor error message proves that communication continues.
A valid reading clears a sensor alert automatically.
Communication recovery does not dismiss an outstanding communication alert.
The dashboard acknowledgment control dismisses it after contact recovers.

The monitor owns all sensor input and alert decisions.
The dashboard reads the SQLite file that the monitor writes.
Closing the dashboard does not stop monitoring.

## Tools

| File | Purpose |
|---|---|
| `tools/check_setup.py` | Reports Python package versions and visible devices. It does not prove that the complete application works. |
| `tools/read_sensor.py` | Opens a selected serial port and prints received JSON records. It is a separate diagnostic tool. |
| `tools/get_person_model.py` | Downloads the YOLOX person model (and with `--mediapipe` the MediaPipe model for the bench) from the OpenCV zoo to `models/` and checks the pinned SHA-256. |
| `tools/occupancy_bench.py` | Captures live webcam frames, one per second, and prints the YOLOX result and top score per frame (and HOG and MediaPipe results for comparison). Stores no frame. |
| `tools/mediapipe_person.py` | MediaPipe person detector on `cv2.dnn`. Used by the bench only. No production module imports it. |
| `tools/sensor_check.py` | Read-only bench check of the board's serial lines for a set time. Prints PASS, FAIL, NOT SEEN or INFO for readings, gas change, dust input, Bosch accuracy and BSEC state lines. Refuses to run when another program holds the port. |

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
| `tests/test_serial_transport.py` | Checks line assembly, invalid input, connection retry, and connection cleanup. Checks that a send failure, a short write, or a full pseudo-terminal buffer returns promptly without an error. |
| `tests/test_monitoring_loop.py` | Checks the running loop with controlled time and simulated serial input. |
| `tests/test_dust.py` | Checks dust record classification, retention, missing dust and BME680 reports, recovery, the estimate and the clean-air baseline. |
| `tests/test_air_quality.py` | Checks the Bosch index in the reading record, older records without it, the current and calibrating rule, word bands and the system settings file. |
| `tests/test_system_limits.py` | Checks the air-quality and dust-estimate blocks, their sustained alerts, pauses and reasons, the buzzer and silence, stored series, the simulator episode, the profile label and the profile-change event. |
| `tests/test_room_software.py` | Checks the simulated alert and recovery, occupancy and profile-change timer restarts, invalid-profile handling, and event history for contact loss and acknowledgment. Checks active and pending alert details, limit-monitoring reasons, alert-end reasons, the acknowledgment event, trends, event paging, retention, the camera interval, and the legacy profile check. |
| `tests/test_dashboard.py` | Checks the dashboard page, profile saving and rejection, the cross-origin check, and acknowledgment requests. Checks the `/api/room` response, system health, event paging, form error messages, and incomplete acknowledgment status. Checks the silence request, its rejections, and the alarm health entry. |
| `tests/test_online_settings.py` | Checks the online settings defaults and their validation. |
| `tests/test_online_auth.py` | Checks that the password file holds a hash, not the password; the rate limit; and CSRF token comparison. |
| `tests/test_online_tunnel.py` | Checks link parsing from sample cloudflared output, state changes with a fake process, the missing program, bounded restarts and stop. |
| `tests/test_online_dashboard.py` | Checks that the online origin allows reading, refuses controls without sign-in or with a bad CSRF token, sends its headers, locks controls with words, rate-limits sign-in and shows no secret; and that the local origin is unchanged. |
| `tests/test_alarm.py` | Checks alarm levels, command timing, confirmation, timeout, failed sends, reconnect, silence, and events. |
| `tests/test_bsec_state.py` | Checks the BSEC state lines in the parser, that they do not reset the communication timer, the file write and rename, missing, damaged and mismatched files, one reply per request, the logged events, the simulated board, the System page row, and an impossible `saved_at` time. |
| `tests/test_sensor_check.py` | Checks the sensor check tool: line counting, each check result, the stuck gas value, the dust floor, the port-holder check and the printed report. |
| `tests/test_person_detector.py` | Checks the model file and hash check, the YOLOX decoding, the threshold and the person class. |
| `tests/test_occupancy_rule.py` | Checks entry confirmation, the hold, camera failure, the progress counts and the manual hold start. |
| `tests/test_occupancy_override.py` | Checks request parsing, expiry, the events and the camera hold start. |
| `tests/test_occupancy_bench.py` | Checks the bench tool output without a camera. |
| `tests/test_mediapipe_person.py` | Checks the MediaPipe bench detector decoding. |
| `tests/test_alarm_link.py` | Checks the simulated board and the alarm through the session and the monitor loop. Shows that failing, silent and raising transports change no reading, fault check, limit alert, event, or published status. |

The test filenames describe the behavior under test.
They do not require an application file with the same name.
The original test filenames and all 301 test cases remain unchanged.
Only their module imports changed.
On 15 November `tests/test_runtime_settings.py` gained 48 cases for the timing settings.
The three newer test files contain 41 cases. The full suite contains 401 cases.
On 15 November the local alarm added 60 cases: 12 in `tests/test_alarm.py`, 9 in `tests/test_alarm_link.py`, and 39 in existing files (runtime settings 9, serial parser 9, message router 3, serial transport 6, dashboard 12). The full suite contains 461 cases.
On 15 November the air-quality and dust-estimate step added 76 cases: 37 in `tests/test_air_quality.py`, 28 in `tests/test_system_limits.py`, 5 in `tests/test_dust.py` and 6 in `tests/test_dashboard.py`. The full suite reported 538 passed, with and without `-W error`.

On 19 November online access added 73 cases: 14 in `tests/test_online_settings.py`, 12 in `tests/test_online_auth.py`, 12 in `tests/test_online_tunnel.py` and 35 in `tests/test_online_dashboard.py`. The full suite reported 634 passed, with and without `-W error`.

On 20 November the BSEC state save added 64 cases: 58 in `tests/test_bsec_state.py` and 6 in `tests/test_serial_parser.py`. On 23 November the full suite reported 752 passed on branch `feature/bsec-state`.

On 25 November the sensor check tool added `tests/test_sensor_check.py`. The full suite reported 798 passed on `feature/bsec-state` and on `fix/dust-led-i2c-restart`.

On 27 November the occupancy work added five test files (49 cases) and changed existing ones. The full suite reported 876 passed on `feature/occupancy`.

## Other important files

| File or folder | Purpose |
|---|---|
| `config/alerts.yaml` | Stores communication and sensor-error waiting periods. |
| `config/system.yaml` | Air-quality and dust limits (off as shipped), word bands and levels, dust sensitivity, baseline rule, and the dust floor `dust.disconnected_below_mv` (100 mV): a lower voltage is "no reading". |
| `config/runtime.yaml` | Stores host polling, connection retry, and periodic fault-check intervals, and the optional timing keys, including the alarm confirmation timeout. |
| `requirements.txt` | Lists the required Python packages and versions. |
| `firmware/room_environment_safety_control_bme680.ino` | Runs on the ESP32. Reads the sensor and sends measurements or errors. Asks the laptop for the BSEC state at start and sends it at IAQ accuracy 3. |
| `firmware/bsec_board_config.h` | Requires the ESP32-S3. Stores all board pins, the buzzer polarity, supply, and reporting intervals. |
| `firmware/bsec_serial_format.h` | Converts firmware measurements and Bosch status into JSON text. |
| `firmware/sharp_dust.h` | Sharp dust acquisition: LED drive GPIO4 (active LOW, direct wiring), analog input GPIO5. Passed on the board on 25 November 2026 after the LED polarity fix (60 of 60 records, 892.7 to 1135.0 mV). The LED timing is not checked on an oscilloscope. |
| `firmware/sharp_dust_limits.h` | Pure dust sample rule: timing window, ADC limit, divider. |
| `firmware/tests/test_sharp_dust_limits.cpp` | Checks `firmware/sharp_dust_limits.h` on a computer with g++. |
| `templates/room.html` | Dashboard page layout and patient limits form. |
| `static/room.js` | Refreshes the dashboard every 10 seconds and draws the 24-hour trend. |
| `static/room.css` | Dashboard styles. |
| `firmware/tests/test_bsec_serial_format.cpp` | Checks firmware message formatting on a computer without the sensor. |
| `firmware/alarm_command.h` | Parses alarm commands with a fixed buffer, reads `Serial` with a byte bound, maps the level to LED and buzzer, and formats the reply. Used by the sketch. |
| `firmware/tests/test_alarm_command.cpp` | Checks `firmware/alarm_command.h` on a computer with g++. |
| `firmware/host_command.h` | Reads the host lines `ALARM,<0|1|2>`, `BSEC_STATE,<hex>` and `BSEC_STATE,NONE` with a fixed buffer (up to 511 characters), formats the BSEC state as hex, and holds the state-save rule (accuracy 3, then every 6 hours). Used by the sketch. |
| `firmware/tests/test_host_command.cpp` | Checks `firmware/host_command.h` on a computer with g++. |
| `firmware/bus_recovery.h` | The I2C bus restart rule (`roomBusRestartDue`): restart after 10 s with no valid reading, at most every 30 s. Used by the sketch. On the board on 25 November 2026 it recovered the BME680 once and failed the second time. |
| `firmware/tests/test_bus_recovery.cpp` | Checks `firmware/bus_recovery.h` on a computer with g++. |
| `tests/fixtures/bsec_reading.json` | Supplies an example reading for tests. It is not a physical measurement. |
| `README.md` | Gives the project entry point and current status. |
| `reference_files/` | Stores the manual reference, project plan, handoff, comparisons, and verification records. |
| `docs/superpowers/` | Stores detailed component designs and implementation checklists. |
| `docs/SHARP_DUST_INTEGRATION.md` | Describes dust wiring, the estimate and baseline, and checks. |

## Effect of the merge

Related functions now share files. Their behavior remains unchanged.
Function and class names remain unchanged.
The program still starts with monitor.py and an explicitly selected serial port.
The two settings files remain separate.
No dependency versions, firmware files, or alert rules changed.
The merge did not add camera processing, patient rules, a dashboard, or notifications.
The later branch `feature/sharp-dust-integration` adds camera processing, patient rules, storage, and a dashboard. It adds no notifications. Branch `feature/local-alarm` adds the host side of a local LED and buzzer alarm.

Run the existing suite from the project folder with the approved environment active:

```bash
python3 -m pytest
```

The original eleven test files contain the original 301 cases and 48 new timing-settings cases.
On 15 November 2026 the full suite reported 401 passed after the dashboard data contract, and 461 passed after the local alarm host side. See the [15 November verification record](LINUX_VERIFICATION_2026-11-15.md).
Hardware operation requires separate physical checks.
