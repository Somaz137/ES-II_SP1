# Dust LED polarity and I2C bus restart — fix plan (25 November 2026)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the dust sensor measure with the wiring on the bench, and let the firmware recover the BME680 when the I2C bus stops answering.

**Architecture:** Pure decision helpers in headers (host-tested with g++), thin use in the sketch. No host Python change.

**Tech Stack:** Arduino ESP32-S3 core, Bosch bsec2 1.10.2610, g++ host tests.

**Evidence (diagnostic of 25 November 2026, report `wt-bsec-state/.superpowers/sdd/2026-11-25-sensor-check/diagnostic-report.md`):**
- Dust: LED pulse HIGH on GPIO4 → 0.8–1.8 mV at GPIO5 (30 windows). Pulse LOW → 446–528 mV, mean 470 mV. GPIO4 drives sensor pin 3 directly (LED on when LOW); no NPN. Supply, Vo and divider work.
- BME680 at 0x76, chip id 0x61, variant 0. The I2C bus failed after the first `bme68x_init` (rc -2, no chip-id reply for about 27 s). `Wire.end()` + `Wire.begin()` restored it at once; then 70/70 reads were good. The sketch has no recovery: a failed `begin()` in setup() reports the error forever; a later bus failure gives `bsec_measurement_unavailable` forever.

## Design decisions

- D1. `bsec_board_config.h` gets `constexpr bool ROOM_DUST_LED_ACTIVE_LOW = true;` with a comment: measured 25 November 2026, GPIO4 drives sensor pin 3 directly; set false for the NPN low-side driver of docs/SHARP_DUST_INTEGRATION.md.
- D2. GPIO4 stays a push-pull output. Not open-drain: released, the pin would float toward 5 V through the LED, above the ESP32-S3 pin limit. Off = HIGH (3.3 V) on the direct wiring.
- D3. `sharp_dust_limits.h` gets `constexpr bool dustLedLevel(bool on, bool activeLow)` returning the logic level (true = HIGH): `on != activeLow`. `sharp_dust.h` uses it for the idle level in `beginDust()`, the pulse start and the pulse end. Pulse timing (280 µs sample, 320 µs pulse, 10 ms period) is unchanged.
- D4. New header `firmware/bus_recovery.h` with a pure helper:
  `inline bool roomBusRestartDue(uint32_t now, uint32_t lastGoodMs, uint32_t lastRestartMs, bool restartedOnce)`
  — true when `now - lastGoodMs >= ROOM_BUS_RESTART_AFTER_MS` and (`!restartedOnce` or `now - lastRestartMs >= ROOM_BUS_RESTART_INTERVAL_MS`). Unsigned wrap-safe subtraction. Constants in `bsec_board_config.h`: `ROOM_BUS_RESTART_AFTER_MS = 10000` (more than three LP intervals of 3 s), `ROOM_BUS_RESTART_INTERVAL_MS = 30000`.
- D5. The sketch: move the sensor start (Wire.begin, begin at LOW then HIGH address, setConfig, state restore, updateSubscription, attachCallback) from setup() into `bool startRoomSensor()`. setup() calls it once. In loop(), when not configured, or when `roomBusRestartDue(...)` is true, call `restartRoomBus()`: before the restart, if configured, copy the BSEC state to a RAM buffer with `roomSensor.getState` (ignore failure); then `Wire.end()`, `Wire.begin(SDA, SCL)`, `startRoomSensor()`. Inside the start, use the RAM state with `setState` when one was copied; otherwise ask the host (`restoreBsecState()`, the boot path). Print `{"type":"error","message":"i2c_bus_restarted"}` once per restart. Keep the existing error lines.
  - On the first boot, `restartedOnce` is false and lastGoodMs is the setup time, so a bus that fails at boot is restarted after 10 s, then at most every 30 s.
- D6. Docs: `docs/SHARP_DUST_INTEGRATION.md` (wiring table: the direct wiring in use, measured 25 November; the NPN driver as the alternative with the constant set false), `firmware/README.md` (pin line for GPIO4 and the restart behaviour, the new host test), `README.md` (the pin line in "Decisions" and item 12 status: dust LED polarity found and fixed in firmware, not yet checked on the board until the flash).

## Global Constraints

- Worktree `/home/bridge/ES-II_SP1/wt-sensor-fixes`, branch `fix/dust-led-i2c-restart`, BASE `f1a9dee` (or the plan commit).
- Firmware host tests: `g++ -std=c++11 -Wall -Wextra -pedantic -Ifirmware firmware/tests/<t>.cpp -o <scratch>/<t> && <scratch>/<t>`, no warnings. All existing firmware tests still pass.
- Python suite unchanged and passing: `/home/bridge/ES-II_SP1/ES-II_SP1/env/bin/python -m pytest -q -p no:cacheprovider` (798).
- Sketch compile: copy `firmware/room_environment_safety_control_bme680.ino` and `firmware/*.h` to a scratch folder named `room_environment_safety_control_bme680`, compile with `/home/bridge/.local/bin/arduino-cli compile --config-file /home/bridge/.local/share/room-arduino/arduino-cli.yaml --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default" --warnings all --build-path <own scratch build dir>`. No warnings from the sketch. **No upload** (the controller flashes after review). Never open /dev/ttyACM0.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not push.

---

### Task 1: Dust LED polarity (D1–D3, dust part of D6)

**Files:** Modify `firmware/bsec_board_config.h`, `firmware/sharp_dust_limits.h`, `firmware/sharp_dust.h`, `firmware/tests/test_sharp_dust_limits.cpp`, `docs/SHARP_DUST_INTEGRATION.md`, `firmware/README.md`, `README.md`.

- [ ] Step 1: Failing tests in `test_sharp_dust_limits.cpp`: `dustLedLevel(true, true) == false` (on, active low → LOW); `dustLedLevel(false, true) == true`; `dustLedLevel(true, false) == true`; `dustLedLevel(false, false) == false`. Build: fails (no function).
- [ ] Step 2: Add `dustLedLevel`; use it in `sharp_dust.h` (`digitalWrite(ROOM_DUST_LED_PIN, dustLedLevel(on, ROOM_DUST_LED_ACTIVE_LOW) ? HIGH : LOW)` for idle, pulse on, pulse off). Update the header comment of `sharp_dust.h` (it now says "HIGH turns on an external NPN sink"). Add D1 constant.
- [ ] Step 3: All four firmware host tests pass, no warnings. Sketch compiles, no warnings; record flash and globals size.
- [ ] Step 4: Docs per D6 (dust part). Commit.

### Task 2: I2C bus restart (D4, D5, restart part of D6)

**Files:** Create `firmware/bus_recovery.h`, `firmware/tests/test_bus_recovery.cpp`. Modify `firmware/bsec_board_config.h`, `firmware/room_environment_safety_control_bme680.ino`, `firmware/README.md`.

- [ ] Step 1: Failing tests in `test_bus_recovery.cpp`: not due at 9999 ms since last good; due at 10000 when never restarted; not due 20000 ms after a restart when still failing; due 30000 ms after a restart; wrap-around (lastGoodMs near UINT32_MAX, now small) behaves by elapsed time.
- [ ] Step 2: Implement `bus_recovery.h` and constants. Refactor the sketch per D5. The RAM state buffer is `static uint8_t[BSEC_MAX_STATE_BLOB_SIZE]` with a `bool` "held" flag.
- [ ] Step 3: All five firmware host tests pass, no warnings. Python suite passes. Sketch compiles, no warnings; record sizes.
- [ ] Step 4: Docs per D6. Commit.

### After review: flash and verify (controller)

Flash this branch, run `tools/sensor_check.py --port /dev/ttyACM0 --seconds 180`, expect dust PASS (sensor-side mV near 900). Watch for `i2c_bus_restarted` lines and whether readings resume after one. Restart the monitor and dashboard from this worktree after the check.
