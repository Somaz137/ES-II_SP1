# BSEC State on the Laptop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save Bosch's BSEC calibration state to a file on the laptop, and restore it to the board when the board starts.

**Architecture:** The board sends the state as a JSON line when accuracy is 3, and then every 6 hours. The host writes it atomically next to the database. At start-up, the board asks for the state, waits up to 10 s while it still handles `ALARM` commands, applies the state with `setState` before `updateSubscription`, and reports the result. A widened host-command reader on the board handles both `ALARM` and `BSEC_STATE` lines.

**Tech Stack:** C++11 headers tested with g++, the Arduino sketch (BSEC2 1.10.2610), and Python 3 with pytest.

**Spec:** `docs/superpowers/specs/2026-11-20-bsec-state-on-laptop-design.md`

## Global Constraints

- Save interval: `ROOM_BSEC_STATE_SAVE_MS` = 6 hours (21600000 ms). The code comment and the docs say: "Bosch's standard interval, from Bosch's example basic_config_state.ino (STATE_SAVE_PERIOD, 360 minutes). User decision, 20 November 2026."
- The board saves only when IAQ accuracy is 3: once when accuracy first reaches 3 after start, and then every 6 hours while it stays 3.
- State size: at most `BSEC_MAX_STATE_BLOB_SIZE` (238) bytes, sent as lowercase hex. The longest host line, `BSEC_STATE,` plus 476 hex characters, is 487 characters. The reader buffer is 512. The per-pass byte bound stays 64.
- Wire format, board to host:
  - `{"type":"bsec_state","accuracy":3,"bsec_version":"a.b.c.d","state":"<hex>"}`
  - `{"type":"bsec_state_request","bsec_version":"a.b.c.d"}`
  - `{"type":"bsec_state_restored","ok":true|false}`
- Wire format, host to board: `BSEC_STATE,<hex>` or `BSEC_STATE,NONE`.
- The start-up wait is 10 s. During the wait the board still applies `ALARM` commands.
- File: `<database stem>.bsec_state.json` next to the database, holding `{saved_at, bsec_version, accuracy, state}`. Write a temporary file and rename it.
- The new board lines do not count as communication, the same as alarm replies.
- Do not upload to the board. The bench step is the user's.
- Each commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A damaged state file** (bad JSON, odd-length hex, longer than 476 characters, or not hex): the host sends `BSEC_STATE,NONE` and logs "file damaged". It never crashes. Tested in Task 3.
2. **A version mismatch** between the file and the board's request: the host sends NONE and logs the reason. Tested in Task 3.
3. **A request that arrives while the host is still starting up, or twice in a row** (the board reset twice): each request gets exactly one reply. Tested in Task 3.
4. **An `ALARM,2` sent during the 10 s start-up wait** is applied and answered. Tested in Task 1 (the reader) and by the sketch structure in Task 2.
5. **Accuracy drops from 3 to 2 before the 6-hour mark:** no save happens until accuracy is 3 again. Tested in Task 1 (the pure save-decision function).

---

### Task 1: Host-command reader and save decision (pure firmware headers)

**Files:**
- Create: `firmware/host_command.h`
- Modify: `firmware/alarm_command.h` (`AlarmLineReader` delegates its line buffer to the new reader, or is replaced by it. Keep `pumpAlarmInput`'s byte bound.)
- Create: `firmware/tests/test_host_command.cpp`
- Modify: `firmware/tests/test_alarm_command.cpp` (only if the reader type changes)

**Interfaces:**
- Produces:
  - `ROOM_HOST_LINE_MAX = 511`
  - `struct HostCommand { int kind; int level; uint8_t state[238]; std::size_t stateLength; }`, where `kind` is one of `ROOM_HOST_NONE`, `ROOM_HOST_ALARM`, `ROOM_HOST_BSEC_STATE`, `ROOM_HOST_BSEC_NONE` or `ROOM_HOST_INVALID`
  - `HostCommand parseHostCommand(const char* line, std::size_t length)`
  - `struct HostLineReader { HostCommand feed(char c); }`
  - `inline bool bsecShouldSave(uint8_t accuracy, bool savedOnce, uint32_t nowMs, uint32_t lastSaveMs, uint32_t periodMs)`
  - `inline bool formatStateHex(const uint8_t* state, std::size_t length, char* out, std::size_t capacity)`

- [ ] **Step 1: Write the failing tests:**
  - `ALARM,0`, `ALARM,1` and `ALARM,2` parse to `ROOM_HOST_ALARM` with that level. `ALARM,9` gives `ROOM_HOST_INVALID`.
  - `BSEC_STATE,NONE` gives `ROOM_HOST_BSEC_NONE`.
  - `BSEC_STATE,` with 476 hex characters gives `ROOM_HOST_BSEC_STATE` and `stateLength` 238, and the bytes round-trip with `formatStateHex`. Uppercase hex is also accepted.
  - Odd length, a non-hex character, 478 characters, and an empty payload each give `ROOM_HOST_INVALID`.
  - A 600-character line gives `ROOM_HOST_INVALID` (overflow), and the next line parses normally.
  - `bsecShouldSave`:
    - accuracy 2 gives false
    - accuracy 3 and not yet saved gives true
    - saved, and 6 h − 1 ms later, gives false
    - saved, and 6 h later, gives true
    - saved, and 6 h later but at accuracy 2, gives false
    - the `millis()` wrap is handled
- [ ] **Step 2: Build.** It must fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Build and run** both C++ test files with `-std=c++11 -Wall -Wextra -pedantic`. Expected: no warnings and PASS.
- [ ] **Step 5: Commit** with the message `Add the host-command reader for ALARM and BSEC_STATE lines and the state-save rule`.

### Task 2: Sketch: request, restore and save

**Files:**
- Modify: `firmware/room_environment_safety_control_bme680.ino`
- Modify: `firmware/bsec_board_config.h` (`ROOM_BSEC_STATE_SAVE_MS`, `ROOM_BSEC_STATE_WAIT_MS` 10000)

**Interfaces:**
- Consumes: Task 1's reader and functions.

- [ ] **Step 1: Implement in `setup()`.**
  - After `setConfig` succeeds and before `updateSubscription`, print `bsec_state_request` with the version from `roomSensor.version` (`major.minor.major_bugfix.minor_bugfix`).
  - Then loop for up to `ROOM_BSEC_STATE_WAIT_MS`, pumping host input. `ALARM` lines go to `applyAlarmLevel`. On the first `BSEC_STATE` or `BSEC_STATE,NONE` line, stop waiting. For a state, call `roomSensor.setState(state)` and print `bsec_state_restored` with `ok` set to its result. For NONE, print nothing more.
  - Follow the order in Bosch's `basic_config_state.ino` (`setState` after `setConfig`, before `updateSubscription`).
- [ ] **Step 2: Implement the save.** In `receiveRoomSample`, store the IAQ output's `accuracy` in a global. In `loop()`, outside the callback, when `bsecShouldSave(...)` is true, call `roomSensor.getState(buffer)`, format the hex, and print the `bsec_state` line. The buffer is a static array of 238 bytes, and the hex buffer has 477 characters.
- [ ] **Step 3: Compile** with the `arduino-cli compile` command from `firmware/README.md`. Expected: no warnings. Record the flash and RAM use that the compiler reports.
- [ ] **Step 4: Commit** with the message `Ask the host for the BSEC state at start, restore it before subscribing, save it every 6 hours at accuracy 3`.

### Task 3: Host: parse, store, reply and show

**Files:**
- Modify: `serial_parser.py` (the kinds `bsec_state`, `bsec_state_request`, `bsec_state_restored`)
- Modify: `monitoring_state.py` (carry the latest of each, like `alarm_reply`, without touching the communication timing)
- Create: `bsec_state_store.py`
- Modify: `monitor.py` (reply to requests through `transport.send`, save state lines, log events, publish the `bsec_state` status block)
- Modify: `simulated_input.py` (demo: one request at start, one state line after 60 s, so the path is visible in demo)
- Modify: `dashboard.py` and `static/room.js` (System page row "Bosch calibration")
- Test: `tests/test_bsec_state.py`, plus the existing `tests/test_serial_parser.py` and `tests/test_dashboard.py`

**Interfaces:**
- Produces:
  - `state_path(db_path: Path) -> Path` (`room.sqlite3` gives `room.bsec_state.json`)
  - `save_state(path, *, state_hex: str, bsec_version: str, accuracy: int, saved_at: float) -> None` (atomic: a temporary file, then `os.replace`)
  - `load_state(path) -> dict | None`
  - `reply_for(path, bsec_version: str) -> tuple[str, str]`, which returns `(line, reason)`. The line is `BSEC_STATE,<hex>` with the reason `"restored from <saved_at ISO>"`, or `BSEC_STATE,NONE` with one of the reasons `"no saved state"`, `"version mismatch (file a.b.c.d, board e.f.g.h)"` or `"file damaged"`.
  - Event kinds: `bsec_state_saved`, `bsec_state_sent`, `bsec_state_not_sent`, `bsec_state_restored`, `bsec_state_restore_failed`.
  - Status block: `bsec_state: {saved_at, accuracy, last_request_at, last_reply_reason, last_restore_ok}`.

- [ ] **Step 1: Write the failing tests:**
  - The parser classifies each of the three lines. A `bsec_state` with a non-hex or over-long `state` is `ignored`.
  - These lines do not reset the communication timer: after a timeout, a `bsec_state_request` line alone does not clear it.
  - `save_state`, then `load_state`, round-trips the data. A crash simulated between the write and the replace leaves the old file whole: monkeypatch `os.replace` to raise, and the old content is still there.
  - `reply_for`:
    - no file gives NONE with "no saved state"
    - a version mismatch gives NONE with the reason naming both versions
    - a damaged file (bad JSON, odd hex, 478 characters) gives NONE with "file damaged"
    - a good file gives `BSEC_STATE,<hex>`
  - Monitor level, with a fake transport:
    - a request gets exactly one `send`
    - two requests get two sends
    - a state line writes the file and logs `bsec_state_saved`
  - Dashboard: `/api/room` `health` (or the System data) includes `bsec_state`. The System page shows "Bosch calibration saved: <time>, accuracy 3", or "not saved yet".
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full suite** (PASS). Then run `monitor.py --demo` with `dashboard.py --demo` for 70 s, and confirm the System row and the events.
- [ ] **Step 5: Commit** with the message `Store the BSEC state next to the database and send it back when the board asks`.

### Task 4: Documentation

- [ ] **Step 1:** Update these documents:
  - `README.md`: replace "Saving the BSEC calibration state across power loss is not implemented" and the remaining-work item 7 wording.
  - `README_HUMAN.md`.
  - `firmware/README.md`: the serial behaviour, the new lines, and a bench item: "run to accuracy 3, wait for a save, power-cycle, confirm restore".
  - `reference_files/PYTHON_FILE_GUIDE.md`.

  State the 6-hour interval and that it is Bosch's standard from their example. Say that it is compiled and not checked on hardware.
- [ ] **Step 2:** Run the full suite and record the count.
- [ ] **Step 3: Commit** with the message `docs: BSEC state saved on the laptop`.
