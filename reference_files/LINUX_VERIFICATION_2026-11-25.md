# Linux verification results - 25 November 2026

On 25 November 2026 an assistant ran bench checks on the ESP32-S3 with the BME680, the Sharp dust sensor and the onboard RGB LED wired. The user took no part in the tests. Steps that need a person are listed at the end. They were not done.
Board: ESP32-S3 (QFN56) revision v0.2, MAC b8:1f:3f:db:45:78, CH343 port `/dev/ttyACM0`.
Python: `/home/bridge/ES-II_SP1/ES-II_SP1/env/bin/python`. Times are local (PKT).
`fuser /dev/ttyACM0` showed no holder before each tool run and each upload.

## Software checks

| Check | Result |
|---|---|
| Python suite, `feature/sensor-check` at `f1a9dee` (the sensor check tool) | 798 passed. The branch was then fast-forwarded into `feature/bsec-state` at `f1a9dee`. 798 passed on the merged tree. |
| Python suite, `fix/dust-led-i2c-restart` at `49029f2` | 798 passed. |
| Firmware host tests at `49029f2` | `test_alarm_command`, `test_bsec_serial_format`, `test_bus_recovery`, `test_host_command`, `test_sharp_dust_limits`: each built with `g++ -std=c++11 -Wall -Wextra -pedantic -Ifirmware`, no warnings, exit 0. |

## Runs in time order

Each `sensor_check` command was:

```bash
env/bin/python tools/sensor_check.py --port /dev/ttyACM0 --seconds <N> --log <scratch>/<file>.log
```

| Time | Firmware on the board | Step | Result |
|---|---|---|---|
| 01:13:02 to 01:15:02 | Old, believed `1c74995` | `sensor_check`, 120 s | Exit 1. 81 lines. Readings NOT SEEN: 0 valid readings, 40 × `{"type":"error","message":"bsec_measurement_unavailable","bsec_code":0,"sensor_code":-2}`. Dust FAIL: 41 × `dust_input_at_zero`. |
| 01:15:44 | — | Flash `f1a9dee` | Compile exit 0, no warnings, 397210 bytes flash (12%), 30200 bytes globals (9%). Upload exit 0, 4 regions, "Hash of data verified." 4 times. |
| 01:15:53 to 01:18:50 | `f1a9dee` | `sensor_check`, 180 s | Exit 1. 118 lines. Readings PASS: 58 valid, mean interval 3.0 s, no sensor errors. Gas FAIL: 55 of 58 at 12917166.00 ohm, 4 distinct values (114682.80, 48249.22, 43419.32 ohm in seconds 12 to 18). Dust FAIL: 60 × `dust_input_at_zero`. Bosch accuracy highest 1, last index 50.25. No BSEC state lines seen. |
| — | `f1a9dee` | Monitor for the BSEC restore check | Not started, because gas failed. |
| 01:51:34 | Diagnostic sketch, version 1 | Dust part and first BME680 init | Partial run, stopped after about 1 min. Compiled 347774 bytes, no warnings. Upload exit 0, all hashes verified. |
| 01:53:39 to 01:59:35 | Diagnostic sketch, version 2 | Dust polarity and BME680 diagnostic, 359 s | See [Diagnostic](#diagnostic-dust-led-and-bme680). Compiled 348362 bytes. Upload exit 0, hashes verified. |
| After the diagnostic | `f1a9dee` (restored) | Flash, then `sensor_check`, 60 s | Flash: 397210 bytes, upload exit 0, all 4 hashes verified. Check exit 1: readings PASS (19, 3.0 s, no errors); gas FAIL (16 of 19 stuck, minimum 32844 ohm); dust FAIL (11.6 to 18.2 mV, below the 100 mV floor). |
| 02:08:57 to 02:17:51 | Heater sweep sketch | BME680 heater sweep, 540 s | See [Heater sweep](#heater-sweep). Compiled 312765 bytes, no warnings. Upload at 02:08:42 exit 0, 4 of 4 hashes verified. |
| 02:18:18 | `f1a9dee` (restored) | Flash, then `sensor_check`, 60 s | Flash: 397210 bytes, upload exit 0, 4 of 4 hashes verified. Check: readings PASS (19, 3.0 s, no errors); gas FAIL (16 of 19 stuck); dust FAIL (52 to 62 mV, below the floor). |
| About 02:24 | — | Flash `49029f2` | Compile exit 0, no warnings, 397546 bytes flash (12%), 30448 bytes globals (9%). Upload exit 0, "Hash of data verified." 4 times, hard reset through RTS. |
| 02:24:59 to 02:27:56 | `49029f2` | `sensor_check`, 180 s | Exit 1, from gas only. 118 lines: 58 readings, 60 dust. Readings PASS: 58, mean 3.0 s, no sensor errors. Gas FAIL: 55 of 58 stuck, minimum 30399.80 ohm (real values 133538.53, 38634.82, 30399.80 ohm, 12 to 18 s after the reset). Dust PASS: 60 records, 0 `dust_input_at_zero`, 0 below the floor, 892.7 to 1135.0 mV, mean 1018.9 mV. Bosch accuracy highest 1, last index 50.1. 0 `i2c_bus_restarted`, 0 `bsec_measurement_unavailable`. |
| From 02:28:21 | `49029f2` | `monitor.py --port /dev/ttyACM0` (PID 125021) and `dashboard.py` (PID 125022), from `wt-sensor-fixes`, local only | Process start 02:28:21. First monitor record 02:28:22. `/api/room` read at 02:31:34: serial connected, BME680 fresh, dust fresh (1055.5 mV, establishing baseline), air quality calibrating (accuracy 1), alarm confirmed at level 0. The monitor output from 02:28:22 to 02:40:12 (654 records) had no sensor error and no `i2c_bus_restarted` line. At 02:40 the dust estimate was current: baseline 921.5 mV, estimate 4.24 µg/m³, word "low". The rest of this run is in [Monitor run, 02:28 to 02:59](#monitor-run-0228-to-0259). |

Dust records from `49029f2`: the first record had 1000 samples and 2 rejected (probably a start-up window; inference). After that, 295 to 298 samples (297 in 54 records) and 2 to 5 rejected (3 in 54 records).

Start-up lines and `bsec_state_request` were not in the logs. The board reset at the end of each upload, before the tool opened the port. Opening the CH343 port does not reset the board (20 November 2026). To capture these lines, the tool must listen before a reset.

Inference about run 1: `sensor_code -2` is the BME68x communication-failure code (`BME68X_E_COM_FAIL`). After the flash (a full reset) the BME680 answered at once. So a sensor or bus state that a reset cleared is more likely than wiring. This was not proven.

## Monitor run, 02:28 to 02:59

Firmware `49029f2`. The monitor (PID 125021) and the dashboard (PID 125022) ran from `wt-sensor-fixes` with the default database `room.sqlite3`. The facts below come from the events and readings in that database (opened read-only) and from the scratch monitor log. Status as of 02:59. The run continued after that.

| Time | What happened |
|---|---|
| 02:40:50 | Bosch accuracy 2. The first stored index value (200). |
| 02:41:50 | Bosch accuracy 3. Event `bsec_state_saved`: "Bosch calibration saved (accuracy 3, BSEC 2.6.1.0)". The file is `room.bsec_state.json` in `wt-sensor-fixes` (git-ignored). |
| 02:49:20 | Last BME680 reading before the first drop-out. Then `bsec_measurement_failed` and `bsec_measurement_unavailable`. |
| 02:49:30 | `i2c_bus_restarted`, then `bsec_initialization_failed`. |
| 02:50:00 | Second `i2c_bus_restarted`. The start succeeded. Event `bsec_state_restored` (from the RAM copy; no laptop request was made). |
| 02:50:03 | Readings again. Gap 43 s. |
| 02:56:48 | Last BME680 reading before the second drop-out. |
| From 02:56:48 | Each bus restart (about every 30 s, 4 seen by 02:59) was followed by `bsec_initialization_failed`. |
| 02:58:50 | Event "BME680 alert active." Alarm confirmed at level 1 (LED on, buzzer off). |

Numbers from the database, 02:28:23 to 02:56:48:

- Temperature: 556 stored readings. The only gap over 10 s is 02:49:20 to 02:50:03.
- Gas: 552 of 556 stored readings were 12917166 ohm (stuck). The scratch monitor log shows the same pattern (about 1527 of 1544 records).
- Bosch index: 307 stored values from 02:40:50. 272 round to 50. Short peaks after the first index (200 at 02:40:50, down to about 61 by 02:41:11) and after the bus restart (385 at 02:50:21, down to about 62 by 02:50:48).
- Temperature, humidity and pressure were good while the sensor answered.
- Dust stayed good for the whole run. The estimate was current from about 02:40 (baseline about 921.5 mV, about 4 µg/m³).

Results:

- The bus restart worked on the board once (02:49:20 to 02:50:03).
- The bus restart did not recover the sensor the second time (from 02:56:48, as of 02:59).
- The Bosch index reached accuracy 3, and the dashboard shows it as current. It has no meaning while the gas reading is stuck. This is an open issue. No fix is chosen. `tools/sensor_check.py` still reports the stuck gas.
- Inference: the module drops off the bus, and a Wire restart is not always enough. This fits the supply or contact inference from the heater sweep. It is not proven.
- Possible next diagnostics (not done): check whether SDA is held low, and try a bus clear (9 SCL pulses) before `Wire.begin`. Or a person checks the BME680 power and contacts (option B in the decision record).

## Diagnostic: dust LED and BME680

The diagnostic sketch measured the dust input in two LED modes and tested the BME680 directly. Run 2 retried after errors and ran `Wire.end()` + `Wire.begin(8, 9)` every 30 s while init failed. Wire clock 100 kHz.

Dust (millivolts at GPIO5, before the divider is undone; 15 windows of 1.9 s per mode per part, 190 pulses per window):

| Part | Mode | Pulse mean (window means) | Idle mean |
|---|---|---|---|
| 1 | A: idle LOW, pulse HIGH | 1.4 mV (1.2 to 1.8) | 0.2 mV |
| 1 | B: idle HIGH, pulse LOW | 467.6 mV (447.5 to 527.7) | 8.0 mV |
| 2 | A | 0.9 mV (0.8 to 1.2) | 0.1 mV |
| 2 | B | 473.3 mV (446.1 to 528.5) | 7.7 mV |

Result: GPIO4 drives sensor pin 3 directly. LOW turns the LED on. About 470 mV at GPIO5 is about 940 mV at the sensor. The firmware had assumed an NPN driver (HIGH on), so the LED was off at every sample. Supply, Vo and divider work. Fixed in `b850690` (`ROOM_DUST_LED_ACTIVE_LOW = true`, push-pull output).

BME680:

- I2C scan: only 0x76 answered. Chip id 0x61, variant id 0x00 (low-gas variant). 0x77 gave no answer.
- `bme68x_init` returned 0. Then the first `set_heatr_conf` failed (rc -2). For about 27 s (60.9 s to 84.9 s board time) every call and every fresh chip-id read failed: 9 `diag_i2c_error` records.
- After `Wire.end()` + `Wire.begin()` at 87.9 s: the scan found 0x76, the chip id read 0x61, init returned 0, and the next 70 measurements had rc 0. No more errors in the remaining run.
- Run 1 had the same pattern after the first init.
- Inference: one ESP32 Wire restart clears the fault. The run cannot separate "the ESP32 driver is stuck" from "the sensor stopped answering and recovered", because both ended at the same moment. Fixed in `49029f2`: the firmware restarts the bus after 10 s without a valid reading, at most every 30 s, and keeps the BSEC state in RAM.
- Gas, 35 readings each: 320 °C / 150 ms gave 34 of 35 at 12917166 ohm. 200 °C / 100 ms gave 35 of 35 real values (6405 to 55405 ohm). Temperature 23.4 to 23.6 °C, humidity 58 to 59 %, pressure 993.5 to 993.6 hPa.

## Heater sweep

Forced mode with the BME68x library, no BSEC, one measurement every 3 s through a 9-step cycle, 20 cycles, 178 measurements in the log. The raw gas ADC and range were read from registers 0x2A/0x2B.

| Setting | n | Real | Gas ADC 0 | Real values (kΩ) |
|---|---|---|---|---|
| 200 °C / 150 ms | 19 | 19 | 0 | 33.3 to 34.9 |
| 240 °C / 150 ms | 19 | 19 | 0 | 21.1 to 22.3 |
| 260 °C / 150 ms | 20 | 20 | 0 | 18.4 to 21.3 |
| 280 °C / 150 ms | 20 | 1 | 19 (range 6, 201.8 kΩ) | 64.5 |
| 300 °C / 150 ms | 20 | 3 | 17 (range 5, 403.4 kΩ) | 750.6 to 778.4 |
| 320 °C / 150, 100, 50 ms | 60 | 0 | 60 (range 0, 12917.2 kΩ) | — |
| 200 °C / 50 ms | 20 | 20 | 0 | 43.7 to 46.5 |

- No carry-over: after each 320 °C failure the next 200 °C reading was real.
- No I2C errors, retries or recoveries in 540 s.
- All status bytes were 0xB0. The valid and stable bits do not show the failure.
- Inference: the failure follows the heater drive, not the heater time. A supply sag and a contact or sensing-layer fault both fit. The data cannot separate them. See the [decision record](../docs/superpowers/specs/2026-11-25-bme680-gas-heater-decision.md).

## False dust event

The dashboard showed "Dust alert cleared" at 01:42:32. The SQLite events of the main folder (`room.sqlite3`, branch `feature/occupancy`) hold it: "Dust alert active" at 01:40:21, "Dust alert cleared" at 01:42:32, "Dust alert active" at 01:45:31. That monitor ran old host code without the 100 mV floor. It stored dust voltages of 7.0 to 17.8 mV in that window as readings. On `feature/bsec-state` and later, a value below 100 mV is "no reading". Run the host from a checkout that matches the firmware.

## Not verified

- A BSEC state restore from the laptop file after a board start. (The save at accuracy 3 and a restore from the RAM copy after a bus restart happened in the monitor run.)
- A bus clear before `Wire.begin`, and the SDA level while the BME680 is off the bus.
- A working gas reading under BSEC. It is blocked by the heater fault.
- The start-up lines after a reset with the tool already listening.
- The dust LED timing on an oscilloscope, and the GPIO4 voltage and current with a meter (also before `beginDust()` at boot).
- A `--breath` run of the sensor check.
- The buzzer (none connected), the camera and the occupancy detector.

## Evidence notes

The logs and reports are outside git: `wt-bsec-state/.superpowers/sdd/2026-11-25-sensor-check/` (`hardware-run-report.md`, `diagnostic-report.md`, `heater-sweep-report.md`, `hw-logs/`) and `wt-sensor-fixes/.superpowers/sdd/2026-11-25-dust-led-and-i2c-restart/` (`flash-report.md`). The diagnostic and sweep sketches and their raw logs are in a session scratch folder, which can be cleared. The numbers above are copied from those reports and logs. The monitor-output figures from 02:28 to 02:59 and the event times were read from the scratch monitor log and the `wt-sensor-fixes` SQLite file (read-only) while this record was written. The `i2c_bus_restarted` and `bsec_initialization_failed` lines appear as the `diagnostic` field of the status records in the monitor log, not in the events table.
