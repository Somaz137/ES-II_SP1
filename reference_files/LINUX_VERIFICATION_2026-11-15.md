# Linux verification results - 15 November 2026

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

## Evidence limits

- No firmware compilation ran today. No compilation of the sketch that includes `firmware/sharp_dust.h` is recorded.
- No firmware was flashed.
- No ESP32, BME680, Sharp dust sensor or camera was connected.
- Occupancy detection did not run with a real camera. The demo bypasses the camera.
- The dashboard ran only on the local machine with simulated data.
- Alert timings come from one demo run. They depend on the three-second simulated reading interval and the five-second fault check.

## Remaining checks

- Identify the ESP32-S3 development board model. Check the decided pins against it.
- Finish the toolchain setup and record the installed versions.
- Adapt the chip check and pin constants for the ESP32-S3. Compile the complete sketch, including `firmware/sharp_dust.h`, with agreed core and Bosch library versions.
- Flash the board. Check BME680 wiring, supply, units, readings and three-second timing.
- Check the dust LED pulse and ADC sampling with an oscilloscope. Measure the clean-air baseline.
- Check physical USB disconnection, reconnection and board reset.
- Check camera capture and HOG detection with seated, lying and occluded people.
- Check the dashboard acknowledgment against a real communication outage.
- Check the decided buzzer, LED and "Silence alarm" behavior after it is implemented.

Do not repeat these software checks without a code, dependency or environment change, a failure, or a specific unresolved concern.
