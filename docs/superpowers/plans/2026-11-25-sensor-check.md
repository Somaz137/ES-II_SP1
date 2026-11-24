# Sensor Check Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A read-only bench tool, `tools/sensor_check.py`, that listens to the ESP32-S3 serial output and prints PASS / FAIL / NOT SEEN lines for BME680 readings, gas resistance change and the dust input.

**Architecture:** A pure analysis core over a list of `(monotonic_time, line)` pairs reuses `serial_parser.parse_serial_line` and `dust.parse_dust`. A thin CLI opens the port with pyserial, collects lines for a fixed time, optionally runs a breath window, and prints the report. The dust floor comes from `config/system.yaml` through `settings.load_system_settings`.

**Tech Stack:** Python 3 (`env/bin/python`), pyserial (already installed), pytest.

**Spec:** `docs/superpowers/specs/2026-11-25-sensor-check-design.md`

## Global Constraints

- Worktree `/home/bridge/ES-II_SP1/wt-room-air`, branch `feature/sensor-check`, BASE `e206849`.
- Python: `/home/bridge/ES-II_SP1/ES-II_SP1/env/bin/python`. Tests: `/home/bridge/ES-II_SP1/ES-II_SP1/env/bin/python -m pytest -q -p no:cacheprovider` run from the worktree. Baseline: 752 passed.
- No new packages. No change to any file outside `tools/sensor_check.py`, `tests/test_sensor_check.py`, `firmware/README.md`, `README.md`.
- The tool never writes to the serial port (no `ALARM`, no BSEC state).
- No pass/fail threshold for the breath step: information only.
- The stuck value is `12917166.00`. FAIL text says the value "matches" the 20 November stuck value; it never says "is".
- Plain, short STE-style English in all printed text and docs.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push.

## Review Focus

1. The monitor is running and holds the port → one clear line, exit 2, no traceback. (Task 2: `test_busy_port_prints_one_line_and_exits_2`.)
2. The cable is pulled during the run → the summary of what was gathered still prints, with "The port closed after N s." (Task 2: `test_port_closed_mid_run_still_prints_summary`.)
3. Wrong port or a board that sends nothing → every check is NOT SEEN, exit 1, no crash on empty data (also in the breath step). (Task 1: `test_no_lines_gives_not_seen_everywhere`, `test_breath_change_with_no_readings_is_none`.)
4. The BME680 is missing or failing → its `sensor_error` messages are shown, not just "0 readings". (Task 1: `test_sensor_errors_are_listed_with_counts`.)
5. Ctrl+C during the run → the summary of what was gathered prints with "Stopped early after N s." (Task 2: `test_ctrl_c_prints_summary`.)

---

### Task 1: Analysis core

**Files:**
- Create: `tools/sensor_check.py` (analysis part only; CLI in Task 2)
- Test: `tests/test_sensor_check.py`

**Interfaces:**
- Consumes: `serial_parser.parse_serial_line(line) -> ParsedSerialMessage` (`kind` in `valid_reading`, `sensor_error`, `incomplete_reading`, `bsec_state`, `bsec_state_request`, `bsec_state_restored`, `bsec_state_save_failed`, …; `measurements["gas_ohms"]`; `gas.iaq_accuracy`, `gas.iaq`; `message`; `restore_ok`). `dust.parse_dust(line) -> None | (float|None, str|None)`; note `dust_input_at_zero` returns `(0.0, None)`, so count it from the raw JSON `message`.
- Produces:
  - `STUCK_GAS_OHMS = 12917166.0`
  - `@dataclass(frozen=True) class Check: name: str; verdict: str  # "PASS" | "FAIL" | "NOT SEEN" | "INFO"; detail: str; next_step: str | None = None`
  - `analyse(lines: list[tuple[float, str]], floor_mv: float) -> list[Check]` — always returns five checks in this order and with these names: `"Readings arrive"`, `"Gas resistance changes"`, `"Dust input"`, `"Bosch accuracy"`, `"BSEC state messages"`.
  - `breath_change(before: list[tuple[float, str]], during: list[tuple[float, str]]) -> float | None` — lowest `gas_ohms` in `during` as a percentage of the median `gas_ohms` in `before`; `None` if either has no valid reading.
  - `exit_code(checks: list[Check]) -> int` — 0 if every check with verdict other than `INFO` is `PASS`, else 1.
  - `format_report(checks: list[Check]) -> str` — one line per check, `f"{verdict:<8} {name}: {detail}"`, and an indented `"  Next step: …"` line under any check with a `next_step`.

The module starts with `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`, as `tools/occupancy_bench.py` does on the occupancy branch. Tests load it with `importlib.util.spec_from_file_location("sensor_check", <repo>/tools/sensor_check.py)`.

Rules (from the spec, section 7.1):

| Check | Verdict |
|---|---|
| Readings arrive | PASS if ≥1 `valid_reading`; else NOT SEEN. Detail: count, mean interval in s (1 decimal; "—" with fewer than 2), count of `incomplete_reading`, and each distinct `sensor_error` message with its count. |
| Gas resistance changes | FAIL if any reading equals `STUCK_GAS_OHMS` (a raw gas ADC of 0 is not a real measurement); the detail then starts "N of M readings match the stuck value of 20 November". Else NOT SEEN with < 2 valid readings. PASS if > 1 distinct `gas_ohms`. FAIL if all equal. Detail: distinct count, min, max (2 decimals). FAIL next_step: "Check the BME680 part. A constant value suggests a faulty or non-genuine gas sensor." When any reading equals `STUCK_GAS_OHMS`, the detail adds: "This matches the stuck value of 20 November (by the BME68x formula, a raw gas ADC of 0)." |
| Dust input | NOT SEEN with no dust lines. PASS if ≥1 `sensor_mv` ≥ `floor_mv`. Else FAIL. Detail: dust records, `dust_input_at_zero` count, each other dust error with its count (for example `dust_acquisition_unavailable (40)`), records below floor, min and max mV of the `dust` records. FAIL next_step: "Check with a meter: Vcc 5 V on sensor pins 6 and 1, ground on pins 2 and 4, Vo on pin 5, and the divider midpoint to GPIO5." When there are only other dust errors (no records, no zero reports), the next step is "The board could not sample the dust input. Reset the board and run again." |
| Bosch accuracy | INFO. Highest `iaq_accuracy` seen and the last `iaq` ("none" when absent). |
| BSEC state messages | INFO. For each of request, state saved, restored (with ok true/false), save failed: "seen" or "not seen". When a request is seen, next_step: "The board asked for its saved calibration. This tool does not send it. Run the monitor to restore it." |

- [ ] **Step 1: Write the failing tests** in `tests/test_sensor_check.py`. Build lines with small helpers, e.g. `reading(gas, acc=0, iaq=None)` returning the JSON text of `{"type":"reading","temp_c":21.0,"humidity_pct":40.0,"pressure_hpa":1000.0,"gas_ohms":gas,"bsec":{"stabilization_status":0,"run_in_status":0,"iaq_accuracy":acc,"iaq":iaq}}`, and `dust(mv)` / `dust_zero()` lines in the firmware's format (`firmware/sharp_dust.h`). Tests:
  - `test_varying_gas_passes`: three readings 50000.0, 50210.5, 49980.0 → gas verdict `PASS`, detail contains `"3 distinct"`.
  - `test_constant_stuck_gas_fails_and_names_20_november`: three readings of 12917166.0 → `FAIL`, detail contains `"matches the stuck value of 20 November"`, next_step starts `"Check the BME680 part"`.
  - `test_other_constant_gas_fails_without_stuck_text`: three of 40000.0 → `FAIL`, `"20 November"` not in detail.
  - `test_one_reading_gas_is_not_seen`.
  - `test_dust_at_zero_fails_with_meter_step`: three `dust_input_at_zero` lines → dust `FAIL`, detail contains `"3 dust_input_at_zero"`, next_step contains `"pins 6 and 1"`.
  - `test_dust_above_floor_passes`: `dust(910.0)` with floor 100 → `PASS`.
  - `test_dust_only_below_floor_fails`: `dust(40.0)` with floor 100 → `FAIL`.
  - `test_no_lines_gives_not_seen_everywhere`: `analyse([], 100)` → first three verdicts all `NOT SEEN`; `exit_code` is 1.
  - `test_sensor_errors_are_listed_with_counts`: two `{"type":"error","message":"bsec_initialization_failed"}` lines → readings `NOT SEEN`, detail contains `"bsec_initialization_failed (2)"`.
  - `test_bsec_request_gives_restore_hint`: a `bsec_state_request` line with a valid version (see `bsec_state_store.is_bsec_version`) → BSEC check next_step contains `"This tool does not send it"`.
  - `test_accuracy_reports_highest_and_last_index`: readings with acc 0, 2, 1 and iaq None, 41.0, 44.5 → detail contains `"highest 2"` and `"44.5"`.
  - `test_breath_change_percent`: before gas 100000, 100000, 102000; during 60000, 80000 → `breath_change` returns `60.0`.
  - `test_breath_change_with_no_readings_is_none`: `breath_change([], [])` is `None`.
  - `test_exit_code_ignores_info`: all three PASS plus INFO lines → 0.
  - `test_report_format`: `format_report([Check("Gas resistance changes","FAIL","1 distinct","Check it.")])` equals `"FAIL     Gas resistance changes: 1 distinct\n  Next step: Check it."`.

- [ ] **Step 2: Run them and see them fail**
Run: `/home/bridge/ES-II_SP1/ES-II_SP1/env/bin/python -m pytest -q -p no:cacheprovider tests/test_sensor_check.py`
Expected: errors, because `tools/sensor_check.py` does not exist.

- [ ] **Step 3: Implement** `STUCK_GAS_OHMS`, `Check`, `analyse`, `breath_change`, `exit_code`, `format_report` in `tools/sensor_check.py` with the rules above. Use `statistics.median`. Lines that fail to decode or parse are skipped.

- [ ] **Step 4: Run the new tests, then the whole suite**
Expected: new tests pass; whole suite 752 + new, all passed.

- [ ] **Step 5: Commit** — `git add tools/sensor_check.py tests/test_sensor_check.py && git commit -m "Add the sensor check analysis: readings, gas change and dust input verdicts"` (with the Co-Authored-By line).

---

### Task 2: Serial listener, CLI and docs

**Files:**
- Modify: `tools/sensor_check.py` (add the CLI)
- Modify: `tests/test_sensor_check.py`
- Modify: `firmware/README.md` (a "Sensor check" subsection in the hardware checklist)
- Modify: `README.md` ("Remaining work" item 12: one line naming the tool)

**Interfaces:**
- Consumes: Task 1's `analyse`, `breath_change`, `exit_code`, `format_report`. `settings.load_system_settings(path) -> dict` (`["dust"]["disconnected_below_mv"]`).
- Produces:
  - `listen(port, seconds: float, clock, log=None) -> tuple[list[tuple[float, str]], str | None]` — reads lines until `clock()` passes start + `seconds`; returns the lines and a stop note (`None`, `"Stopped early after N s."` on `KeyboardInterrupt`, `"The port closed after N s."` on `serial.SerialException` or `OSError` during read). Each line: `readline()`; a read without a trailing newline (cut at the 1 s timeout) is kept and joined with the next read; then decode UTF-8 with `errors="replace"`, strip, skip empty. With `log`, write `f"{datetime.now().isoformat(timespec='seconds')} {line}\n"` for each line.
  - `port_holders(port: str, proc: str = "/proc") -> list[int]` — pids (not its own) whose `/proc/[pid]/fd/*` link equals `os.path.realpath(port)`; skips unreadable or gone entries.
  - `main(argv: list[str] | None = None, opener=serial.Serial, clock=time.monotonic, proc="/proc") -> int`

CLI: `--port` (required), `--baud` (default 115200), `--seconds` (default 120, must be finite and > 0), `--breath` (flag), `--log FILE`, `--config` (default `<repo>/config/system.yaml`). The port opens as `opener(port, baud, timeout=1, exclusive=True)`.

`main` flow:
1. Load the dust floor from `--config`. On any error: print `f"Cannot read {path}: {error}"`, return 2.
2. If `port_holders(port)` is not empty: print `f"{port} is open in another program (pid {pid}). Stop the monitor first: two programs on one port each get only part of the lines."`, return 2. Open the port. On `serial.SerialException` or `OSError`: print `f"Cannot open {port}: {error}. Stop the monitor first: two programs on one port each get only part of the lines. Check that the cable is in the CH343 port."`, return 2. If `--log` cannot be opened: print `f"Cannot write {path}: {error}"`, return 2 (the port is closed).
3. Print `f"Listening on {port} for {seconds} s. This tool only reads; it sends nothing to the board."` Then `listen`.
4. If `--breath` and no stop note: print `"Breathe on the BME680 for 5 seconds now."` and `listen` 30 s more. Append the breath lines to the total. Print `f"INFO     Breath test: lowest gas resistance {p:.0f}% of the value before."`, or `"INFO     Breath test: no gas readings to compare."` when `breath_change` is `None`.
5. Print the stop note if any, then `f"Lines received: {n}."` (with 0 lines add "No lines came. Check that the cable is in the CH343 port and that the board runs."), then `format_report(analyse(all_lines, floor))`. Return `exit_code(...)`. Close the port in all cases.

- [ ] **Step 1: Write the failing tests.** Use a fake port class with `readline()` returning queued bytes (and `b""` when empty), a `close()` that records the call, and no `write` method at all (so any write raises `AttributeError`). Use a fake clock that advances 1 s per call. Pass `--config` pointing at `config/system.yaml` in the repo. Tests:
  - `test_main_reports_and_returns_0_when_all_pass`: queue varying readings and one `dust(910.0)` line; `main([...,"--seconds","10"], opener=..., clock=...)` returns 0; captured stdout contains `"PASS     Gas resistance changes"`.
  - `test_main_returns_1_on_stuck_gas`.
  - `test_busy_port_prints_one_line_and_exits_2`: opener raises `serial.SerialException("[Errno 16] Device or resource busy")` → returns 2; stdout contains `"Stop the monitor first"`; no `"Traceback"`.
  - `test_port_closed_mid_run_still_prints_summary`: `readline` raises `serial.SerialException` after two lines → stdout contains `"The port closed after"` and `"Readings arrive"`; port closed.
  - `test_ctrl_c_prints_summary`: `readline` raises `KeyboardInterrupt` after two lines → stdout contains `"Stopped early after"` and the report.
  - `test_breath_step_prints_percentage`: with `--breath`, the prompt and `"Breath test: lowest gas resistance"` appear.
  - `test_log_writes_each_line`: with `--log tmp_path/"run.log"`, the file has one line per received line, each ending with the JSON text.
  - `test_bad_config_exits_2`: `--config` to a missing file → 2, stdout starts `"Cannot read"`.

- [ ] **Step 2: Run them and see them fail** (`main` not defined).

- [ ] **Step 3: Implement** `listen` and `main` as above; add `if __name__ == "__main__": sys.exit(main())`. Module docstring with the usage line: `env/bin/python tools/sensor_check.py --port /dev/ttyACM0 [--seconds 120] [--breath] [--log FILE]`.

- [ ] **Step 4: Run the new tests, then the whole suite.** Expected: all passed. Also run `env/bin/python tools/sensor_check.py --help` and check it exits 0.

- [ ] **Step 5: Docs.** In `firmware/README.md`, under the hardware checklist, add "Sensor check" with the usage line, what each line means, the exit codes (0 all pass, 1 a check failed or was not seen, 2 port or config error), and the run order from the spec section 7.1 (1. stop the monitor, run with the current firmware; 2. meter checks, fix wiring, run again; 3. flash, run again, then start the monitor for the BSEC restore check in README item 11). In `README.md` "Remaining work" item 12, add one line: "Run `tools/sensor_check.py` before and after the meter checks (see the firmware guide)."

- [ ] **Step 6: Commit** — `git add tools/sensor_check.py tests/test_sensor_check.py firmware/README.md README.md && git commit -m "Add the sensor check command line: listen, breath test, log and docs"` (with the Co-Authored-By line).

---

### After the final review: hardware run (main session oversees; user allowed flashing on 25 November)

Not a code task. Steps, in order, each reported to the user:
1. Confirm no monitor holds `/dev/ttyACM0`. Run the tool with the firmware now on the board (`1c74995`) and `--log` into the scratchpad. Record the result.
2. Compile the sketch from this branch with the `arduino-cli compile` command in `firmware/README.md` (scratch folder named `room_environment_safety_control_bme680`), then upload it to `/dev/ttyACM0` (CH343 port). Record the commit flashed.
3. Run the tool again. Record the result.
4. If gas and dust pass, start the monitor for the BSEC restore check (README item 11) in the background; the user takes no part in the tests (25 November). No `--breath` run: it needs a person.
