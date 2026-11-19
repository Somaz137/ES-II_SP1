# Dust "Not Connected" and Alarm Link Blink Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Report a missing dust sensor as a fault instead of a reading, and make the board blink its LED when the laptop stops sending alarm commands.

**Architecture:** The host carries a dust voltage floor in the dust state. A record below the floor counts as a dust error, which reuses the existing fault and timeout path, and after the timeout the status becomes `not_connected`. On the board, a pure function in `alarm_command.h` decides the LED from the commanded level, the time since the last valid command and `millis()`. The buzzer follows the commanded level only.

**Tech Stack:** Python 3 and pytest (host), C++11 header tested with g++ (firmware), and arduino-cli for the compile check.

**Spec:** `docs/superpowers/specs/2026-11-20-dust-disconnect-and-alarm-link-design.md`

## Global Constraints

- Dust floor: `dust.disconnected_below_mv`, default 100, sensor-side mV, in `config/system.yaml` and `settings.SYSTEM_DEFAULTS`. The existing test keeps both equal.
- Dust timeout: the existing `sensor_error_timeout_s` (120 s). No new timeout.
- Page text for the fault: "Dust sensor not connected (reading below 100 mV)". The value comes from the setting.
- Link timeout: `ROOM_ALARM_LINK_TIMEOUT_MS` 30000 in `firmware/bsec_board_config.h`. Blink: 1 s on, 1 s off. The buzzer keeps its last commanded state (user decision).
- Only a valid `ALARM,<0|1|2>` command resets the link timer. The board prints no new line for "link lost".
- Python: `env/bin/python -m pytest -q -p no:cacheprovider`. The firmware tests are built with `g++ -std=c++11 -Wall -Wextra -pedantic`, with no warnings.
- Compile the sketch with the `arduino-cli compile` command in `firmware/README.md`. Do not upload to the board. Flashing waits for the user at the bench.
- Each commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A record exactly at the floor (100.0 mV)** is a reading, not a fault. Tested in Task 1.
2. **Readings that alternate around the floor** (99, 101, 99, …): one record at or above the floor resets the timer, so no fault is raised. The baseline restarts on each low record. Tested in Task 1.
3. **`millis()` wraps after about 49.7 days.** A command just before the wrap must not cause a false "link lost" just after it. Tested in Task 2 with unsigned arithmetic.
4. **Malformed lines and overflowed lines** do not reset the link timer. Tested in Task 2.
5. **A floor set to 0 or above 5500** in `config/system.yaml` is refused at load. Tested in Task 1.

---

### Task 1: Dust floor on the host

**Files:**
- Modify: `dust.py` (`DustState`, `record_dust`, `dust_status`)
- Modify: `monitoring_state.py` (`create_monitoring_state` gains `dust_floor_mv: float = 100.0`)
- Modify: `monitor.py` (pass `system["dust"]["disconnected_below_mv"]`)
- Modify: `settings.py` (`SYSTEM_DEFAULTS`, validation), `config/system.yaml`
- Modify: `static/room.js` (dust status text for `not_connected`)
- Test: `tests/test_dust.py`, `tests/test_system_limits.py`

**Interfaces:**
- Produces:
  - `DustState.floor_mv: float = 100.0`.
  - In `record_dust`, a value `< floor_mv` sets `diagnostic = DUST_BELOW_FLOOR` (a new module constant, the text "Dust reading below the not-connected floor."), and keeps `received_at` and `last_voltage_mv` unchanged.
  - In `dust_status`, when the record is stale and `diagnostic == DUST_BELOW_FLOOR`, the status is `"not_connected"` and `alert_active` is True. Before the timeout, the status is `"sensor_error"`, as for other dust errors.
  - The status dict gains `floor_mv`.

- [ ] **Step 1: Write the failing tests.**
  - `test_record_below_floor_is_not_a_reading`: floor 100, record 99.0. `received_at` and `last_voltage_mv` are unchanged, and `diagnostic == DUST_BELOW_FLOOR`.
  - `test_record_at_floor_is_a_reading`: a record of 100.0 updates `received_at`.
  - `test_not_connected_after_timeout`: started at 0, only 50 mV records at 3 s steps. At t=119 the status is `"sensor_error"`. At t=120 it is `"not_connected"` and `alert_active` is True.
  - `test_recovery_clears_not_connected`: then one 920 mV record gives `"fresh"`, and the alert is inactive.
  - `test_alternating_around_floor_never_faults`: 99/101 alternating for 300 s. The status is never `not_connected`.
  - `test_floor_setting_validated`: `disconnected_below_mv` set to 0, -1, 5501 or `true` is refused with `ValueError`. The default equals 100 in both the YAML and `SYSTEM_DEFAULTS`.
  - Session level: with only below-floor records, `update_dust` gives no `dust_ugm3` sample, and the baseline value stays None.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.** In `room.js`, the `not_connected` text reads "Dust sensor not connected (reading below {floor_mv} mV)", in the fault tone that dust faults already use. The System page dust row uses the same text.
- [ ] **Step 4: Run the full suite.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `Report a dust reading below the floor as a missing sensor, not a reading`.

### Task 2: LED blink when the laptop link is lost

**Files:**
- Modify: `firmware/alarm_command.h` (pure functions)
- Modify: `firmware/bsec_board_config.h` (`ROOM_ALARM_LINK_TIMEOUT_MS`, `ROOM_ALARM_BLINK_HALF_PERIOD_MS` 1000)
- Modify: `firmware/room_environment_safety_control_bme680.ino` (track the level and the last command time, and write the LED from the pure function each loop pass)
- Test: `firmware/tests/test_alarm_command.cpp`

**Interfaces:**
- Produces, in `alarm_command.h`:
  - `inline bool alarmLinkLost(uint32_t nowMs, uint32_t lastCommandMs, uint32_t timeoutMs)`, which is `nowMs - lastCommandMs >= timeoutMs` in unsigned arithmetic.
  - `inline AlarmOutputs alarmOutputsAt(int level, bool linkLost, uint32_t nowMs, uint32_t halfPeriodMs)`. When `linkLost` is true, `led = (nowMs / halfPeriodMs) % 2 == 0`. When it is false, `led` comes from `alarmOutputs(level)`. `buzzer = alarmOutputs(level).buzzer` always.

- [ ] **Step 1: Write the failing tests** in `test_alarm_command.cpp`:
  - not lost at 29999 ms after the last command; lost at 30000.
  - wrap: last command at `0xFFFFF000`, now at `0x00000FFF`. The elapsed time is 8191 ms, which is not lost.
  - lost, level 0: LED on at 0–999 ms, off at 1000–1999 ms. The buzzer is off.
  - lost, level 2: the LED blinks and the buzzer stays on.
  - not lost, level 1: the LED is steady on, and the buzzer is off.
  - A malformed line fed to `AlarmLineReader` returns `ROOM_ALARM_INVALID`, so the sketch's apply callback is not called (existing behaviour, asserted again).
- [ ] **Step 2: Build and run.** It must fail to compile, because the functions are not defined.
- [ ] **Step 3: Implement.** In the sketch:
  - `applyAlarmLevel` stores `roomAlarmLevel` and `roomLastCommandMs = millis()`.
  - `setup()` sets `roomLastCommandMs = millis()` at start.
  - `loop()` calls a new `refreshAlarmOutputs()`, which writes the pins from `alarmOutputsAt(...)` only when the outputs change.
  - The reply to each command is unchanged.
- [ ] **Step 4: Build and run the C++ tests** (no warnings, PASS). Then run the `arduino-cli compile` command from `firmware/README.md` (no warnings).
- [ ] **Step 5: Docs.** In `firmware/README.md` (Local alarm section and the hardware checklist, adding a bench item "stop monitor.py, LED blinks after about 30 s, next command stops it") and the README local-alarm section, write that the fallback is implemented, compiled and not checked on hardware. In the README remaining-work list, change the dust item 9 to name the floor rule and its pending bench check.
- [ ] **Step 6: Commit** with the message `Blink the alarm LED when no host command arrives for 30 s; keep the buzzer state`.
