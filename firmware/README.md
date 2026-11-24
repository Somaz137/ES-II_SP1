# ESP32-S3 BSEC firmware

**Target:** an ESP32-S3 (QFN56, revision v0.2) with 16 MB quad flash and 8 MB embedded PSRAM, an N16R8-type module. esptool read these facts from the connected board on 17 November 2026. The documents assumed an N8R2 module until then. The board was selected on 15 November 2026. It supersedes the DOIT ESP32 DevKit V1.
**Status:** the board was flashed on 17 November 2026. The serial link and the alarm protocol were checked without sensors. See the [17 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-17.md). On 20 November 2026 the board, still on firmware `1c74995`, was checked on the bench with the BME680, the dust sensor and the onboard RGB LED. The results are in the [hardware checklist](#hardware-checklist). On 25 November 2026 the board was flashed with `f1a9dee`, then with `49029f2` (dust LED polarity fix and I2C bus restart). With `49029f2`, readings and dust pass on the board. The gas reading fails at the Bosch heater temperature. See the [25 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-25.md). The exact development board model is not identified. The buzzer is not connected. In a monitor run on 25 November the board reached Bosch accuracy 3 and saved its state, but on a stuck gas reading. The I2C bus restart recovered the BME680 once and failed the second time.
The 8 November build for the DOIT board is history. See the [8 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-08.md).

This source prepares BSEC low-power acquisition every three seconds, experimental Sharp dust acquisition, a local LED and buzzer alarm, and the BSEC state save and restore through the laptop.
It does not establish a working hardware integration.

## Board configuration

| Setting | Value |
|---|---|
| Board | ESP32-S3 with 16 MB flash and 8 MB embedded PSRAM (N16R8-type module) |
| Arduino board identifier | `esp32:esp32:esp32s3` |
| Board options | `FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default`. Flash mode stays the default (QIO). PSRAM is disabled because the firmware does not use it. |
| USB port | CH343 USB-UART bridge (USB 1a86:55d3), `/dev/ttyACM0` on Linux |
| Serial speed | 115200 baud |
| Sensor supply | 3.3 V, confirmed by the user |
| BSEC sampling | Low-power mode, one acquisition every three seconds |

`bsec_board_config.h` rejects any chip other than the ESP32-S3 with the message "Select an ESP32-S3 board (esp32:esp32:esp32s3). This firmware targets the ESP32-S3 (developed on an N16R8-type module)."
The message changed on 17 November 2026. Before, it named the N8R2. The check itself is unchanged.
It checks the selected chip type, not the physical board or its memory.

The user confirmed a 3.3 V sensor supply on 8 November 2026.
ROOM_BME680_SUPPLY_MV therefore defaults to 3300 in bsec_board_config.h.
The header rejects supply values other than 1800 and 3300.
Breakout VIN and the BME680 supply can differ.
Check this setting again if you change the sensor breakout.

## Wiring (ESP32-S3)

The user decided these pins. They are not checked against the physical board. On 20 November 2026 the user decided that no external alarm LED and no buzzer are connected; the onboard RGB LED is the alarm LED. All are named constants in bsec_board_config.h.

| Function | GPIO | Constant | Note |
|---|---|---|---|
| BME680 SDA | GPIO8 | ROOM_I2C_SDA_PIN | |
| BME680 SCL | GPIO9 | ROOM_I2C_SCL_PIN | |
| Dust analog input (Vo through 2:1 divider) | GPIO5 | ROOM_DUST_ADC_PIN | ADC1 channel 4 |
| Dust LED drive (sensor pin 3, wired directly) | GPIO4 | ROOM_DUST_LED_PIN | LOW turns the sensor LED on (measured 25 November 2026). `ROOM_DUST_LED_ACTIVE_LOW` sets the polarity: `true` for this direct wiring, `false` for the NPN driver of [the dust integration guide](../docs/SHARP_DUST_INTEGRATION.md). Push-pull output; off is HIGH (3.3 V) |
| Alarm LED (onboard RGB LED, `LED_BUILTIN`) | GPIO48 by default | ROOM_ALARM_LED_PIN | HIGH lights it white through the core's RGB LED support. Lit white and turned off as commanded on the bench (20 November 2026) |
| Buzzer module signal (3-pin module) | GPIO7 | ROOM_BUZZER_PIN | No buzzer connected now (20 November 2026). Polarity: ROOM_BUZZER_ACTIVE_HIGH |

Connect all grounds together. Use the breakout documentation to identify the BME680 power terminal.
The dust circuit is in [SHARP_DUST_INTEGRATION.md](../docs/SHARP_DUST_INTEGRATION.md).

The alarm LED is `LED_BUILTIN` from the esp32 core's ESP32-S3 variant. In core 3.3.12, `digitalWrite` on this pin sends white at `RGB_BRIGHTNESS` (64) for HIGH and off for LOW to the addressable RGB LED on GPIO48. Some ESP32-S3 DevKitC-1 v1.1 boards have the RGB LED on GPIO38, and some clone boards need the "RGB" solder pad closed. On this board the default worked: on 20 November 2026 the LED lit white for `ALARM,1` and `ALARM,2` and turned off for `ALARM,0`.

`ROOM_BUZZER_ACTIVE_HIGH` defaults to `true`: HIGH sounds the buzzer. The module's trigger level is not verified. Many 3-pin modules trigger on LOW. If the buzzer sounds right after power-on (level 0), the polarity is wrong: set the constant to `false` and rebuild.

## Choosing CDC On Boot

- `CDCOnBoot=default`: `Serial` is UART0. Use it when the USB cable goes into a port served by a USB-UART bridge chip (often labelled UART or COM). On Linux the port is usually `/dev/ttyUSB<n>` or `/dev/ttyACM<n>`, depending on the bridge chip.
- `CDCOnBoot=cdc`: `Serial` is the native USB port of the ESP32-S3 (hardware CDC). Use it when the cable goes into the port wired to GPIO19/GPIO20 (often labelled USB). On Linux the port is usually `/dev/ttyACM<n>`.
- This board's USB port goes through a CH343 bridge (USB 1a86:55d3). It carries UART0, so use `CDCOnBoot=default`. Linux names it `/dev/ttyACM0`. The flash on 17 November 2026 used this setting.
- The board also has a native USB port (USB 303a:1001). On 20 November 2026, with the cable in that port, upload worked but no serial data came, because `CDCOnBoot=default` sends `Serial` to UART0. Use the CH343 port for the monitor.
- Opening the CH343 port does not reset the board (checked on 20 November 2026).
- The source is the same for both. Only the build option differs.

## Build commands

Run from any directory. The Arduino sketch folder must be named after the main file. This repository's folder is `firmware/`, so copy `firmware/*.ino` and `firmware/*.h` into a folder named `room_environment_safety_control_bme680` first, or rename a copy of the folder.

UART0 through the CH343 bridge (`CDCOnBoot=default`). This build and upload ran on 17 November 2026:

```bash
arduino-cli compile --config-file /home/bridge/.local/share/room-arduino/arduino-cli.yaml \
  --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default" \
  --warnings all --build-path <BUILD_DIR> <SKETCH_DIR>/room_environment_safety_control_bme680

arduino-cli upload --config-file /home/bridge/.local/share/room-arduino/arduino-cli.yaml \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default" \
  --build-path <BUILD_DIR> <SKETCH_DIR>/room_environment_safety_control_bme680
```

The 15 November builds used `FlashSize=8M,PSRAM=enabled,PartitionScheme=default_8MB` for the assumed N8R2 module. Do not use them for this board.

In Arduino IDE, select **ESP32S3 Dev Module** and set Flash Size "16MB (128Mb)", PSRAM "Disabled", Partition Scheme "16M Flash (3MB APP/9.9MB FATFS)" and USB CDC On Boot "Disabled" (`default`). The flash size and partition labels come from `arduino-cli board details`. The IDE itself was not checked.

## Hardware checklist

The board was flashed on 17 November 2026 with nothing wired to it. The serial link and the alarm replies were checked. See the [17 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-17.md).
On 20 November 2026 the board was checked on the bench with the BME680, the dust sensor and the onboard RGB LED. It still ran firmware `1c74995`, from before the BSEC state save. The cable was in the CH343 USB port (`1a86:55d3`, `/dev/ttyACM0`). The results are recorded against the items below.
On 25 November 2026 the checks ran again with `tools/sensor_check.py`, a dust and BME680 diagnostic and a BME680 heater sweep, then with firmware `49029f2`. The results are recorded against the items below, after the 20 November results. See the [25 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-25.md).
Items marked partly done say what is still open. All other items are still to do.

Before wiring the board:

1. Identify the exact ESP32-S3 board and get its pinout and schematic.
2. Check that GPIO4, GPIO5, GPIO7, GPIO8 and GPIO9 are broken out and free on this board. Check that GPIO7 is not used by a button or other on-board part. The onboard RGB LED part is done (20 November 2026): it lights on the default pin without closing an "RGB" solder pad.
3. Check that no wire goes to a strapping pin (GPIO0, GPIO3, GPIO45, GPIO46). Check that nothing pulls these pins at reset.
4. Done on 17 November 2026: the laptop uses the CH343 USB-UART bridge (USB 1a86:55d3), Linux port `/dev/ttyACM0`, `CDCOnBoot=default`.
5. No buzzer is connected now (20 November 2026). When one is connected, read the buzzer module's markings or documentation for its trigger level and supply voltage. Set `ROOM_BUZZER_ACTIVE_HIGH` to match. Check that the module's signal input is safe at 3.3 V.
6. Check the BME680 breakout supply (3.3 V) and its I2C address pin (0x76 or 0x77). Partly done on 25 November 2026: the I2C scan found only 0x76, chip id 0x61, variant 0. The supply voltage under heater load is not measured.
7. Measure the dust divider with a meter. Check that the ADC pin never sees more than about 3.1 V.
8. Dust disconnect: the host applies a floor rule (decided and implemented on the host on 20 November 2026). A dust voltage below `dust.disconnected_below_mv` (default 100 mV, sensor side), a 0 mV reading, or the board's `dust_input_at_zero` report all count as "no reading". After `sensor_error_timeout_s` (120 s) with no reading at or above the floor, the dust status is `not_connected` and the dust fault is on. Not yet checked on the bench: with the 2:1 divider wired and no sensor, confirm that the input reads below 100 mV (on 17 November, with nothing wired, the floating input read about 870 to 930 mV) and that a connected sensor reads above it. See after-flashing item 9 for the 20 November result.

After flashing:

1. Partly done on 17 November 2026: the first firmware line after reset was `{"type":"alarm","state":0}`. Still open: check that the LED and buzzer are off. Not done on 20 November 2026: the start-up line after a reset-button press (the window was missed). Not done on 25 November 2026: each upload reset the board before the tool opened the port, so the start-up lines were not captured.
2. Partly done on 17 November 2026: `ALARM,0`, `ALARM,1`, `ALARM,2` and `ALARM,0` each got the matching reply in about 10 ms, and `ALARM,9` got none. Pass on 20 November 2026: `ALARM,0`, `ALARM,1` and `ALARM,2` replied in about 10 ms, `ALARM,9` got no reply, and the onboard RGB LED was off or white as commanded. Still open: the buzzer, and whether it needs a tone instead of a steady level.
3. Check BME680 readings every three seconds, their units and the address in use. Partly done on 20 November 2026: temperature, humidity and pressure came every 3.000 s with plausible values. Gas: SUSPECT. `gas_ohms` was 12917166.00 in every reading for about 15 minutes. Inference, not measured: by the BME68x formula this value is a raw gas ADC of 0 at range 0 with the valid bits still set, so the gas part may be faulty or not genuine. The IAQ values are then not meaningful. Still open then: the address in use and the 10-minute gas run.
   25 November 2026: before the flash, the old firmware gave no reading in 120 s (40 × `bsec_measurement_unavailable`, `sensor_code` -2). Readings PASS with `f1a9dee` and `49029f2` (58 readings in 180 s, mean interval 3.0 s, no sensor errors). Address 0x76 (diagnostic). Gas FAIL: 55 of 58 readings at 12917166.00 ohm with both firmware versions. A heater sweep without BSEC found the cause: the gas reading is real at 200 to 260 °C. It fails in most readings at 280 and 300 °C and in all readings at 320 °C (gas ADC 0), at every heater time tried. The Bosch configuration heats to about 320 °C (inference), so the Bosch index cannot work with this module as it is. The fix is an open decision: see the [BME680 gas heater decision record](../docs/superpowers/specs/2026-11-25-bme680-gas-heater-decision.md).
4. Check the dust LED pulse width (0.32 ms), the sampling point (0.28 ms) and the 10 ms period on an oscilloscope. Check the accepted and rejected sample counts.
5. Done on 20 November 2026: opening the CH343 serial port does not reset the board.
6. With native USB: check what happens to readings when the laptop stops reading the port.
7. Link-lost fallback: stop `monitor.py`. Check that the LED blinks (1 s on, 1 s off) after about 30 s and that the buzzer keeps its last state. Start `monitor.py` again and check that its next command stops the blink. Partly done on 20 November 2026: the user saw the blink start after 30 s with no command and saw the next command stop it. Still open: the buzzer part (no buzzer connected).
8. Done on 20 November 2026 (moved here from the before-wiring list): `ALARM,1` lights the onboard RGB LED white and `ALARM,0` turns it off. No external alarm LED is connected, so there is no LED resistor to check.
9. Dust readings. FAIL on 20 November 2026: every reading was `dust_input_at_zero` (GPIO5 reads 0 V). The code reads the right pin.
   Fixed on 25 November 2026, by polarity. A diagnostic showed that GPIO4 drives sensor pin 3 directly, so LOW turns the LED on. The firmware assumed an NPN driver and turned the LED off for every sample. With `ROOM_DUST_LED_ACTIVE_LOW = true` (`49029f2`): PASS, 60 of 60 dust records, 892.7 to 1135.0 mV sensor side (mean 1018.9 mV), 0 `dust_input_at_zero`. Still open: the GPIO4 voltage and current with a meter, and the LED timing (item 4).
10. Monitor and dashboard. Pass on 20 November 2026: `monitor.py` raised the dust fault at 120 s and sent level 1, and the board confirmed it (the user saw the LED white). All five dashboard pages and `/api/room` returned HTTP 200.
11. BSEC state save and restore. Partly done on 25 November 2026 (`49029f2`, monitor run from 02:28): accuracy 2 at 02:40:50, accuracy 3 at 02:41:50, event `bsec_state_saved` ("accuracy 3, BSEC 2.6.1.0"). The gas reading stayed stuck, so the saved state and the index have no meaning (open issue). After the bus restart at 02:50:00 the board restored the state from its RAM copy (`bsec_state_restored`, no host request). Still open: a restore from the laptop file after a power cycle, with a working gas reading.
12. I2C bus restart (25 November 2026, `49029f2`). Worked once: the last BME680 reading was at 02:49:20. Then `i2c_bus_restarted` at 02:49:30 with `bsec_initialization_failed`, and a second restart at 02:50:00 that started the sensor. Readings again at 02:50:03 (gap 43 s). Failed the second time: the last reading was at 02:56:48. Each restart after that (about every 30 s, 4 by 02:59) gave `bsec_initialization_failed`, and the monitor raised the BME680 alert at 02:58:50 (level 1). Inference: the module drops off the bus and a Wire restart is not always enough. This fits the supply or contact inference from the heater sweep. It is not proven. Possible next diagnostics (not done): check whether SDA is held low, and try a bus clear (9 SCL pulses) before `Wire.begin`. Or a person checks the BME680 power and contacts.

### Sensor check

`tools/sensor_check.py` reads the board's serial lines and checks the gas and dust readings. It only reads: it sends nothing to the board.

```bash
env/bin/python tools/sensor_check.py --port /dev/ttyACM0 [--seconds 120] [--breath] [--log FILE]
```

- `--seconds` is the listen time (default 120 s, one full dust window).
- `--breath` asks you to breathe on the BME680 after the listen time, then listens 30 s more. It prints the lowest gas resistance as a percentage of the value before. This is information only: there is no pass or fail limit.
- `--log FILE` writes each line with a timestamp.

The summary lines:

Each summary line has one of four verdicts: PASS, FAIL, NOT SEEN (no data to judge) or INFO (no pass or fail). Before the summary, the tool prints `Lines received: N.` When no line came, it adds: "No lines came. Check that the cable is in the CH343 port and that the board runs."

- `Readings arrive`: PASS when at least one valid BME680 reading came. It gives the count and the mean interval. With sensor errors and no readings, the next step is to check the BME680 wiring (I2C SDA GPIO8, SCL GPIO9) and its power.
- `Gas resistance changes`: PASS when the valid readings have more than one `gas_ohms` value and none is the stuck value of 20 November (12917166.00). FAIL when the value is constant, or when any reading matches the stuck value (a raw gas ADC of 0 is not a real measurement). The text gives how many readings match. NOT SEEN with fewer than 2 valid readings.
- `Dust input`: PASS when at least one dust record is at or above the `dust.disconnected_below_mv` floor. A FAIL gives the meter checks. Other dust errors are named with their counts. When there are only such errors, the next step is to reset the board and run again.
- `Bosch accuracy` and `BSEC state messages`: information only. When the board asks for its saved calibration, the tool does not send it. Run the monitor to restore it.

Exit codes: 0 all checks pass, 1 a check failed or was not seen, 2 port, config or log file error.

Run order:

1. Stop the monitor. The monitor does not lock the port: two programs on one port each get only part of the lines. The tool refuses to run when another program holds the port. Run the tool with the current firmware.
2. Do the meter checks and fix the wiring. Run the tool again.
3. Flash the new firmware. Run the tool again. Then start the monitor for the BSEC restore check (README "Remaining work" item 2). This check needs a working gas reading.

On 25 November 2026 the tool ran on the old firmware, after the flash of `f1a9dee`, and after the flash of `49029f2`. The meter step was not done; the diagnostic sketch found the dust fault instead.

## Local alarm

The host sends `ALARM,0` (LED and buzzer off), `ALARM,1` (LED only) or `ALARM,2` (LED and buzzer). See the [local alarm design](../docs/superpowers/specs/2026-11-15-local-alarm-design.md) and the [port design](../docs/superpowers/specs/2026-11-15-esp32-s3-port-design.md).

- `setup()` sets both outputs to level 0 before `Serial.begin`, the dust task and the BME680 start-up.
- `setup()` prints `{"type":"alarm","state":0}` once after `Serial.begin`. With native USB this line can be lost if the laptop has not opened the port yet. The host repeats its command at every fault check.
- `loop()` reads at most 64 bytes per pass with `pumpAlarmInput`. It never waits for input. It runs even when the BME680 failed to start.
- Each valid command sets the outputs and prints one reply. Malformed lines get no reply.
- The buzzer gets a steady level. There is no tone and no beep pattern.
- Link-lost fallback: when no valid command arrives for 30 s (`ROOM_ALARM_LINK_TIMEOUT_MS`), the LED blinks, 1 s on and 1 s off (`ROOM_ALARM_BLINK_HALF_PERIOD_MS`). The buzzer keeps its last commanded state. The timer starts at boot, and only a valid `ALARM` command resets it; malformed lines do not. The next valid command ends the blink. The board prints no line for this. The host normally sends a command every 5 s (`fault_check_interval_s`). Implemented on 20 November 2026. On the bench the same day the user saw the blink start after 30 s and stop at the next command (after-flashing item 7).
- `refreshAlarmOutputs()` is the only function that writes the LED and buzzer pins. `setup()`, each valid command and each `loop()` pass call it. It computes the outputs with `alarmOutputsAt` and writes the pins only when they change.

## Serial behavior

The sketch uses 115200 baud and I2C SDA GPIO8/SCL GPIO9.
It tries address 0x76 and then 0x77.
BSEC controls acquisition timing through BSEC_SAMPLE_RATE_LP.
The loop calls BSEC frequently without a three-second delay.
Only a new callback produces a reading record.
Only the loop task writes `Serial`. The dust task never writes it. Lines therefore never interleave.

Every 3 s the loop prints one dust line:

- `{"type":"dust","sensor_mv":…,"samples":…,"rejected_samples":…}`: the mean sensor-side voltage of the accepted samples.
- `{"type":"dust_error","message":"dust_input_at_zero"}`: the window failed (fewer than 100 accepted samples, or more rejected than accepted) and more than half of all its samples read 0 mV with good timing. A missing sensor at about 0 V gives this line. The host counts it as below the floor. Added on 20 November 2026. Seen on the board on 20 and 25 November 2026, while the LED polarity was wrong.
- `{"type":"dust_error","message":"dust_acquisition_unavailable"}`: any other failed window, or the dust task did not start.

With `CDCOnBoot=cdc`, a write can wait up to about 100 ms per block when the laptop holds the port open but does not read. This is core behaviour (`HWCDC.cpp`). It is not checked on the board.

Each reading includes temp_c, humidity_pct, pressure_hpa, and gas_ohms.
The bsec object includes stabilization_status, run_in_status, iaq_accuracy and iaq.
`iaq` is Bosch's `BSEC_OUTPUT_IAQ` index with two decimals, added on 15 November 2026. It is null when the signal is not finite or outside 0 to 500. The host still accepts records without it.
The firmware keeps `BSEC_OUTPUT_IAQ`, not `BSEC_OUTPUT_STATIC_IAQ`. The installed library describes the static output only as "Unscaled indoor-air-quality estimate". That does not settle which suits a fixed room device.
Missing status fields appear as null.
Python treats incomplete status information as unknown.
The example in [bsec_reading.json](../tests/fixtures/bsec_reading.json) describes the format.
It is a fixture, not observed hardware output.

Expected BSEC warm-up flags do not prevent valid raw readings.
Invalid conversions and failures produce recognized error records.
Continuous failure reports errors at most once every three seconds.
Two missing sample periods trigger reporting when BSEC returns without measurements.
Python still applies its separate 120-second fault rules.
Initialization failures keep reporting their error until a bus restart succeeds.

I2C bus restart (added 25 November 2026; compiled and host-tested; on the board since 25 November 2026. It recovered the BME680 once and failed the second time, see hardware checklist item 12). A diagnostic on 25 November 2026 showed the BME680's I2C bus stop answering after the first `bme68x_init` (rc -2 for about 27 s), and `Wire.end()` + `Wire.begin()` restored it at once. The firmware now restarts the bus by elapsed time (`roomBusRestartDue` in `bus_recovery.h`):

- With no valid reading, and no successful sensor start, for 10 s (`ROOM_BUS_RESTART_AFTER_MS`, more than three LP intervals), `loop()` calls `restartRoomBus()`. While the readings stay missing, it restarts at most once every 30 s (`ROOM_BUS_RESTART_INTERVAL_MS`). A sensor that fails to start at boot is restarted 10 s after `setup()`, then at most every 30 s.
- Before the restart, a running sensor copies its BSEC state to RAM with `getState`. The board prints `{"type":"error","message":"i2c_bus_restarted"}` once per restart, then calls `Wire.end()` and `startRoomSensor()` (`Wire.begin`, `begin` at 0x76 then 0x77, `setConfig`, state restore, `updateSubscription`, callback; the same function `setup()` uses).
- The state restore uses the RAM copy with `setState` when one is held and prints `{"type":"bsec_state_restored","ok":true|false}`. Without a RAM copy (the sensor was not running, or `getState` failed) it asks the host as at boot (`bsec_state_request`, up to 10 s wait, ALARM lines applied during the wait). A RAM copy stays held until a start succeeds.
- The existing error lines are unchanged. Calling `Bsec2::begin()`, `setConfig()` and `updateSubscription()` again on the same object is safe in bsec2 1.10.2610: `begin()` reuses the BSEC instance memory and calls `bsec_init`, which clears the algorithm state, so the restore after `setConfig` puts the calibration back.

The BSEC calibration state is also kept on the laptop. See [BSEC state on the laptop](#bsec-state-on-the-laptop).

## BSEC state on the laptop

Bosch's BSEC library keeps its learned calibration state in RAM. A reset or power cut loses it. The laptop keeps a copy (user decision, 20 November 2026). See the [design](../docs/superpowers/specs/2026-11-20-bsec-state-on-laptop-design.md). Compiled and host-tested on 20 November 2026. On the board since 25 November 2026 (`f1a9dee`, then `49029f2`). On 25 November the board reached accuracy 3 and saved its state at 02:41:50, on a stuck gas reading. The RAM restore after a bus restart worked once. A restore from the laptop file after a board start is not checked.

Restore at start. In `startRoomSensor()` (called by `setup()`, and by a bus restart when no RAM copy of the state is held), after `setConfig` and before `updateSubscription` (the order of Bosch's example `basic_config_state.ino`), the board prints:

- `{"type":"bsec_state_request","bsec_version":"<x.y.z.w>"}`

It then waits up to 10 s (`ROOM_BSEC_STATE_WAIT_MS`) for one line from the host:

- `BSEC_STATE,<hex>`: the board calls `setState` and prints `{"type":"bsec_state_restored","ok":true}` or `{"type":"bsec_state_restored","ok":false}`. A state shorter than 238 bytes is padded with zeros, because `Bsec2::setState` always passes 238 bytes to BSEC.
- `BSEC_STATE,NONE`: the board prints nothing and starts without a state.
- No valid line in 10 s: the board prints nothing and starts without a state.

During the wait the board still applies `ALARM` commands and replies to them. It reads at most 64 bytes per pass, as in `loop()`. Invalid lines are ignored and the wait goes on. A `BSEC_STATE` line that arrives after the wait is treated as an invalid line. Opening the CH343 port does not reset the board (20 November 2026), so starting `monitor.py` does not cause a restore. The board asks only when it starts.

Save. `loop()` calls `saveBsecState()` after `roomSensor.run()`. The board sends its state only when the latest IAQ accuracy is 3: at once the first time after start, then every 6 hours (`ROOM_BSEC_STATE_SAVE_MS`) while the accuracy is 3. Six hours is Bosch's standard interval, from Bosch's example `basic_config_state.ino` (`STATE_SAVE_PERIOD`, 360 minutes). The line is:

- `{"type":"bsec_state","accuracy":3,"bsec_version":"<x.y.z.w>","state":"<hex>"}`

`Bsec2::getState` does not report the state length, so the board always sends all 238 bytes (`BSEC_MAX_STATE_BLOB_SIZE`) as 476 lowercase hex characters.

If `Bsec2::getState` fails, the board prints an error line and tries again after 60 seconds (`ROOM_BSEC_STATE_RETRY_MS`):

- `{"type":"error","message":"bsec_state_save_failed","bsec_code":<n>,"sensor_code":<n>}`

A lasting fault therefore sends this line once a minute. The line also shares the error rate limit of `reportRoomError`. The host parses it as its own kind, `bsec_state_save_failed`, not as a sensor error, and logs a `bsec_state_save_failed` event ("The board could not read its Bosch calibration state to save it. The board tries again.").

The host side: the monitor writes `<database name>.bsec_state.json` next to the database and answers each request with one line. It sends the state when the file exists and its BSEC version matches the request. Otherwise it sends `BSEC_STATE,NONE`. The BSEC state lines do not count as communication. See the main [README](../README.md#bosch-calibration-state).

Python receives the same JSON records at the same serial speed.
Its parser, fault rules and gas readiness rules need no change for this board.

## Pressure contract

The inspected wrapper converts pressure to hPa before the application callback.
The sketch therefore sends callback pressure without another division by 100.
Generic BSEC output documentation describes pressure in Pa.
Check this version-sensitive behavior before using another wrapper release.
Check real pressure units independently before accepting hardware results.

## Dependency references

| Component | Recorded version | Verification |
|---|---|---|
| Bosch BSEC2 wrapper | 1.10.2610, algorithm 2.6.1.0 | Installed. The build uses its precompiled `esp32s3` library. |
| Bosch BME68x wrapper | 1.3.40408 | Installed. Complete firmware compiled for the ESP32-S3. |
| ESP32 board core | 3.3.12 | Installed. Complete firmware compiled for the ESP32-S3. |
| arduino-cli | 1.5.1 | Used for the 15 November builds. |
| Arduino IDE | Course version 2.3.10 | Preserve this requirement. |

Python requirements.txt does not install these firmware libraries.
The sketch does not use the Adafruit BME680 library.
Bosch distributes algorithm binaries and configuration under its own license.
Use the upstream distribution rather than copying those files into this repository.
The source includes the matching Bosch three-second, four-day-history configuration.
Four days describes baseline history, not a required warm-up wait.

## Source organization

- room_environment_safety_control_bme680.ino handles BSEC setup (`startRoomSensor`), the I2C bus restart (`restartRoomBus`), callbacks, errors, the alarm outputs and the BSEC state request, restore and save.
- bus_recovery.h holds the pure I2C bus restart rule `roomBusRestartDue` and its constants (10 s without a valid reading, then at most one restart per 30 s; wrap-safe). Pure C++11, no Arduino dependency.
- bsec_board_config.h contains the chip check, all board pins, the buzzer polarity, serial speed, supply selection, reporting intervals, the alarm read bound, the alarm link timeout and blink period, the BSEC state save period (6 hours) and the restore wait (10 s).
- bsec_serial_format.h converts scalar values and status fields to JSON.
- sharp_dust.h runs experimental Sharp dust acquisition on GPIO4 (LED drive) and GPIO5 (analog input) and reports raw voltage records.
- sharp_dust_limits.h holds the pure dust sample rule: timing window, ADC limit 2750 mV, the 2:1 divider and `dustLedLevel` (LED logic level from the wanted state and the polarity).
- host_command.h reads host lines (`ALARM,<0|1|2>`, `BSEC_STATE,<hex>` of up to 238 bytes, `BSEC_STATE,NONE`) into a fixed 512-byte buffer, formats a BSEC state as hex and holds the state-save rule (accuracy 3, then once per period). Pure C++11, no Arduino dependency, no dynamic allocation.
- alarm_command.h is the local alarm command core: line parser on top of host_command.h, level to LED and buzzer, link-lost check and LED blink, polarity helper, bounded serial pump and reply formatter. Pure C++11, no Arduino dependency, no dynamic allocation.
- tests/test_bsec_serial_format.cpp, tests/test_alarm_command.cpp, tests/test_sharp_dust_limits.cpp, tests/test_host_command.cpp and tests/test_bus_recovery.cpp run without a board. Build and run each on Linux, for example `g++ -std=c++11 -Wall -Wextra -pedantic firmware/tests/test_alarm_command.cpp -o /tmp/test_alarm_command && /tmp/test_alarm_command`. The first three passed with no warnings on 15 November 2026 and again on 20 November 2026; all four passed with no warnings on 20 November 2026 after host_command.h was added; all five passed with no warnings on 25 November 2026 after bus_recovery.h was added.

## Verification status

- Completed: the host tests above, with g++ 11.4.0. Three test programs until 20 November 2026; four since `test_host_command.cpp` was added; five since `test_bus_recovery.cpp` was added (25 November 2026).
- Completed: compilation for the ESP32-S3 with `CDCOnBoot=default` and `CDCOnBoot=cdc`, `--warnings all`, no warnings (15 November, 8 MB options).
- Completed: a build for `esp32:esp32:esp32doit-devkit-v1` fails with the chip-check message.
- Completed on 17 November 2026: compilation with the 16 MB options above, no warnings, and upload to the board with every hash verified.
- Completed on 17 November 2026, without sensors: clean boot, `bsec_initialization_failed` (`sensor_code` -2) every 3 s with no BME680, matching alarm replies, and a 60 s `monitor.py` run with the alarm confirmed at level 0.
- Completed on 20 November 2026: the three host tests then present (all but `test_host_command.cpp`) with g++ 11.4.0, no warnings, and compilation with the 16 MB options and `CDCOnBoot=default`, `--warnings all`, no warnings (391518 bytes flash, 28752 bytes global RAM). No upload.
- Completed on 20 November 2026, after the alarm LED moved to the onboard RGB LED (`LED_BUILTIN`): all four host tests with g++ 11.4.0, no warnings, and compilation with the 16 MB options and `CDCOnBoot=default`, `--warnings all`, no warnings (391890 bytes flash, 29232 bytes global RAM). No upload.
- Completed on 20 November 2026, after the BSEC state save and restore: all four host tests with g++ 11.4.0, no warnings, and compilation with the 16 MB options and `CDCOnBoot=default`, `--warnings all`, no warnings (397162 bytes flash, 30192 bytes global RAM). No upload. Not checked on hardware.
- Completed on 20 November 2026, on firmware `1c74995`: the bench checks recorded in the hardware checklist (alarm replies, the onboard RGB LED, the link-lost blink, the dust fault through the monitor, the dashboard pages, and BME680 temperature, humidity and pressure).
- Completed on 25 November 2026, after the dust LED polarity fix (`ROOM_DUST_LED_ACTIVE_LOW`): all four host tests (the dust test now checks `dustLedLevel`), no warnings, and compilation with the 16 MB options and `CDCOnBoot=default`, `--warnings all`, no warnings (397210 bytes flash, 30200 bytes global RAM). No upload at that step.
- Completed on 25 November 2026, after the I2C bus restart (`bus_recovery.h`, `startRoomSensor`, `restartRoomBus`): all five host tests with g++ 11.4.0, no warnings, and compilation with the 16 MB options and `CDCOnBoot=default`, `--warnings all`, no warnings (397546 bytes flash, 30448 bytes global RAM). No upload at that step.
- Completed on 25 November 2026: upload of `f1a9dee` (397210 bytes, all four hashes verified) and of `49029f2` (397546 bytes flash, 30448 bytes globals, all four hashes verified). `tools/sensor_check.py` after the `49029f2` flash: readings PASS, dust PASS, gas FAIL (heater fault).
- Pending: the rest of the hardware checklist, including the buzzer output, a working gas reading and a meaningful `iaq` field (gas fails at the Bosch heater temperature, 25 November), the BSEC restore from the laptop file, and the BME680 drop-outs that the I2C bus restart did not always recover (25 November).
- Pending: a bench check of a real dust disconnect. The host floor rule is implemented (before-wiring item 8). On 20 November every reading was `dust_input_at_zero` (wrong LED polarity, found on 25 November) and the monitor raised the dust fault at 120 s.
- Pending: check that an invalid supply value fails with the supply-selection message.
- Pending: check startup, missing-data and read-failure error reporting on the board.
- Pending: check the six-second measurement watchdog, the three-second error interval and the millisecond counter rollover.

No dashboard, occupancy logic or environmental thresholds exist in this sketch. The sketch stores no BSEC state in flash. The laptop keeps it.

## Upstream references

- [BSEC2 API source](https://github.com/boschsensortec/Bosch-BSEC2-Library/tree/1.10.2610)
- [BME68x wrapper source](https://github.com/boschsensortec/Bosch-BME68x-Library/tree/v1.3.40408)
- [Adafruit BSEC guide](https://learn.adafruit.com/adafruit-bme680-humidity-temperature-barometic-pressure-voc-gas/bsec-air-quality-library)

## Sharp dust sensor extension

The experimental GP2Y1010AU0F path adds independent dust voltage and status. See [wiring, plan, calibration and verification](../docs/SHARP_DUST_INTEGRATION.md). It compiles for the ESP32-S3. Hardware timing remains pending.
