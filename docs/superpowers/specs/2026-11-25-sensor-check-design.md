# Sensor check tool — design (25 November 2026)

Branch `feature/sensor-check`, from `feature/bsec-state` (`a664b7d`), which has the current pins (dust Vo GPIO5, dust LED GPIO4, onboard RGB alarm LED) and the BSEC state save.

## 1. Intent

The user wants the system to give meaningful output, starting with air quality. Today it cannot:

- On the 20 November bench check, `gas_ohms` was 12917166.00 in every reading for about 15 minutes. A constant gas resistance makes the Bosch index meaningless.
- Every dust record was `dust_input_at_zero` (GPIO5 at 0 V), so there is no dust estimate.

So the hardware comes first. The dashboard already shows the Bosch index with a word band and the dust estimate with a word level; they become meaningful once the sensors give real data.

**Sensor check tool.** A bench tool that reads the board's serial output and says, in plain pass/fail lines, whether the BME680 gas reading and the dust input are working. The user runs it before and after their wiring checks and after the firmware flash. The hardware fixes themselves (meter checks, wiring, flashing) are the user's steps.

## 2. Goals

- G1. `tools/sensor_check.py` gives a pass/fail verdict for: readings arrive, gas resistance changes, dust input above the disconnect floor. It also reports the Bosch accuracy reached and any BSEC state messages seen.

## 3. Non-goals

- No dashboard change. The user dropped the overall room air status on 25 November: the existing Air quality and Dust tiles already give word levels.
- No run-time stuck-gas detection in the monitor (offered, not chosen).
- No Python code outside `tools/`, the tool's tests and the docs.
- No new BSEC outputs (CO2 estimate, breath-VOC estimate), no change of the BSEC sample rate or calibration window. These are candidates after real data exists.
- No limit values. `upper_limit` and `hold_s` stay `null` in the shipped file.
- No firmware change. No flashing (the user's step).

## 4. Anti-goals (a failure even if it works)

- A sensor check that hides a fault behind a pass, for example passing gas because values were received while they never changed.
- A tool that writes to the board (no `ALARM` commands, no BSEC state sent).

## 5. Constraints

- Product rules in the README Product section and `PRODUCT.md`: say it in words, never colour alone; never show a retained or estimated value as fresh; state facts, no medical judgement; patient limits are never invented.
- No new Python packages. pyserial is already used (`tools/read_sensor.py`, `serial_transport.py`).
- No build step, no CDN: plain Flask templates, CSS and JavaScript.
- Only one program can open the serial port. The monitor must be stopped while the tool runs. Opening the CH343 port (`/dev/ttyACM0`) does not reset the board.
- Status reports and docs in plain, short STE-style English.

## 6. Approaches considered

**Sensor check tool**

- A. Read the stored readings from the SQLite store while the monitor runs. No port conflict, but limited to what the monitor stores and keeps.
- **B. Read the serial port directly (chosen by the user).** More detail: raw lines, `dust_error` messages, BSEC state messages, start-up lines. The monitor must be stopped first.

**Overall room air status** (a summary line on Overview): designed, then dropped by the user on 25 November because the tiles already show word levels.

## 7. Design

### 7.1 Sensor check tool

Command: `env/bin/python tools/sensor_check.py --port /dev/ttyACM0 [--seconds 120] [--breath] [--log FILE]`

- `--port` is required. If the port cannot be opened, print one line that says the port is busy or missing and that the monitor must be stopped, then exit 2.
- `--seconds` (default 120) is the listen time. The BME680 reports every 3 s, so 120 s gives about 40 readings. The dust timeout is 120 s, so the default covers one full dust window.
- Parsing reuses `serial_parser.parse_serial_line` for readings and BSEC messages, and `dust.parse_dust` for dust lines. The disconnect floor is read from `config/system.yaml` (`dust.disconnected_below_mv`) through the existing settings loader, not copied.
- `--log FILE` writes every raw line with a timestamp, so the run can be analysed later.
- `--breath`: after the main listen time, print "Breathe on the BME680 for 5 seconds now." and listen 30 s more. Report the lowest gas resistance in that window as a percentage of the median before it. This is information only, with no pass/fail threshold, because no threshold has been chosen.

Summary lines at the end, each PASS, FAIL or NOT SEEN, with the numbers behind it:

| Check | PASS when | Numbers printed |
|---|---|---|
| Readings arrive | at least one valid BME680 reading | count, mean interval |
| Gas resistance changes | more than one distinct `gas_ohms` value among the valid readings, and not every reading is 12917166.00 | count of distinct values, min, max |
| Dust input | at least one dust record with `sensor_mv` at or above the floor | dust records, `dust_input_at_zero` count, other dust errors, min and max mV |
| Bosch accuracy | information only | highest `iaq_accuracy` seen, last `iaq` |
| BSEC state messages | information only | `bsec_state_request`, `bsec_state_restored`, `bsec_state_save_failed` seen or not |

- The value 12917166.00 is named in the FAIL text as the 20 November stuck value: by the BME68x formula it matches a raw gas ADC of 0 at range 0. This is an inference and the text says "matches", not "is".
- When a BSEC state request is seen, print: "The board asked for its saved calibration. This tool does not send it. Run the monitor to restore it."
- On a FAIL, print the matching next step: for dust, the meter checks from README "Remaining work" item 12 (Vcc 5 V on sensor pins 6 and 1, ground on pins 2 and 4, Vo on pin 5, divider midpoint to GPIO5); for gas, "Check the BME680 part. A constant value suggests a faulty or non-genuine gas sensor."
- Exit code 0 when every PASS/FAIL check passes, 1 when any fails or is not seen.
- The analysis is a pure function over a list of (time, line) pairs, so it is tested without a port. The serial loop stays thin.
- Read only: the tool never writes to the port.

A short "Sensor check" section in `firmware/README.md` (hardware checklist) gives the run order:
1. Stop the monitor. Run the tool with the current firmware. Expect gas and dust to fail.
2. Do the meter checks and fix the wiring. Run again.
3. Flash `feature/bsec-state` firmware (user's step). Run again, then start the monitor and do the BSEC restore check from README item 11.

## 8. Left to the builder

- Test file names and fixtures.
- Exact wording of the tool's error lines, within the meanings above.

## 9. Calls made for the user to check

- Branch from `feature/bsec-state`, not `feature/occupancy` (new pins and BSEC there).
- The `--breath` step reports a percentage but has no pass/fail threshold.
- The tool's FAIL for gas also catches any single constant value, not only 12917166.00.
- Default listen time 120 s.
