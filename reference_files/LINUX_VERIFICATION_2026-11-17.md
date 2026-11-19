# Linux verification results - 17 November 2026

On 17 November 2026 an assistant flashed the ESP32-S3 for the first time and checked the serial link and the alarm protocol.
The firmware came from branch `feature/dashboard-pages` at commit 4f84c19.
Nothing else was wired to the board. No BME680, Sharp dust sensor, LED, buzzer or camera was connected.

## Board identity

esptool read these facts from the connected board:

| Item | Value |
|---|---|
| Chip | ESP32-S3 (QFN56), revision v0.2 |
| Flash | 16 MB, quad, 3.3 V |
| PSRAM | 8 MB, embedded (AP_3v3) |
| Module type | N16R8-type, not the N8R2 the documents assumed |
| USB-UART bridge | CH343, USB ID 1a86:55d3 |
| Linux port | `/dev/ttyACM0` |

The board's USB port goes through the CH343 bridge. It carries UART0, not the native USB of the ESP32-S3. The build therefore uses `CDCOnBoot=default`.
PSRAM is disabled in the build. The firmware does not use it.
The exact development board model and its pinout are still not identified.

## Build and upload

The build copied `firmware/*.ino` and `firmware/*.h` into a scratch folder named `room_environment_safety_control_bme680`, as in the [15 November record](LINUX_VERIFICATION_2026-11-15.md).
Tools: arduino-cli 1.5.1 and ESP32 core 3.3.12, with the same configuration file as on 15 November.

```bash
arduino-cli compile --config-file /home/bridge/.local/share/room-arduino/arduino-cli.yaml \
  --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default" \
  --warnings all --build-path <BUILD_DIR> <SKETCH_DIR>/room_environment_safety_control_bme680

arduino-cli upload --config-file /home/bridge/.local/share/room-arduino/arduino-cli.yaml \
  -p /dev/ttyACM0 \
  --fqbn "esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default" \
  --build-path <BUILD_DIR> <SKETCH_DIR>/room_environment_safety_control_bme680
```

The partition scheme `app3M_fat9M_16MB` is "16M Flash (3MB APP/9.9MB FATFS)" in the core's board options.

| Step | Result |
|---|---|
| Compile | Exit code 0. No warnings. "Sketch uses 391286 bytes (12%) of program storage space. Maximum is 3145728 bytes." "Global variables use 28736 bytes (8%) of dynamic memory, leaving 298944 bytes for local variables. Maximum is 327680 bytes." |
| Upload | Exit code 0. The application went to 0x10000: "Wrote 391440 bytes (233224 compressed) at 0x00010000 in 3.2 seconds". Each written region reported "Hash of data verified." The upload ended with "Hard resetting via RTS pin...". |

## Serial capture

A small pyserial script opened `/dev/ttyACM0` at 115200 baud, reset the board with an RTS pulse and logged every line with a time stamp.
The board booted cleanly. The ROM lines were followed by the firmware's start-up alarm reply:

```text
[  0.232] RX rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)
[  0.232] RX entry 0x403c88b8
[  0.334] RX {"type":"alarm","state":0}
[  0.334] RX {"type":"error","message":"bsec_initialization_failed","bsec_code":0,"sensor_code":-2}
[  3.319] RX {"type":"dust","sensor_mv":896.5,"samples":299,"rejected_samples":1}
[  3.340] RX {"type":"error","message":"bsec_initialization_failed","bsec_code":0,"sensor_code":-2}
```

With no BME680 attached, the firmware reported `bsec_initialization_failed` with `sensor_code` -2 every 3 s. This is the expected record for a missing sensor. It is not a firmware fault.

After 30 s the script sent four alarm commands one second apart, then one malformed command:

```text
[ 30.202] TX ALARM,0\n
[ 30.213] RX {"type":"alarm","state":0}
[ 31.212] TX ALARM,1\n
[ 31.223] RX {"type":"alarm","state":1}
[ 32.214] TX ALARM,2\n
[ 32.224] RX {"type":"alarm","state":2}
[ 33.215] TX ALARM,0\n
[ 33.225] RX {"type":"alarm","state":0}
[ 34.217] TX ALARM,9\n
[ 36.352] RX {"type":"dust","sensor_mv":885.1,"samples":300,"rejected_samples":0}
```

Each valid command got one reply with the matching state, about 10 ms later. `ALARM,9` got no reply. The dust and error records continued.

## Monitor run

`monitor.py` ran against the board for 60 s with a scratch database and the default configuration files. No patient profile was set.

```bash
timeout -s INT 60 env/bin/python monitor.py --port /dev/ttyACM0 --db <SCRATCH_DB>
```

- The monitor printed 48 status records. `timeout` stopped it with exit code 124, as intended. The output had no traceback.
- The first record showed the port not yet connected. The next showed the alarm request pending. From the third record the alarm state was `confirmed` at level 0.
- The last 45 records showed `input_status` `sensor_error` with diagnostic `bsec_initialization_failed`. The communication alert stayed off.
- The sensor alert was not raised within the 60 s. Its timeout (`sensor_error_timeout_s`) is 120 s, so this run does not test it.
- The dust status was `fresh` in those records, for example at 901.5 mV. See the open issue below.

The port was free after the run.

## Not verified

- The alarm LED and buzzer outputs. Nothing was wired to GPIO6 or GPIO7. Only the serial replies were seen.
- BME680 readings, their units and timing, and the `iaq` field. No BME680 was attached.
- Dust readings. No dust sensor was attached.
- The sensor alert on the real board, which needs more than 120 s of sensor errors.
- The decided pins against the physical board's pinout.
- Physical USB disconnection and reconnection.

## Open issue: floating dust input

With no dust sensor attached, the dust input read about 870 to 930 mV (872.1 to 929.8 mV in the capture). The firmware sent these as normal dust records with almost no rejected samples. The monitor accepted them as fresh dust records.
The most likely cause is the floating ADC pin (GPIO4).
A disconnected dust sensor therefore cannot currently be told apart from a working one.

Candidate fixes. Neither is decided. The user will choose when the sensor is wired.

- A pull-down resistor on the dust input, so that a disconnected sensor reads near 0 mV.
- A firmware check that compares the signal with the sensor LED on and off. A floating pin would show no difference.

## Evidence notes

The raw logs (compile, upload, serial capture and monitor output) were saved in a session scratch folder. That folder was cleared before this record was written. The excerpts above are copied from the tool output recorded during the run.
