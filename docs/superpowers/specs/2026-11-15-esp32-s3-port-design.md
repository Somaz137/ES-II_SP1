# ESP32-S3 firmware port design

> **Note, 17 November 2026:** esptool shows the connected board is an N16R8-type module (16 MB quad flash, 8 MB embedded PSRAM, CH343 USB-UART bridge), not the N8R2 this document names. It was flashed with `esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default`. This document is kept as written. See the [17 November verification record](../../../reference_files/LINUX_VERIFICATION_2026-11-17.md).

Approved scope: the user changed the board to an ESP32-S3 with an N8R2 module (8 MB quad flash, 2 MB quad PSRAM) on 15 November 2026. This step ports the firmware source to that chip and wires the local alarm into the sketch, as the [local alarm design](2026-11-15-local-alarm-design.md) lists. Verification is compilation and host tests only. Nothing is flashed. No board is connected.

## Decisions taken by the user

- Board: ESP32-S3 N8R2.
- Pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, buzzer module (3-pin) GPIO7.
- Alarm levels: 0 off, 1 LED only, 2 LED and buzzer. Command `ALARM,<0|1|2>\n`. Reply `{"type":"alarm","state":<n>}`.

The pins are not checked against the physical board.

## Target and build

- `bsec_board_config.h` requires `CONFIG_IDF_TARGET_ESP32S3`. Any other chip fails with the message "Select an ESP32-S3 board (esp32:esp32:esp32s3). This firmware targets the ESP32-S3 N8R2."
- The chip check cannot identify the physical development board or its memory.
- All six board pins are named constants in `bsec_board_config.h`. `sharp_dust.h` uses them.
- FQBN: `esp32:esp32:esp32s3:FlashSize=8M,PSRAM=enabled,PartitionScheme=default_8MB,CDCOnBoot=<default|cdc>`. Flash mode stays the default (QIO).
- `CDCOnBoot=default` sends `Serial` to UART0, for a board whose USB port goes through a USB-UART bridge. `CDCOnBoot=cdc` sends `Serial` to the native USB port (hardware CDC). The source is the same for both. The choice is made at build time.

## Alarm wiring

- The sketch includes `alarm_command.h`.
- `setup()` sets GPIO6 and GPIO7 as outputs at level 0 first, before `Serial.begin`, the dust task and the BME680 start-up.
- `setup()` prints `formatAlarmReply(0)` once after `Serial.begin`, before the BME680 start-up. The host sees a reset at once. If the BME680 start-up fails, the reply has already been sent.
- `loop()` calls `pumpAlarmInput` first, before the BSEC configuration check. The alarm therefore works when the BME680 failed to start. A sensor alert lights the LED, so this matters.
- Each valid command sets both outputs from `alarmOutputs` and prints one reply. A repeated level also gets a reply; the host asks for one at every fault check. Malformed lines get no reply.
- Buzzer polarity is the constant `ROOM_BUZZER_ACTIVE_HIGH` in `bsec_board_config.h`. The default is `true` (HIGH sounds). The module's trigger level is not verified and must be checked on the real part. Reasons for the default: it matches `alarmOutputs` (true means on means HIGH) and the dust LED drive; the GPIO output latch is low after reset, so `pinMode(OUTPUT)` gives "off" with no first-level glitch for an active-high module; a wrong guess inverts the buzzer, so it sounds at level 0 right after power-on and the error is found at the first test.
- The alarm LED is active high (GPIO HIGH lights it through a series resistor to ground). This is a wiring assumption to check.
- The buzzer gets a steady level. No tone and no beep pattern. Whether the module needs a tone is a hardware check.

## Bounded command reading

- `pumpAlarmInput(source, reader, maxBytes, apply)` in `alarm_command.h` is pure and has a host test. It reads while `available() > 0` and stops after `maxBytes` bytes.
- The sketch passes `ROOM_ALARM_MAX_BYTES_PER_PASS = 64`. A command is 8 or 9 bytes. Bytes beyond 64 stay in the driver's receive buffer for the next pass.
- `available()` and `read()` do not wait on either `Serial` type. One pass costs at most 64 buffer reads and at most 64 replies (only for a flood of valid commands; the host sends one command per fault check).
- The dust task runs at priority 2 in its own FreeRTOS task. The loop task (priority 1) cannot delay it. BSEC chooses its own acquisition time and tolerates a loop pass that is a few milliseconds late.

## Whole output lines

- Only the loop task writes `Serial`: `reportDust`, `reportRoomError`, the BSEC callback (called from `roomSensor.run()` inside `loop()`) and the alarm reply. The dust task only updates counters under a spinlock. Lines therefore cannot interleave.
- The alarm reply is formatted into a buffer and written with one `Serial.println`.
- This rule is a comment in the sketch. Any new writer must stay in the loop task.

## Dust input on the ESP32-S3

Reviewed against ESP32 core 3.3.12 (`cores/esp32/esp32-hal-adc.c`):

- GPIO4 is ADC1 channel 3. ADC1 is not shared with Wi-Fi.
- `ADC_11db` has the value 3. The core passes it as `atten & 3`, which is ESP-IDF `ADC_ATTEN_DB_12`. The default attenuation is the same value.
- `analogReadMilliVolts` creates its calibration scheme with the global default attenuation, not the per-pin value. Both are 12 dB here, so the calibration matches.
- **Defect fixed:** `analogSetPinAttenuation` only reconfigures a pin that is already an ADC channel. `beginDust` called it before the first read, so the call did nothing; the default gave the same result. `beginDust` now primes the pin with a read first, then sets the attenuation, then reads once more outside the timed pulse.
- **Defect fixed:** the firmware accepted ADC samples below 3000 mV, so it could report `sensor_mv` up to 5999.x. `dust.py` rejects values above 5500 mV as "Invalid dust sensor voltage." The firmware now accepts ADC samples up to `ROOM_DUST_MAX_ADC_MV = 2750` (5500 mV at the sensor with the 2:1 divider). The mean of accepted samples times two is then at most 5500, which the host accepts. `sharp_dust_limits.h` holds the rule. A C++ host test and a Python test check it against `dust.py`.
- The new limit is also below the end of the ESP32-S3 12 dB range (about 3.1 V). That range end was not re-read from Espressif documentation in this step.
- The 2:1 divider (two equal 10 kohm resistors) is unchanged. It is a wiring assumption. Resistor tolerance changes the reported voltage directly.

Open points, not changed:

- The divider's source impedance (about 5 kohm) against the ADC sampling time is not checked.
- Pulse timing and the real ADC sampling instant need an oscilloscope.
- No calibration value is set. Concentration stays null until the user supplies a measured baseline and sensitivity.

## Serial output under native USB

With `CDCOnBoot=cdc`, the core's `HWCDC::write` waits up to `tx_timeout_ms` (100 ms) per block when the host is attached but not reading. This is output, not command reading. It is unchanged and must be checked on the board. With `CDCOnBoot=default`, writes go to the UART at 115200 baud.

## Python

No Python code changes. A test reads `ROOM_DUST_MAX_ADC_MV` from the header and checks that `dust.py` accepts twice that value and rejects anything above it.

## Not in scope

- No flashing, no hardware result.
- No Bosch outputs beyond the current ones. Gas resistance and dust voltage stay raw.
- No board-side fallback when the host is silent.
