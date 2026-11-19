# Bosch BSEC calibration state saved on the laptop

Date: 20 November 2026. Status: short design, for approval.

## Why

Bosch's BSEC library learns the room's normal air over hours. Its accuracy goes from 0 to 3. Until accuracy is high enough, the dashboard shows "calibrating" instead of the air-quality index. The learned state is kept only in the board's RAM. A power cut or reset loses it, and calibration starts again.

User decision (20 November 2026): keep the saved state in a file on the laptop, not in the board's flash. The laptop is the edge device. The ESP32 is only the sensor bridge.

## Approaches

| Approach | Trade-off | Result |
|---|---|---|
| Save to the board's flash (Bosch's example) | Simple, and works without the laptop. But it stores data on the bridge, and flash writes are limited. | Rejected by the user |
| Save to a file on the laptop over the serial link | Fits the edge design. The file is easy to inspect and back up. Needs a new serial message in each direction. | **Chosen** |
| Do not save | No work. The index calibrates again after each board start. | Rejected |

## Facts from the installed library (BSEC2 1.10.2610)

- `Bsec2::getState(uint8_t*)` and `Bsec2::setState(uint8_t*)` exist. The state is at most `BSEC_MAX_STATE_BLOB_SIZE` = 238 bytes.
- Bosch's interface notes say the state is retrieved before shutdown and applied during re-initialization. Bosch's example applies it after `setConfig` and before `updateSubscription`.
- Bosch's example `basic_config_state.ino` saves every 360 minutes (`STATE_SAVE_PERIOD`).

## Design

**Save interval: 6 hours.** This is Bosch's standard interval from their own example sketch (`STATE_SAVE_PERIOD` = 360 minutes). User decision, 20 November 2026. With the file on the laptop, a shorter interval would cost nothing. The project uses Bosch's standard value.

1. **Save rule.** The board sends the state only when the IAQ accuracy is 3. It sends at the first time accuracy reaches 3 after start, and then every 6 hours while accuracy is 3. *My call:* this stops an uncalibrated state from overwriting a good file after a failed restore.
2. **Board to laptop.** One JSON line: `{"type":"bsec_state","accuracy":3,"bsec_version":"<x.y.z.w>","state":"<hex>"}`. The hex text is at most 476 characters.
3. **Laptop file.** The monitor writes `<database name>.bsec_state.json`, next to the database: `{saved_at, bsec_version, accuracy, state}`. It writes a temporary file and renames it, so a crash never leaves a half-written file. An event records each save. These lines do not count as communication, the same rule as alarm replies.
4. **Restore at board start.** After `setConfig`, the board prints `{"type":"bsec_state_request","bsec_version":"<x.y.z.w>"}`. It then waits up to 10 seconds for one line, `BSEC_STATE,<hex>` or `BSEC_STATE,NONE`. During the wait it still applies `ALARM` commands. It calls `setState` with the state and reports `{"type":"bsec_state_restored","ok":true|false}`. Then it subscribes to outputs as now.
5. **Laptop reply.** When the monitor reads a request, it sends the saved state if the file exists and the BSEC version matches. Otherwise it sends `BSEC_STATE,NONE` and logs the reason (no file, version mismatch, or file damaged). The restore and its result are logged as events.
6. **If the laptop is not listening at board start,** the board continues without a state after 10 s. Note: with the CH343 bridge, opening the serial port may reset the board (firmware checklist item 5, not yet checked). If it does, starting `monitor.py` triggers a fresh start and a restore.
7. **Firmware command reader.** It now keeps at most 31 characters. Raise the limit to fit `BSEC_STATE,` plus 476 hex characters. Keep the per-pass byte bound.
8. **Dashboard.** The System page shows "Bosch calibration saved: <time>, accuracy 3", or "not saved yet", and the result of the last restore.

## Tests

- Host: parsing the new lines, the atomic file write, the version check, the NONE reply, damaged-file handling, and that state lines do not count as communication.
- Firmware (g++): the larger line reader, the `BSEC_STATE` parsing (hex, length, NONE), and that an `ALARM` command still works during the wait.
- Bench (with the BME680): run until accuracy 3, wait for a save, power-cycle the board, and confirm the index skips "calibrating" or leaves it sooner.

## Left to the builder

- Whether `setState` must come before `updateSubscription` in the Bsec2 wrapper. Follow Bosch's example order.
- The exact accuracy source. Use the IAQ output's `accuracy` field.
