# Room Environment Safety Control - Project 8

## What this is

This project monitors the environment of one occupied room.
An ESP32-S3 board reads a BME680 sensor and a Sharp dust sensor. It sends the readings to a laptop over USB serial.
The laptop runs the monitor, a local Flask dashboard and a SQLite store. A webcam on the laptop gives occupancy.
The monitor commands a local alarm on the board: an LED and a buzzer.
This is a course project. It is not a medical device. The project supplies no patient limits.

## How it works

```text
BME680 (I2C GPIO8/9)      Sharp dust sensor (Vo GPIO5, LED GPIO4)
          \                    /
     ESP32-S3 firmware (firmware/room_environment_safety_control_bme680.ino)
       - one JSON reading line about every 3 s (Bosch BSEC low-power mode)
       - one JSON dust line every 3 s
       - reads ALARM,<0|1|2> and BSEC_STATE lines from the laptop
          |  USB serial, CH343 bridge, /dev/ttyACM0, 115200 baud
          v
serial_transport.py   read lines, retry the port, send alarm and BSEC lines
serial_parser.py      classify each line: reading, error, alarm reply, BSEC line
dust.py               dust lines, the 100 mV floor, baseline and estimate
          v
monitoring_loop.py    poll the port, run the fault check every 5 s
monitoring_state.py   apply each line to readings, communication and sensor timers
room_session.py       patient and system limits, occupancy gate, events, alarm level
          v
room_store.py         SQLite: status, readings (kept 7 days), events (kept)
status_output.py      the status record the monitor publishes
          v
dashboard.py          Flask pages on 127.0.0.1:5000 and GET /api/room

alarm.py              alarm level 0/1/2, silence, confirmation -> ALARM line to the board
occupancy.py          camera check every 60 s (OpenCV people detector, no frame saved)
bsec_state_store.py   keeps the Bosch calibration state in a file, sends it back at board start
online_tunnel.py      optional Cloudflare quick tunnel to a view-only copy of the dashboard
```

The monitor (`monitor.py`) and the dashboard (`dashboard.py`) are two programs. The dashboard can stop while monitoring continues. They share two files next to the database:

- the SQLite file (default `room.sqlite3`)
- the patient profile `<database name>.profile.yaml` (for example `room.profile.yaml`). The dashboard writes it. The monitor reads it (`room_store.py`).

The monitor also keeps the Bosch calibration state in `<database name>.bsec_state.json` (`bsec_state_store.py`). The dashboard does not open that file. It gets the state facts from the monitor status.

## Repository map

Every entry below exists on this branch, except `config/online_secret.yaml`, which git ignores. "Open it when" says when you need the file.

| Path | What it does | Open it when |
|---|---|---|
| `monitor.py` | Starts the monitor with `--port` or `--demo`. Connects storage, rules, camera, alarm, BSEC state and dashboard requests. | You run or change the monitor. |
| `dashboard.py` | Flask dashboard on 127.0.0.1:5000: five pages, `/api/room`, limit form, acknowledge and silence requests, `--online`. | You change the pages or the API. |
| `serial_transport.py` | Opens the port, collects complete lines, retries after errors, sends lines with a short write limit. | The serial link fails. |
| `serial_parser.py` | Classifies one line: valid reading, sensor error, incomplete reading, alarm reply, BSEC state lines, ignored. | You add a firmware message. |
| `measurements.py` | Checks the four BME680 values and keeps the last complete reading. | A reading is rejected. |
| `monitoring_state.py` | The combined state. Applies each line to the reading, the communication timer and the sensor timer. | You change what counts as contact. |
| `monitoring_loop.py` | The poll loop and the periodic fault check. | You change loop timing. |
| `communication_fault.py` | Communication timeout and acknowledgment (pure logic). | You change the communication alert. |
| `sensor_fault.py` | Sensor-error timing and recovery (pure logic). | You change the BME680 alert. |
| `gas_readiness.py` | Bosch status fields: warm-up, accuracy, index. | You change gas status labels. |
| `air_quality.py` | Decides if the Bosch index is current or calibrating. Picks the word band. | You change the air-quality display rule. |
| `dust.py` | Dust lines, the not-connected floor, dust status, clean-air baseline and estimate. | You change dust handling. |
| `room_session.py` | Patient and system limits, sustained timers, occupancy gate, fault events, alarm level. | You change any alert rule. |
| `room_store.py` | SQLite store and the patient profile file. | You change storage. |
| `status_output.py` | Builds the published status record. | You add a status field. |
| `alarm.py` | Alarm level, silence and board confirmation (pure logic). | You change the local alarm. |
| `occupancy.py` | Camera check with OpenCV's default people detector. Saves no frame. | You change occupancy. |
| `bsec_state_store.py` | The Bosch calibration state file `<database name>.bsec_state.json`, replies to the board's requests. | You change the BSEC save or restore. |
| `online_auth.py` | Online password file, sign-in rate limit, CSRF tokens. | You change online sign-in. |
| `online_tunnel.py` | Starts and watches `cloudflared`. | You change online access. |
| `settings.py` | Loads and checks the three YAML files. Holds the defaults and the demo values. | You add a setting. |
| `simulated_input.py` | Simulated board records for `--demo`. | You change the demo. |
| `config/runtime.yaml` | Host timing: fault check 5 s, serial retry 5 s, poll 0.05 s, reading gap 6 s, dashboard overdue 15 s and refresh 10 s, camera 60 s, retention 7 days, alarm confirmation 2 s, online access options. | You tune host timing. |
| `config/alerts.yaml` | Communication timeout and sensor-error timeout (both 120 s). | You change the fault timeouts. |
| `config/system.yaml` | Air-quality and dust limits (off as shipped), word bands, dust sensitivity, baseline rule, the 100 mV dust floor. | You set system limits. |
| `config/online_secret.yaml` | Not in git. Created by `dashboard.py --set-password`. Holds the online password hash. | Never edit it by hand. |
| `templates/` | Dashboard HTML: shared layout `room.html`, pages `overview`, `trends`, `events`, `limits`, `system`, the sign-in page and the online footer. | You change page markup. |
| `static/` | `room.js` (page logic), `chart.js` (the project's own SVG line charts), `room.css`. | You change page behaviour or style. |
| `firmware/` | The ESP32-S3 sketch, its headers and host tests. See the [firmware guide](firmware/README.md). | You change or flash the board. |
| `firmware/*.ino` | The sketch: BSEC set-up, readings, errors, dust report, alarm outputs, BSEC state, I2C bus restart. | You change board behaviour. |
| `firmware/*.h` | `bsec_board_config.h` (pins, polarity, intervals), `bus_recovery.h` (I2C restart rule), `alarm_command.h`, `host_command.h`, `bsec_serial_format.h`, `sharp_dust.h`, `sharp_dust_limits.h`. | You change one board rule. |
| `firmware/tests/` | Five C++ host tests, built with g++ on Linux (no board). | You change a header. |
| `tools/sensor_check.py` | Read-only bench check of the board's serial lines: readings, gas change, dust input. | You test the board. |
| `tools/read_sensor.py` | Prints the board's records from a serial port. | You want raw lines. |
| `tools/check_setup.py` | Prints platform, Python, package and port facts. | You check a new laptop. |
| `tests/` | The Python test suite (pytest) and `tests/fixtures/`. | You change Python code. |
| `docs/SHARP_DUST_INTEGRATION.md` | Dust wiring, acquisition, estimate and baseline. | You touch the dust sensor. |
| `docs/superpowers/specs/` | Designs, one file per feature, with dates. | You need the reason for a rule. |
| `docs/superpowers/plans/` | Implementation plans for those designs. | You continue a feature. |
| `reference_files/` | Verification records per date, the Python file guide, the course reference, the implementation plan, the Linux handoff and the VIGIL comparison. | You need evidence or history. |
| `README_HUMAN.md` | A longer guide for people. | You want more background. |
| `DESIGN.md`, `.impeccable/design.json` | The dashboard design system. | You change the page look. |
| `requirements.txt` | Pinned Python packages. | You set up the environment. |

The [Python file guide](reference_files/PYTHON_FILE_GUIDE.md) describes every Python file and test file.

## Readings

| Source | Fields | How often |
|---|---|---|
| BME680 through Bosch BSEC2 | `temp_c`, `humidity_pct`, `pressure_hpa`, `gas_ohms`, and `bsec`: `stabilization_status`, `run_in_status`, `iaq_accuracy` (0 to 3), `iaq` (Bosch index, 0 to 500) | About every 3 s. BSEC low-power mode sets the time. |
| Sharp GP2Y1010AU0F | `sensor_mv`: the mean sensor-side voltage of the accepted samples (the firmware undoes the 2:1 divider), with `samples` and `rejected_samples`. Or a `dust_error` line. | Every 3 s. One LED pulse every 10 ms. |

The host stores temperature, humidity, pressure, gas resistance, the Bosch index (only while it is current), the dust voltage and the dust estimate.
The dust estimate is `max(0, sensor_mv - baseline_mv) * 1000 / 5000` µg/m³. The baseline is the lowest fresh voltage in the last 24 hours. The estimate appears only after 10 minutes of unbroken fresh dust records.
Raw gas resistance is not a calibrated concentration. The dust estimate is not PM2.5.

Freshness rules (from `config/runtime.yaml`, `config/alerts.yaml` and the code):

| Rule | Value | Effect |
|---|---|---|
| Reading gap (`reading_gap_limit_s`) | 6 s | A BME680 reading older than 6 s is not current. A gap of more than 6 s between readings restarts the sustained timers. The same rule applies to dust records. |
| Sensor timeout (`sensor_error_timeout_s`) | 120 s | 120 s of BME680 errors raises the BME680 alert. 120 s with no dust reading at or above the floor raises the dust alert. |
| Communication timeout (`communication_timeout_s`) | 120 s | 120 s with no reading, sensor error or dust line raises the communication alert. |
| Fault check (`fault_check_interval_s`) | 5 s | Timers, dashboard requests and the alarm resend run at this interval. |
| Camera (`camera_interval_s`) | 60 s | One camera check every 60 s. An observation older than 65 s becomes unknown. |
| Dashboard refresh (`dashboard_refresh_s`) | 10 s | The page reloads its data every 10 s. |
| Monitor overdue (`status_stale_after_s`) | 15 s | A monitor status older than 15 s shows as "Monitor overdue". |
| Alarm confirmation (`alarm_confirm_timeout_s`) | 2 s | With no board reply in 2 s the alarm shows as unreachable. |
| Reading retention (`readings_retention_days`) | 7 days | The monitor deletes older readings every hour. Events are kept. |

The laptop settings do not change the board's acquisition timing.

## Alerts and states

Three alert families stay separate: communication, sensor and limit alerts.
Only limit alerts sound the buzzer. Communication, BME680 and dust faults light the LED and show on the dashboard without sound. A patient-profile fault does not light the LED (`room_session.update_alarm`).

| Alert | Starts when | Ends when | Local alarm |
|---|---|---|---|
| Communication | No reading, sensor error or dust line for 120 s. The first wait starts when the monitor starts. Alarm replies and BSEC state lines do not count as contact. | A person acknowledges it on the dashboard after contact is back. Contact alone does not end it. The dashboard cannot acknowledge during an outage. | Level 1 (LED). |
| BME680 | 120 s of sensor errors or incomplete readings with no valid reading. Repeated errors do not restart the wait. The wait pauses while communication is timed out. Also: no BME680 reading for 120 s while dust lines still arrive. | The next valid reading, with no acknowledgment. | Level 1 (LED). |
| Dust | 120 s with no dust reading at or above the floor. A voltage below `dust.disconnected_below_mv` (100 mV), a 0 mV record and the board's `dust_input_at_zero` line are not readings. When the last record was below the floor, the page says "Dust sensor not connected". During a communication timeout the dust alert stays off: the communication alert covers it. | The next dust reading at or above the floor. | Level 1 (LED). |
| Patient profile | The profile file is invalid. Monitoring continues on the last valid profile. | A valid file. | None. Dashboard and event only. |
| Patient limit (temperature, humidity, pressure) | A value stays below the lower limit or above the upper limit for the sustained duration. The room must be occupied and the reading current. | One in-range reading, or the value crosses to the other limit. A stale reading, a gap over 6 s, unknown occupancy or a changed profile also ends the alert and restarts the timer. | Level 2 (LED and buzzer). Level 1 after "Silence alarm". |
| System limit: air quality (Bosch index) | The index stays above `air_quality.upper_limit` for `hold_s`. The index must be current (accuracy 2 or 3) and the room occupied. Off as shipped (no value set). | As for patient limits. "Calibrating" also ends it. | Level 2. Level 1 after silence. |
| System limit: dust estimate | The estimate stays above `dust.upper_limit` for `hold_s`. The baseline must exist and the room must be occupied. Off as shipped. | As for patient limits. A missing baseline also ends it. | Level 2. Level 1 after silence. |

Local alarm levels (`alarm.py`, `firmware/alarm_command.h`):

| Level | When | LED | Buzzer |
|---|---|---|---|
| 0 | No alert. The board also starts at 0. | Off | Off |
| 1 | A silenced limit alert, or an active communication, BME680 or dust alert. | On | Off |
| 2 | At least one limit alert that is not silenced. | On | On |

- The host sends `ALARM,<level>` on each change and again at each fault check (every 5 s), so a board reset is corrected.
- "Silence alarm" on the dashboard stops the buzzer for the limit alerts shown. The LED stays on. A new limit alert sounds again. The silence is logged.
- The dashboard shows the alarm as confirmed, pending or unreachable. Unreachable means the port is not connected, the write failed, or no reply came in 2 s.
- Link lost: when the board gets no valid `ALARM` command for 30 s, the LED blinks (1 s on, 1 s off). The buzzer keeps its last state. The next valid command ends the blink.
- No buzzer is connected now. On this bench, level 2 therefore gives only the LED.

Occupancy (this branch, `occupancy.py` and `monitor.py`):

| State | When | Effect |
|---|---|---|
| Occupied | The result of the latest camera check is "person found", and that check is no older than 65 s (`occupancy.current`). In `--demo` the room is always occupied. | Limit checks run. |
| Unknown | The latest check found no person (a newer check with no person replaces an older "person found"), a failed capture, a latest check older than 65 s, or no `--camera` option. | Patient-limit, air-quality and dust-limit checks pause. Running breaches end with an event. Faults do not depend on occupancy. |

The dashboard has text for "Not occupied", but the monitor on this branch never sends that state.
A new occupancy design (a new detector, a hold time, a "No person seen" state and a manual override) is in progress on branch `feature/occupancy`. It is not on this branch. See the [occupancy design](docs/superpowers/specs/2026-11-20-occupancy-detector-override-design.md).

Other states on the dashboard:

- **Calibrating** (air quality): Bosch accuracy is 0 or 1. The page shows no index value. The air-quality check pauses.
- **Establishing baseline** (dust): fewer than 10 minutes of unbroken fresh dust records. The page shows no estimate. The dust check pauses. A dust fault, a gap over 6 s or a monitor restart starts the baseline again.
- **Limit monitoring off or paused**: no profile, no limits, a reading that is not current, or unknown occupancy. The page says which.

## Run it

Use the project environment (`env/bin/python`). Run the monitor and the dashboard in separate terminals.

Demo, no hardware:

```text
python monitor.py --demo
python dashboard.py --demo
```

Open http://127.0.0.1:5000. The demo uses its own database (`room-demo.sqlite3`). It simulates an occupied room, BME680 readings and dust voltage every 3 s. On a fresh demo database the temperature crosses the example limit at 18 s, raises an alert at about 27 s, and returns to range at about 60 s. The demo also uses demonstration system limits (air quality 150 for 30 s, dust 100 µg/m³ for 30 s). These are not recommendations.

With the board:

```text
python monitor.py --port /dev/ttyACM0 [--camera 0] [--db FILE]
python dashboard.py [--db FILE]
```

Both programs must use the same `--db` file (default `room.sqlite3`). Without `--camera`, occupancy is always unknown, so limit alerts never start.

**Run the host from a checkout that matches the firmware.** On 25 November 2026 a "Dust alert cleared" event at 01:42 was false. The monitor ran from a folder on branch `feature/occupancy`. That host code has no 100 mV floor, so it accepted 7 to 18 mV records as dust readings. On `feature/bsec-state` and later, a value below 100 mV is "no reading".

Online access (opt-in, view-only): see [Online access](#online-access-opt-in-view-only).

Sensor check (stop the monitor first):

```text
python tools/sensor_check.py --port /dev/ttyACM0 [--seconds 120] [--breath] [--log FILE]
```

It only reads. It prints PASS, FAIL, NOT SEEN or INFO for readings, gas change, dust input, Bosch accuracy and BSEC state lines. See the [firmware guide](firmware/README.md#sensor-check).

## Hardware and status (25 November 2026)

The board is an ESP32-S3 (QFN56, revision v0.2) with 16 MB flash and 8 MB embedded PSRAM, an N16R8-type module (read by esptool, 17 November 2026). The USB port goes through a CH343 bridge (USB 1a86:55d3), `/dev/ttyACM0` on Linux. The exact development board model is not identified.

| Function | Pin | Note |
|---|---|---|
| BME680 I2C SDA / SCL | GPIO8 / GPIO9 | BME680 at address 0x76, chip id 0x61, variant 0 (diagnostic, 25 November 2026). 3.3 V supply. |
| Dust Vo (through a 2:1 divider) | GPIO5 | ADC1 channel 4. |
| Dust LED (sensor pin 3) | GPIO4 | Wired directly. LOW turns the LED on (measured 25 November 2026). `ROOM_DUST_LED_ACTIVE_LOW = true`. Push-pull output. |
| Alarm LED | Onboard RGB LED (`LED_BUILTIN`, GPIO48 by default) | Lit white as commanded (20 November 2026). |
| Buzzer module | GPIO7 | No buzzer connected. GPIO7 drives nothing. |

Build options: `esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default`. ESP32 core 3.3.12, BSEC2 1.10.2610, BME68x 1.3.40408.
The board runs firmware `49029f2` (branch `fix/dust-led-i2c-restart`) since 25 November 2026.

| Item | Result on the board | Date |
|---|---|---|
| Serial link, alarm replies (`ALARM,0/1/2` in about 10 ms, `ALARM,9` no reply) | Pass | 17 and 20 Nov |
| Onboard RGB LED off or white as commanded; link-lost blink after 30 s | Pass | 20 Nov |
| Monitor dust fault at 120 s with level 1 confirmed; five dashboard pages and `/api/room` HTTP 200 | Pass | 20 Nov |
| BME680 temperature, humidity and pressure every 3.0 s | Pass (58 readings in 180 s) | 25 Nov |
| Dust input after the LED polarity fix | Pass: 60 of 60 records, 892.7 to 1135.0 mV sensor side, mean 1018.9 mV | 25 Nov |
| Dust estimate in the monitor status | Current after the 10-minute baseline: baseline 921.5 mV, estimate about 4 µg/m³, "low" (monitor output at 02:40) | 25 Nov |
| BME680 gas resistance | Fail: 55 of 58 readings stuck at 12917166.00 ohm (raw gas ADC 0). See [BME680 gas: open decision](#bme680-gas-open-decision). | 25 Nov |
| Bosch index (IAQ) | Accuracy 2 at 02:40:50 and 3 at 02:41:50. The dashboard then shows the index as current (about 50). It has no meaning: the gas reading stayed stuck (552 of 556 stored readings, 02:28 to 02:56). Open issue. | 25 Nov |
| BSEC state save on the board | Pass: event `bsec_state_saved` "accuracy 3, BSEC 2.6.1.0" at 02:41:50. The state is from a stuck gas reading. | 25 Nov |
| I2C bus restart (`i2c_bus_restarted`) | Worked once: the BME680 stopped at 02:49:20, two restarts, start succeeded, `bsec_state_restored` from the RAM copy, readings again at 02:50:03 (gap 43 s). Failed the second time: the BME680 stopped at 02:56:48, and each restart (about every 30 s) gave `bsec_initialization_failed`. BME680 alert at 02:58:50 (status at 02:59). | 25 Nov |
| BSEC state restore from the laptop file after a board start | Not checked | — |
| Buzzer, GPIO7, buzzer polarity | Not checked: no buzzer connected | — |
| Camera and occupancy detector | Not checked with a real camera on this branch | — |
| Dust LED timing on an oscilloscope; GPIO4 voltage and current with a meter | Not checked | — |
| Signed-in control request through a real tunnel | Pass: save limits, silence alarm and acknowledge got HTTP 403 without sign-in and HTTP 303 after sign-in with the CSRF token. The test used a scratch database and a temporary password. | 20 Nov |

Read the [25 November verification record](reference_files/LINUX_VERIFICATION_2026-11-25.md) for the numbers, commands and flash sizes.

## BME680 gas: open decision

A heater sweep on 25 November 2026 (forced mode, no BSEC) gave real gas values at 200, 240 and 260 °C (18.4 to 46.5 kΩ). At 280 °C, 19 of 20 readings failed. At 300 °C, 17 of 20 failed. At 320 °C, 60 of 60 failed (all 12917166 ohm). The heater time (50, 100 or 150 ms) made no difference at 320 °C. A failure did not carry over to the next cooler step. There were no I2C errors.

Inference: the failure follows the heater drive. The cause is a supply sag, or a contact or sensing layer that fails when hot. The data cannot tell these apart.
Inference: the BSEC configuration in use heats to about 320 °C. Its readings show the same stuck value as the 320 °C sweep step. So the Bosch air-quality index cannot work with this module as it is.

Options (no option chosen, 25 November 2026):

- **B, hardware:** a person adds a 10 µF (plus 100 nF) capacitor at the BME680 power pins, uses a stronger 3.3 V supply, or replaces the module. Then run `tools/sensor_check.py` again.
- **C, software:** run the gas heater at or below 260 °C without BSEC. This gives a real gas resistance but no Bosch index. The dashboard then needs its own simpler indication. It needs a design first.

New evidence, 25 November 2026, 02:49 to 02:59: the BME680 dropped off the I2C bus twice. The bus restart brought it back once, not the second time. Inference: this leans toward a hardware cause (supply or contacts). It is not proven.

Temperature, humidity and pressure work while the sensor answers. See the [decision record](docs/superpowers/specs/2026-11-25-bme680-gas-heater-decision.md).

## Current status

The room software is complete in software: SQLite storage, patient limits, sustained-breach alerts, camera occupancy, the five-page dashboard, the dust path, the local alarm, the BSEC state on the laptop, online access and the sensor check tool.
Automated tests and the simulator verify it. The board checks are in the table above.

Verification records:

- [25 November 2026](reference_files/LINUX_VERIFICATION_2026-11-25.md): sensor check runs, dust LED and BME680 diagnostic, heater sweep, flashes.
- [17 November 2026](reference_files/LINUX_VERIFICATION_2026-11-17.md): first flash and serial link check, no sensors.
- [15 November 2026](reference_files/LINUX_VERIFICATION_2026-11-15.md): software results.
- [8 November 2026](reference_files/LINUX_VERIFICATION_2026-11-08.md): virtual serial and compilation.
- The 20 November bench results are in the [firmware hardware checklist](firmware/README.md#hardware-checklist).

| Check | Recorded result |
|---|---|
| Python test suite, `fix/dust-led-i2c-restart` | 798 passed (25 November). |
| Python test suite, `feature/bsec-state` | 798 passed after the sensor check tool merge (25 November). 752 passed on 23 November. |
| Firmware host tests | Five programs (`test_alarm_command`, `test_bsec_serial_format`, `test_bus_recovery`, `test_host_command`, `test_sharp_dust_limits`) built with `g++ -std=c++11 -Wall -Wextra -pedantic`, no warnings, all passed (25 November). |
| Firmware `49029f2` | Compiled, no warnings, 397546 bytes flash, 30448 bytes globals. Uploaded with all four hashes verified (25 November). |
| Sensor check, firmware `49029f2` | Readings PASS (58, 3.0 s), dust PASS (60 records, 892.7 to 1135.0 mV), gas FAIL (55 of 58 stuck) (25 November). |
| Sensor check, old firmware (believed `1c74995`) | Readings NOT SEEN (40 × `bsec_measurement_unavailable`, sensor_code -2), dust FAIL (41 × `dust_input_at_zero`) (25 November). |
| Bench check, firmware `1c74995` | Pass: alarm replies, LED, link-lost blink, dust fault through the monitor, dashboard pages, BME680 temperature, humidity and pressure. Dust and gas failed then (20 November). |
| Local alarm demo | With `--demo`, the simulated board confirmed level 2 during the limit alert, level 1 after "Silence alarm", and level 0 after the alert ended (15 November). |
| Online access, real tunnel | Pages loaded. Control requests without sign-in were refused (19 November). Through a real quick tunnel, save limits, silence alarm and acknowledge got HTTP 403 without sign-in and HTTP 303 after sign-in with the CSRF token. The profile file changed, and the event log recorded the profile change, the silence and the acknowledgment. The test used a scratch database and a temporary password (20 November). |
| Communication and sensor faults | Virtual serial checks of missing communication, recovery, repeated sensor errors and sensor-error recovery (8 November). |

These checks do not establish physical sensor accuracy, calibration, camera detection or room safety.

## Start here

- [Human guide](README_HUMAN.md): project purpose and behaviour.
- [Room software design](docs/superpowers/specs/2026-11-15-room-software-design.md): storage, rules, occupancy and dashboard as built.
- [Local alarm design](docs/superpowers/specs/2026-11-15-local-alarm-design.md): alarm levels, serial command, silence and reachability.
- [Dashboard data contract](docs/superpowers/specs/2026-11-15-dashboard-data-contract-design.md): the dashboard response, alert text, events, timing and retention.
- [Sensor check design](docs/superpowers/specs/2026-11-25-sensor-check-design.md): the bench check tool.
- [Sharp dust integration](docs/SHARP_DUST_INTEGRATION.md): dust wiring, calibration and checks.
- [Firmware guide](firmware/README.md): sketch structure, build commands and hardware checks.
- [25 November verification record](reference_files/LINUX_VERIFICATION_2026-11-25.md): the current board results.
- [BME680 gas heater decision](docs/superpowers/specs/2026-11-25-bme680-gas-heater-decision.md): the open hardware or software choice.
- [Manual reference](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md): course requirements and source pointers.
- [Python requirements](requirements.txt): package versions.

History only (15 to 19 November 2026, not current guidance): the [implementation plan](reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md) and the [Linux handoff](reference_files/LINUX_AI_HANDOFF.md).
Older preparation notes and component checklists describe the state before the recorded Linux sessions.
Do not repeat completed checks without a change, failure or specific open concern.

## Online access (opt-in, view-only)

Monitoring, alerts and the local alarm never depend on the internet. Online access starts only on request. Install `cloudflared` separately, then set the online password once (it is stored as a hash in the git-ignored `config/online_secret.yaml`):

```text
python dashboard.py --set-password
python dashboard.py --online
```

`--online` also serves a view-only origin on 127.0.0.1:5001 and starts a Cloudflare quick tunnel to it. The random `trycloudflare.com` link changes on each start and appears on the System page (with Copy link) on this computer. Anyone with the link can view. Saving limits, silencing and acknowledging online need the password. On this computer they need no sign-in. Without a password or without `cloudflared`, the local dashboard still runs and the System page says why online access is off or failed. Stop online access by stopping `dashboard.py`. Port, program path and sign-in lifetime are in `config/runtime.yaml`. Design: [online access](docs/superpowers/specs/2026-11-19-online-access-design.md).

## Dashboard

The dashboard has five pages: Overview, Trends, Events, Patient limits and System. It refreshes every 10 s. It shows the last monitor update, readings, occupancy, 24-hour trends, caregiver alerts with limit, value and duration, pending breaches, the latest 50 events (with paging), a patient limits form, the communication acknowledgment control and the local alarm state with a "Silence alarm" button. Trend points are one-minute averages with minimum and maximum. Gas resistance and dust voltage are charted as system details and have no limit. Air quality and the dust estimate are shown with a word and an "estimate" label, and charted while current. `GET /api/room` returns all of this in one response. The dashboard accepts requests only for `localhost` and `127.0.0.1` and rejects cross-site form posts. Patient limits are saved beside the database in a `.profile.yaml` file. Valid changes take effect at the next monitor update. If the file is invalid, the monitor keeps its last valid profile and shows a profile error. The dashboard is checked with the simulator and screenshots, and on 20 November 2026 with the board (pages and `/api/room` HTTP 200).

## Sharp dust sensor

The GP2Y1010AU0F path gives an independent dust voltage and status. The host converts the voltage to an estimated concentration in µg/m³ with Sharp's typical sensitivity and an automatic clean-air baseline. See [wiring, plan, calibration and verification](docs/SHARP_DUST_INTEGRATION.md).
The dust pins are GPIO5 (analog input) and GPIO4 (LED drive). GPIO4 drives the sensor LED directly, and LOW turns it on (measured 25 November 2026). With this polarity in the firmware, the sensor read 892.7 to 1135.0 mV on the board on 25 November 2026. The LED pulse timing is not checked on an oscilloscope.

## Local alarm

The host commands a local alarm on the ESP32 over the serial link: `ALARM,0` (off), `ALARM,1` (LED only) or `ALARM,2` (LED and buzzer). The board replies `{"type":"alarm","state":<n>}` after it applies a command, and once at start-up. The levels are in [Alerts and states](#alerts-and-states).

The sketch reads commands without blocking, at most 64 bytes per loop pass. It drives the onboard RGB LED (GPIO48 by default) and GPIO7 (buzzer module) with a steady level. The buzzer polarity is one constant, `ROOM_BUZZER_ACTIVE_HIGH`, default active high, not verified. Alarm failures never delay readings, fault checks or the status. In the demo the simulated board echoes each command.

## Bosch calibration state

Bosch's BSEC library learns the room's normal air over hours. Its IAQ accuracy goes from 0 to 3. The board keeps this learned state only in RAM, so a reset or a power cut loses it. The laptop keeps a copy in a file (user decision, 20 November 2026). See the [design](docs/superpowers/specs/2026-11-20-bsec-state-on-laptop-design.md).

- Save: the board sends its state only at IAQ accuracy 3. It sends the first time accuracy reaches 3 after start, then every 6 hours while accuracy is 3. Six hours is Bosch's standard interval, from Bosch's example sketch `basic_config_state.ino` (`STATE_SAVE_PERIOD`, 360 minutes).
- File: the monitor writes `<database name>.bsec_state.json` next to the database, for example `room.bsec_state.json` or `room-demo.bsec_state.json`. It writes a temporary file and renames it, so a crash never leaves a half-written file.
- Restore: at start the board asks for the state after `setConfig` and before it subscribes to outputs (Bosch's example order). It waits up to 10 s and still applies `ALARM` commands. The monitor replies `BSEC_STATE,<hex>` when the file exists and its BSEC version matches the board's. Otherwise it replies `BSEC_STATE,NONE` and logs the reason: no saved state, version mismatch, or file damaged. With no reply in 10 s the board starts without a state.
- I2C bus restart (25 November 2026): before a bus restart, a running sensor copies its state to RAM. The board puts it back after the restart, without the laptop. When it has no RAM copy, it asks the laptop as at start.
- If the board cannot read its state to save it, it prints the error `bsec_state_save_failed` and tries again after 60 seconds. The monitor logs it as a `bsec_state_save_failed` event, not as a sensor error. The monitor also logs this event when the laptop cannot write the state file. The event message tells the two causes apart.
- Events: `bsec_state_saved`, `bsec_state_sent`, `bsec_state_not_sent`, `bsec_state_restored`, `bsec_state_restore_failed` and `bsec_state_save_failed`. The Events page shows them under "Bosch calibration".
- The System page has a "Bosch calibration" row: "Bosch calibration saved: <time>, accuracy 3" or "Bosch calibration not saved yet", with the result of the last board request.
- In `--demo` the simulated board asks for the state at start and sends one stand-in state (not a real Bosch state) after 60 s.

Status: compiled and host-tested. The firmware with this feature has run on the board since 25 November 2026. On 25 November the board reached accuracy 3 and saved its state at 02:41:50 (`room.bsec_state.json` in the `wt-sensor-fixes` checkout, git-ignored). That state comes from a stuck gas reading, so it has no meaning for air quality. After the I2C bus restart at 02:50:00 the board restored the state from its RAM copy, with no laptop request. A restore from the laptop file after a board start is not checked. Opening the CH343 port does not reset the board (20 November 2026), so starting `monitor.py` does not cause a restore. The board asks only when it starts.

## Behavior to preserve

The monitor loads technical settings at startup.
The initial communication wait begins when the monitor starts.
Recognized readings, sensor errors and dust lines count as communication.
Incomplete readings retain the previous complete measurements and their original receipt time.
Ignored input does not reset communication timing.
Alarm replies do not count as communication. The host asks for them, so they must not hide a stopped measurement stream.
The BSEC state lines (`bsec_state`, `bsec_state_request`, `bsec_state_restored` and the `bsec_state_save_failed` error) do not count as communication either.
The board's `i2c_bus_restarted` line is an error line. The host treats it as a BME680 sensor error, so it starts the sensor-error wait. The next valid reading clears it.

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
- Their limits are system setup in `config/system.yaml`, not dashboard controls. Each has an upper limit and a hold time. The shipped file leaves both off. The project supplies no values. The word bands and levels there are display defaults, not health standards. The Bosch bands and the Sharp sensitivity are not checked against a datasheet on this machine.
- Their alerts follow the patient-limit rule (sustained, occupied, current reading), sound the buzzer and can be silenced. A calibrating index or a missing baseline pauses that check, with a stated reason.
- `monitor.py --demo` uses demonstration limits (air quality 150 for 30 s, dust 100 µg/m³ for 30 s) so the simulator shows both alerts. They are not recommendations.
- The patient profile has an optional short label, for example "Bed 3", set in the limits form. No patient name is stored.
- With the BME680 on the bench, the index reached accuracy 3 on 25 November 2026 and shows as current, but it has no meaning while the gas reading is stuck (open issue). See [BME680 gas: open decision](#bme680-gas-open-decision).

See the [design](docs/superpowers/specs/2026-11-15-air-quality-dust-label-design.md).

Patient limits apply to temperature, humidity and pressure. Each enabled measurement has a lower and upper limit. One sustained duration applies to all.
The project supplies no patient limits. The demo example limit applies only to the simulator.
A patient-limit alert starts when a breach lasts the sustained duration. One in-range reading ends it.
Patient-limit alerts require occupied status and a fresh BME680 reading at most six seconds old (`reading_gap_limit_s`).
Unknown occupancy, a stale reading, or a gap of more than six seconds between readings restarts the timer.
A changed profile restarts all timers. An invalid profile file keeps the last valid profile and shows a profile fault.
Communication, BME680, dust and profile fault alerts do not depend on occupancy.

The timing values are optional keys in `config/runtime.yaml`. An older three-key file still loads with the defaults. Demo mode uses the same defaults. The dashboard reads the effective values from the monitor status.
Laptop YAML does not control ESP32 acquisition timing.
Firmware configuration commands remain future work.

## Known limitations

- The BME680 gas reading fails at the Bosch heater temperature (25 November 2026). The Bosch index is therefore not usable with this module. See [BME680 gas: open decision](#bme680-gas-open-decision).
- Open issue (no fix chosen): the Bosch index reaches accuracy 3 and the dashboard shows it as current, but it has no meaning while the gas reading is stuck. A meaningless value is shown as current. `tools/sensor_check.py` still reports the stuck gas.
- Open issue: the BME680 drops off the I2C bus at times (25 November 2026). The firmware bus restart recovered it once and failed the second time. Inference: a Wire restart is not always enough. This fits the supply or contact inference from the heater sweep. It is not proven.
- The occupancy detector is OpenCV's default people detector, trained on upright pedestrians. It can miss seated, lying or occluded people. Unknown occupancy suppresses limit alerts. It has not been checked with a camera on this branch.
- In serial mode without `--camera`, occupancy is always unknown, so limit alerts never start.
- Readings older than 7 days are deleted hourly. Events are never deleted. The event list shows the latest 50 events and pages to older ones.
- The independent notification path is a local LED and buzzer on the ESP32, commanded by the host over USB. The LED lit as commanded on 20 November 2026. No buzzer is connected now. GPIO7 and the buzzer polarity are not checked on hardware.
- When the USB link is down the host cannot command the LED or buzzer. The dashboard then shows the alarm as unreachable. After 30 s without a valid command the board blinks the LED and keeps the buzzer in its last state. The blink was seen on the bench on 20 November 2026. The buzzer part is not checked.
- With the direct dust LED wiring, GPIO4 is not yet an output during reset and boot, before `beginDust()` runs. The GPIO4 voltage and current are not measured.
- The dust estimate uses a typical sensitivity and an automatic baseline. It is not PM2.5, an official index or a calibrated concentration. It is not checked against a reference instrument.
- The air-quality index is Bosch's estimate. It is not a gas concentration and is not checked against a reference.
- The monitor does not lock the serial port. Two programs on one port each get only part of the lines. `tools/sensor_check.py` refuses to run when another program holds the port.

## Decisions (15 November 2026)

- Board: ESP32-S3 with an N8R2 module. Correction, 17 November 2026: esptool shows the connected board is an N16R8-type module (16 MB flash, 8 MB embedded PSRAM), not an N8R2. Pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7. Correction, 20 November 2026: the dust pins were swapped to match the wiring: dust analog input GPIO5, dust LED drive GPIO4. Correction, 20 November 2026: the alarm LED is now the onboard RGB LED (GPIO48 by default), not GPIO6. Correction, 25 November 2026: the dust LED drive GPIO4 is wired directly to sensor pin 3, so LOW turns the LED on (measured). The firmware had assumed an NPN driver (HIGH on). `ROOM_DUST_LED_ACTIVE_LOW` in `firmware/bsec_board_config.h` now sets the polarity. It is `true` for the wiring in use.
- Completion work builds on this branch. The dust sensor stays.
- Primary dashboard viewer: a caregiver at a desk screen.
- Notification: a local ESP32 buzzer and LED. The buzzer sounds for limit alerts only (patient limits and the air-quality and dust system limits). System faults light the LED and show on the dashboard without sound.
- A dashboard "Silence alarm" button stops the buzzer for that alert. The LED stays on until the condition clears. The silence is logged. A new alert sounds again.
- Buzzer part: a 3-pin buzzer module driven from one GPIO (GPIO7 on the ESP32-S3). Correction, 20 November 2026: no external alarm LED and no buzzer are connected. The alarm LED is the onboard RGB LED. GPIO7 drives nothing for now.
- Raw readings are kept for 7 days. Event history is kept regardless. Implemented on 15 November.
- The dashboard is redesigned as five pages (Overview, Trends, Events, Patient limits, System).
- Air quality is shown as Bosch's index and dust as an estimated concentration, both with words. Their limits are system setup. The profile has a short label. Implemented on 15 November. This replaces the earlier raw-signals-only rule.

Later decisions are in the dated designs under `docs/superpowers/specs/`: dust disconnect and alarm link (20 November), BSEC state on the laptop (20 November), occupancy detector and override (20 and 23 November), sensor check (25 November) and the BME680 gas heater (25 November, open).

## Remaining work

1. BME680 gas: choose option B (hardware) or C (software). See [BME680 gas: open decision](#bme680-gas-open-decision). After a hardware change, run `tools/sensor_check.py` again.
2. Bosch index shown as current while the gas is stuck: decide what the dashboard shows (open issue, no fix chosen). After a gas fix, confirm a restore from the laptop file after a power cycle. The save and the RAM restore happened on 25 November.
3. BME680 drop-outs on the I2C bus: the restart recovered the sensor once and failed the second time. Possible next diagnostics (not done): check whether SDA is held low, and try a bus clear (9 SCL pulses) before `Wire.begin`. Or a person checks the BME680 power and contacts (option B).
4. Identify the ESP32-S3 board model. Run the rest of the hardware checklist in the [firmware guide](firmware/README.md#hardware-checklist).
5. Dust hardware follow-ups: check the LED pulse width (0.32 ms), the sample point (0.28 ms) and the 10 ms period on an oscilloscope. Measure the GPIO4 voltage and current with a meter, also in the boot window before `beginDust()`. Check a real dust disconnect: with the divider wired and no sensor, the input reads below 100 mV.
6. Check camera capture and the occupancy detector with seated, lying and occluded people. The occupancy plan on `feature/occupancy` continues with its Task 1b.
7. Agree on real patient limits for any demonstration.
8. Check the local alarm buzzer when one is connected: GPIO7 free, buzzer polarity, and whether it needs a tone.
9. Check the five-page dashboard with the real board and sensors over a longer run.
10. Check the Bosch word bands and the Sharp sensitivity against the datasheets.
11. Done 20 November 2026: online access with a signed-in control request through a real tunnel. Save limits, silence alarm and acknowledge were refused without sign-in (HTTP 403) and accepted after sign-in (HTTP 303).
12. Demonstrate the complete system with actual hardware.
13. Small follow-ups in code comments (dated text, no behaviour change): `firmware/bsec_board_config.h` line 10 still says "Not yet checked against the physical board". `GAS_NEXT_STEP` in `tools/sensor_check.py` says "faulty or non-genuine gas sensor"; the heater sweep points to a heater-drive threshold instead.

Steps that need a person (a meter, an oscilloscope, new parts, a person in front of the camera) are reported here. They are not scheduled.

Follow the course requirements and approved project decisions.
Preserve the existing environment and required dependencies.
Do not recreate the removed setup installer.
Ask before adding unspecified dependencies, algorithms, services or hardware procedures.
Use the [VIGIL comparison](reference_files/VIGIL_COMPARISON.md) for verified reference behaviour.
The original course PDFs and VIGIL archive are not included in this repository.
