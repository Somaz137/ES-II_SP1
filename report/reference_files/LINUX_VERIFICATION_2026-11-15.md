# Linux verification results - 15 November 2026

> **Note, 17 November 2026:** esptool shows the connected board is an N16R8-type module (16 MB quad flash, 8 MB embedded PSRAM, CH343 USB-UART bridge), not the N8R2 this document names. It was flashed with `esp32:esp32:esp32s3:FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,PSRAM=disabled,CDCOnBoot=default`. This document is kept as written. See the [17 November verification record](LINUX_VERIFICATION_2026-11-17.md).

An assistant ran these checks on the project Linux machine. A second assistant re-ran them.
The checks cover branch `feature/sharp-dust-integration` at commit 5e2de1b and `main` at commit 85d5f05.
No ESP32 was connected. No physical sensor or camera was used.

| Check | Result |
|---|---|
| Python test suite on `main` (85d5f05) | `python -m pytest` reported **301 passed**. Exit code 0. |
| Python test suite on this branch (5e2de1b) | **317 passed**. Exit code 0. No skips. No warnings with `-W error`. |
| New test files on this branch | `tests/test_dashboard.py` 1 case, `tests/test_dust.py` 11 cases, `tests/test_room_software.py` 4 cases. |
| Firmware JSON formatting test | `firmware/tests/test_bsec_serial_format.cpp` built with `g++ -std=c++11 -Wall -Wextra -pedantic` with no warnings. It ran with exit code 0. |
| Software demo | `monitor.py --demo` and `dashboard.py --demo` ran together with no errors. |
| Simulated temperature breach | Temperature rose above the example limit at about 18 s. The `limit_alert` event appeared at about 27 s. The `limit_ended` event appeared at about 61 s. |

The demo uses simulated serial records and always reports an occupied room.
The example limit (20 to 27 °C, 9 s) exists only for the simulator. It is not a patient limit.
These results establish software behavior. They do not establish sensor accuracy, camera detection, hardware timing, or room safety.

## Software versions

| Component | Recorded version |
|---|---|
| Python | 3.10.12 |
| NumPy | 1.26.4 |
| opencv-python | 4.11.0.86 |
| pyserial | 3.5 |
| Flask | 3.0.3 |
| PyYAML | 6.0.1 |
| pytest | 8.2.0 |
| SQLite (Python module) | 3.37.2 |
| g++ | 11.4.0 |

The package versions come from imports in the environment, not only from metadata.

## Environment note

The package `python3.10-venv` is not installed on this machine.
The environment at `env/` was therefore created without pip:

```bash
python3 -m venv --without-pip env
python3 -m pip --python env/bin/python install -r requirements.txt
```

The installed versions match `requirements.txt`.
The `env/` folder is excluded from version control.

## Board decision recorded today

On 15 November 2026 the user selected an ESP32-S3 with an N8R2 module (8 MB flash, 2 MB PSRAM).
This supersedes the DOIT ESP32 DevKit V1 selection. The decision is not implemented.

- The firmware source is unchanged. `firmware/bsec_board_config.h` still requires the classic ESP32 chip. It refuses to compile for an ESP32-S3.
- GPIO22 (I2C clock) and GPIO25 (dust LED drive) do not exist on the ESP32-S3. GPIO34 (dust input) is not an analog input on it.
- The user decided these ESP32-S3 pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7. They are not implemented and not checked against the physical board.
- The firmware compilation in the [8 November record](LINUX_VERIFICATION_2026-11-08.md) used ESP32 core 3.3.12, BSEC2 1.10.2610 and BME68x 1.3.40408 for the DOIT board on a different setup.
- On this machine, Arduino IDE 2.3.10 and ESP32 core 3.1.3 were present when checked. The Bosch libraries were not found.
- This machine is being set up to match the recorded versions: ESP32 core 3.3.12, BSEC2 1.10.2610, and BME68x 1.3.40408. That setup is in progress.
- Nothing has been compiled for the ESP32-S3. No ESP32-S3 has been connected or flashed. The exact development board model is not identified.

## ESP32-S3 firmware port - compilation only

Later on 15 November an assistant ported the firmware to the ESP32-S3 N8R2 on branch `feature/esp32-s3-port` and wired the local alarm into the sketch. See the [port design](../docs/superpowers/specs/2026-11-15-esp32-s3-port-design.md).
This is compilation and host testing only. No board was connected. Nothing was flashed. No sensor, LED or buzzer was driven.

| Tool | Version |
|---|---|
| arduino-cli | 1.5.1 (commit 01f3d4f2b) |
| ESP32 Arduino core (`esp32:esp32`) | 3.3.12 |
| Bosch BSEC2 | 1.10.2610, precompiled `esp32s3` library |
| Bosch BME68x Sensor library | 1.3.40408 |
| g++ | 11.4.0 |

arduino-cli needs the sketch folder to carry the main file's name. The repository folder is `firmware/`. The build therefore copied `firmware/*.ino` and `firmware/*.h` into a scratch folder named `room_environment_safety_control_bme680` and compiled that copy. Both commands used `--config-file /home/bridge/.local/share/room-arduino/arduino-cli.yaml` and a scratch `--build-path`.

```bash
arduino-cli compile --config-file /home/bridge/.local/share/room-arduino/arduino-cli.yaml \
  --fqbn "esp32:esp32:esp32s3:FlashSize=8M,PSRAM=enabled,PartitionScheme=default_8MB,CDCOnBoot=default" \
  --warnings all --build-path <BUILD_DIR> <SKETCH_DIR>/room_environment_safety_control_bme680

arduino-cli compile --config-file /home/bridge/.local/share/room-arduino/arduino-cli.yaml \
  --fqbn "esp32:esp32:esp32s3:FlashSize=8M,PSRAM=enabled,PartitionScheme=default_8MB,CDCOnBoot=cdc" \
  --warnings all --build-path <BUILD_DIR> <SKETCH_DIR>/room_environment_safety_control_bme680
```

| Build | Result |
|---|---|
| `CDCOnBoot=default` (Serial on UART0) | Exit code 0. No warnings. "Sketch uses 394008 bytes (11%) of program storage space. Maximum is 3342336 bytes." "Global variables use 28832 bytes (8%) of dynamic memory, leaving 298848 bytes for local variables. Maximum is 327680 bytes." Flags included `-DARDUINO_USB_CDC_ON_BOOT=0` and `-DBOARD_HAS_PSRAM`. |
| `CDCOnBoot=cdc` (Serial on native USB) | Exit code 0. No warnings. "Sketch uses 389392 bytes (11%) of program storage space. Maximum is 3342336 bytes." "Global variables use 29016 bytes (8%) of dynamic memory, leaving 298664 bytes for local variables. Maximum is 327680 bytes." Flags included `-DARDUINO_USB_CDC_ON_BOOT=1` and `-DBOARD_HAS_PSRAM`. |
| `esp32:esp32:esp32doit-devkit-v1` (old board) | Exit code 1, as intended: `bsec_board_config.h:6:2: error: #error "Select an ESP32-S3 board (esp32:esp32:esp32s3). This firmware targets the ESP32-S3 N8R2."` |
| `firmware/tests/test_alarm_command.cpp` | Built with `g++ -std=c++11 -Wall -Wextra -pedantic`, no warnings. Exit code 0. |
| `firmware/tests/test_bsec_serial_format.cpp` | Same flags, no warnings. Exit code 0. |
| `firmware/tests/test_sharp_dust_limits.cpp` (new) | Same flags, no warnings. Exit code 0. |
| Python suite | **462 passed**. Exit code 0. Also 462 passed with `-W error`. One new case in `tests/test_dust.py`. |

The compilation shows that the source builds for the selected chip with the listed versions. It does not show that the pins suit the physical board, that the alarm outputs or the buzzer polarity are right, or that sampling timing holds on the board.

## Evidence limits

- Firmware compilation ran only in the ESP32-S3 port section above. It is compilation only.
- No firmware was flashed.
- No ESP32, BME680, Sharp dust sensor or camera was connected.
- Occupancy detection did not run with a real camera. The demo bypasses the camera.
- The dashboard ran only on the local machine with simulated data.
- Alert timings come from one demo run. They depend on the three-second simulated reading interval and the five-second fault check.

## Remaining checks

- Identify the ESP32-S3 development board model. Check the decided pins against it.
- Done: toolchain versions are recorded in the ESP32-S3 port section.
- Done in the ESP32-S3 port section: chip check, pin constants and compilation of the complete sketch, including `firmware/sharp_dust.h`. Next, run the hardware checklist in `firmware/README.md`.
- Flash the board. Check BME680 wiring, supply, units, readings and three-second timing.
- Check the dust LED pulse and ADC sampling with an oscilloscope. Measure the clean-air baseline.
- Check physical USB disconnection, reconnection and board reset.
- Check camera capture and HOG detection with seated, lying and occluded people.
- Check the dashboard acknowledgment against a real communication outage.
- Check the buzzer, LED and "Silence alarm" behavior on the board. The buzzer polarity (`ROOM_BUZZER_ACTIVE_HIGH`, default true) is unverified.

Do not repeat these software checks without a code, dependency or environment change, a failure, or a specific unresolved concern.
