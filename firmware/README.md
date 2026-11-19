# ESP32-S3 BSEC firmware

**Target:** an ESP32-S3 (QFN56, revision v0.2) with 16 MB quad flash and 8 MB embedded PSRAM, an N16R8-type module. esptool read these facts from the connected board on 17 November 2026. The documents assumed an N8R2 module until then. The board was selected on 15 November 2026. It supersedes the DOIT ESP32 DevKit V1.
**Status:** the board was flashed on 17 November 2026. The serial link and the alarm protocol were checked without sensors. See the [17 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-17.md). The exact development board model is not identified. Sensor, LED and buzzer behaviour is unverified.
The 8 November build for the DOIT board is history. See the [8 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-08.md).

This source prepares BSEC low-power acquisition every three seconds, experimental Sharp dust acquisition and a local LED and buzzer alarm.
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

The user decided these pins. They are not checked against the physical board. All are named constants in bsec_board_config.h.

| Function | GPIO | Constant | Note |
|---|---|---|---|
| BME680 SDA | GPIO8 | ROOM_I2C_SDA_PIN | |
| BME680 SCL | GPIO9 | ROOM_I2C_SCL_PIN | |
| Dust analog input (Vo through 2:1 divider) | GPIO4 | ROOM_DUST_ADC_PIN | ADC1 channel 3 |
| Dust LED drive (NPN base through 1 kohm) | GPIO5 | ROOM_DUST_LED_PIN | HIGH turns the sensor LED on |
| Alarm LED (series resistor to ground) | GPIO6 | ROOM_ALARM_LED_PIN | HIGH lights the LED |
| Buzzer module signal (3-pin module) | GPIO7 | ROOM_BUZZER_PIN | Polarity: ROOM_BUZZER_ACTIVE_HIGH |

Connect all grounds together. Use the breakout documentation to identify the BME680 power terminal.
The dust circuit is in [SHARP_DUST_INTEGRATION.md](../docs/SHARP_DUST_INTEGRATION.md).

`ROOM_BUZZER_ACTIVE_HIGH` defaults to `true`: HIGH sounds the buzzer. The module's trigger level is not verified. Many 3-pin modules trigger on LOW. If the buzzer sounds right after power-on (level 0), the polarity is wrong: set the constant to `false` and rebuild.

## Choosing CDC On Boot

- `CDCOnBoot=default`: `Serial` is UART0. Use it when the USB cable goes into a port served by a USB-UART bridge chip (often labelled UART or COM). On Linux the port is usually `/dev/ttyUSB<n>` or `/dev/ttyACM<n>`, depending on the bridge chip.
- `CDCOnBoot=cdc`: `Serial` is the native USB port of the ESP32-S3 (hardware CDC). Use it when the cable goes into the port wired to GPIO19/GPIO20 (often labelled USB). On Linux the port is usually `/dev/ttyACM<n>`.
- This board's USB port goes through a CH343 bridge (USB 1a86:55d3). It carries UART0, so use `CDCOnBoot=default`. Linux names it `/dev/ttyACM0`. The flash on 17 November 2026 used this setting.
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

The board was flashed on 17 November 2026 with nothing wired to it. The serial link and the alarm replies were checked. See the [17 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-17.md). Items marked partly done say what is still open. All other items are still to do.

Before wiring the board:

1. Identify the exact ESP32-S3 board and get its pinout and schematic.
2. Check that GPIO4 to GPIO9 are broken out and free on this board. Check that GPIO6 and GPIO7 are not used by an on-board RGB LED, button or other part.
3. Check that no wire goes to a strapping pin (GPIO0, GPIO3, GPIO45, GPIO46). Check that nothing pulls these pins at reset.
4. Done on 17 November 2026: the laptop uses the CH343 USB-UART bridge (USB 1a86:55d3), Linux port `/dev/ttyACM0`, `CDCOnBoot=default`.
5. Check the alarm LED series resistor value and that the LED current is within the GPIO limit.
6. Read the buzzer module's markings or documentation for its trigger level and supply voltage. Set `ROOM_BUZZER_ACTIVE_HIGH` to match. Check that the module's signal input is safe at 3.3 V.
7. Check the BME680 breakout supply (3.3 V) and its I2C address pin (0x76 or 0x77).
8. Measure the dust divider with a meter. Check that the ADC pin never sees more than about 3.1 V.
9. Dust disconnect: the host applies a floor rule (decided and implemented on the host on 20 November 2026). A dust voltage below `dust.disconnected_below_mv` (default 100 mV, sensor side), a 0 mV reading, or the board's `dust_input_at_zero` report all count as "no reading". After `sensor_error_timeout_s` (120 s) with no reading at or above the floor, the dust status is `not_connected` and the dust fault is on. Not yet checked on the bench: with the 2:1 divider wired and no sensor, confirm that the input reads below 100 mV (on 17 November, with nothing wired, the floating input read about 870 to 930 mV) and that a connected sensor reads above it.

After flashing:

1. Partly done on 17 November 2026: the first firmware line after reset was `{"type":"alarm","state":0}`. Still open: check that the LED and buzzer are off.
2. Partly done on 17 November 2026: `ALARM,0`, `ALARM,1`, `ALARM,2` and `ALARM,0` each got the matching reply in about 10 ms, and `ALARM,9` got none. Still open: check the LED and the buzzer, and whether the buzzer needs a tone instead of a steady level.
3. Check BME680 readings every three seconds, their units and the address in use.
4. Check the dust LED pulse width (0.32 ms), the sampling point (0.28 ms) and the 10 ms period on an oscilloscope. Check the accepted and rejected sample counts.
5. Check whether opening the serial port resets the board.
6. With native USB: check what happens to readings when the laptop stops reading the port.
7. Link-lost fallback: stop `monitor.py`. Check that the LED blinks (1 s on, 1 s off) after about 30 s and that the buzzer keeps its last state. Start `monitor.py` again and check that its next command stops the blink.

## Local alarm

The host sends `ALARM,0` (LED and buzzer off), `ALARM,1` (LED only) or `ALARM,2` (LED and buzzer). See the [local alarm design](../docs/superpowers/specs/2026-11-15-local-alarm-design.md) and the [port design](../docs/superpowers/specs/2026-11-15-esp32-s3-port-design.md).

- `setup()` sets both outputs to level 0 before `Serial.begin`, the dust task and the BME680 start-up.
- `setup()` prints `{"type":"alarm","state":0}` once after `Serial.begin`. With native USB this line can be lost if the laptop has not opened the port yet. The host repeats its command at every fault check.
- `loop()` reads at most 64 bytes per pass with `pumpAlarmInput`. It never waits for input. It runs even when the BME680 failed to start.
- Each valid command sets the outputs and prints one reply. Malformed lines get no reply.
- The buzzer gets a steady level. There is no tone and no beep pattern.
- Link-lost fallback: when no valid command arrives for 30 s (`ROOM_ALARM_LINK_TIMEOUT_MS`), the LED blinks, 1 s on and 1 s off (`ROOM_ALARM_BLINK_HALF_PERIOD_MS`). The buzzer keeps its last commanded state. The timer starts at boot, and only a valid `ALARM` command resets it; malformed lines do not. The next valid command ends the blink. The board prints no line for this. The host normally sends a command every 5 s (`fault_check_interval_s`). Implemented and compiled on 20 November 2026; not checked on hardware.
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
- `{"type":"dust_error","message":"dust_input_at_zero"}`: the window failed (fewer than 100 accepted samples, or more rejected than accepted) and more than half of all its samples read 0 mV with good timing. A missing sensor at about 0 V gives this line. The host counts it as below the floor. Added on 20 November 2026; compiled, not checked on hardware.
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
Initialization failures continue reporting until intervention or restart.
Automatic sensor reinitialization and calibration-state storage remain future work. Without stored state the index calibrates again after each board start.

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

- room_environment_safety_control_bme680.ino handles BSEC setup, callbacks, errors and the alarm outputs.
- bsec_board_config.h contains the chip check, all board pins, the buzzer polarity, serial speed, supply selection, reporting intervals, the alarm read bound and the alarm link timeout and blink period.
- bsec_serial_format.h converts scalar values and status fields to JSON.
- sharp_dust.h runs experimental Sharp dust acquisition on GPIO5 (LED drive) and GPIO4 (analog input) and reports raw voltage records.
- sharp_dust_limits.h holds the pure dust sample rule: timing window, ADC limit 2750 mV and the 2:1 divider.
- alarm_command.h is the local alarm command core: line parser with a fixed 32-byte buffer, level to LED and buzzer, link-lost check and LED blink, polarity helper, bounded serial pump and reply formatter. Pure C++11, no Arduino dependency, no dynamic allocation.
- tests/test_bsec_serial_format.cpp, tests/test_alarm_command.cpp and tests/test_sharp_dust_limits.cpp run without a board. Build and run each on Linux, for example `g++ -std=c++11 -Wall -Wextra -pedantic firmware/tests/test_alarm_command.cpp -o /tmp/test_alarm_command && /tmp/test_alarm_command`. All three passed with no warnings on 15 November 2026 and again on 20 November 2026.

## Verification status

- Completed: the three host tests above, with g++ 11.4.0.
- Completed: compilation for the ESP32-S3 with `CDCOnBoot=default` and `CDCOnBoot=cdc`, `--warnings all`, no warnings (15 November, 8 MB options).
- Completed on 17 November 2026: compilation with the 16 MB options above, no warnings, and upload to the board with every hash verified.
- Completed on 20 November 2026: the three host tests above with g++ 11.4.0, no warnings, and compilation with the 16 MB options and `CDCOnBoot=default`, `--warnings all`, no warnings (391518 bytes flash, 28752 bytes global RAM). No upload.
- Completed on 17 November 2026, without sensors: clean boot, `bsec_initialization_failed` (`sensor_code` -2) every 3 s with no BME680, matching alarm replies, and a 60 s `monitor.py` run with the alarm confirmed at level 0.
- Completed: a build for `esp32:esp32:esp32doit-devkit-v1` fails with the chip-check message.
- Pending: the rest of the hardware checklist, including the LED and buzzer outputs, BME680 readings and the `iaq` field, and dust readings.
- Open: a disconnected dust sensor cannot currently be told apart from a working one (checklist item 9).
- Pending: check that an invalid supply value fails with the supply-selection message.
- Pending: check startup, missing-data and read-failure error reporting on the board.
- Pending: check the six-second measurement watchdog, the three-second error interval and the millisecond counter rollover.

No dashboard, occupancy logic, environmental thresholds, or state persistence exists in this sketch.

## Upstream references

- [BSEC2 API source](https://github.com/boschsensortec/Bosch-BSEC2-Library/tree/1.10.2610)
- [BME68x wrapper source](https://github.com/boschsensortec/Bosch-BME68x-Library/tree/v1.3.40408)
- [Adafruit BSEC guide](https://learn.adafruit.com/adafruit-bme680-humidity-temperature-barometic-pressure-voc-gas/bsec-air-quality-library)

## Sharp dust sensor extension

The experimental GP2Y1010AU0F path adds independent dust voltage and status. See [wiring, plan, calibration and verification](../docs/SHARP_DUST_INTEGRATION.md). It compiles for the ESP32-S3. Hardware timing remains pending.
