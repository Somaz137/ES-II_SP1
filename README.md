# SAFE-ROOM — Ubuntu 22.04 laptop + ESP32 starter

**Scope:** dependency environment + minimal BME680 serial test. **Not** the complete Project 8 implementation. No patient-specific limits or medical safety guarantees are included.

## Which versions are from the lectures?

- Python 3.10.x — Module 3.2 laptop platform.
- NumPy 1.26.4 and OpenCV 4.11.0.86 — Module 3.2.
- pyserial 3.5 and baud 115200 — Module 3.3.
- Flask 3.0.3, PyYAML 6.0.1, pytest 8.2.0 — Module 3.4 and `vigil/requirements.txt`.
- SQLite is built into Python; install **no** sqlite3 pip distribution.
- Arduino IDE 2.3.10 — Module 3.3.

**Additional proposed firmware versions, from online vendor/project sources (not specified in the lectures):** ESP32 Arduino board core **3.3.12** (stable as checked Nov 7, 2026); Adafruit BME680 Library **2.0.6**; dependencies installed when prompted by Arduino Library Manager. These versions have NOT been compilation-tested with the user's hardware. If compilation problems arise, capture the compile output before changing versions.

## Prerequisites and Python environment

Use Ubuntu 22.04 x86-64 (not Jetson) with Python 3.10.x. In a terminal in this folder:

```bash
chmod +x setup_ubuntu.sh
./setup_ubuntu.sh
```

This installs APT prerequisites (`python3-venv`, `python3-pip`, `libgl1`, `libglib2.0-0`, `v4l-utils`), creates `.venv`, installs pinned Python requirements, runs `pip check`, and displays system/port status. No JetPack/CUDA packages are installed. It does **not** modify ESP32 board firmware.

To activate the virtual environment in later terminals:

```bash
source .venv/bin/activate
python tools/check_setup.py
```

To let your user access USB serial ports:

```bash
sudo usermod -aG dialout "$USER"
```

**Log out and back in** before using the new group membership. Device may be `/dev/ttyUSB0`, `/dev/ttyACM0`, or a persistent symlink in `/dev/serial/by-id/`.

## Arduino IDE

If Arduino IDE is not already installed, lecture Module 3.3 (pp. 4–6) uses version **2.3.10** as a 64-bit AppImage and requires:

```bash
sudo apt install libfuse2
```

Download from the Arduino project's official downloads or follow the *full URL* on p.5 of Module 3.3. In Arduino IDE, add Espressif's stable Boards Manager URL:

`https://espressif.github.io/arduino-esp32/package_esp32_index.json`

Lecture shows an equivalent GitHub raw URL. Install `esp32` by **Espressif Systems**, select **DOIT ESP32 DEVKIT V1** (for the course's 30-pin WROOM board) and your actual USB port. Record the installed board-core version. The lecture does **not** pin one.

Install **Adafruit BME680 Library** via Library Manager (candidate 2.0.6) and accept required library dependencies. This library is **not in the uploaded lectures** because Modules 4.2 and 4.3 are missing; it is an external implementation choice.

## Wiring (power disconnected)

| BME680 module | ESP32 DevKit V1 |
|---|---|
| VCC/VIN (3.3 V compatible breakout only) | 3V3 |
| GND | GND |
| SDA | GPIO21 |
| SCL | GPIO22 |

Check your *exact* BME680 breakout board's labeled pins, power requirements, and onboard pull-ups. **Never connect 5 V directly to ESP32 GPIO.** Typical I2C addresses 0x76/0x77; the test firmware tries both.

## First hardware test

1. Disconnect power, wire BME680, then connect USB.
2. Open `firmware/safe_room_bme680.ino` in Arduino IDE and upload it.
3. Close **Serial Monitor** before opening the same port from Python (one application at a time).
4. In activated `.venv`, run:

```bash
python -m serial.tools.list_ports -v
python tools/read_sensor.py --port /dev/ttyUSB0
```

Replace the port with your actual detected device. Output will be newline-delimited JSON resembling:

`{"type":"reading","temp_c":25.1,"humidity_pct":45.6,"pressure_hpa":1005.2,"gas_ohms":120000}`

The values above are **illustrative only**. If you get `bme680_not_found`, verify wiring/address. If access is denied, check active `dialout` group membership. If the device disappears, check `dmesg` for USB driver / `brltty` conflicts before changing system packages.

## Next software stages (not yet implemented)

1. Store timestamps and samples to SQLite; detect missing/stale measurements.
2. Camera occupancy via OpenCV; avoid assuming motion detection catches stationary patients. Start with a manual occupancy override for unit testing; evaluate the actual person-detection method separately.
3. YAML config and clinician-facing edit form; validate thresholds and save changes safely.
4. Per-metric sustained-time breach rules with recovery/hysteresis, cooldown, offline handling.
5. Nonblocking alert worker + optional ESP32 local LED/buzzer on **non-I2C pins** (e.g. GPIO23 with a series resistor for an LED).
6. Flask dashboard with live values, 24-hour history and alert log.
7. pytest tests: brief spike, sustained breach, recovery, missing sensor, absent occupant, alert delay and offline mode.

**Clinical limitation:** teaching prototype, not a medical device. Do not invent universally safe patient limits; thresholds must be provided for an actual use case by an appropriate supervisor/clinician. BME680 gas resistance is not a calibrated AQI, CO2, CO or specific hazard detection reading.

## Source traceability

- Project #8: Idea Book, pages 21–22.
- Environment and package versions: Module 3.2, pages 3–4 and installation examples.
- ESP32 GPIO, 3.3V safety, IDE and serial: Module 3.3, pages 3–8.
- VIGIL implementation architecture/dependencies: Module 3.4, pages 3–7; `vigil_v0.8.zip`.
- External BME680 wiring and API: https://learn.adafruit.com/adafruit-bme680-humidity-temperature-barometic-pressure-voc-gas/arduino-wiring-test
- External ESP32 Arduino core versions: https://github.com/espressif/arduino-esp32/releases
- External BME680 library metadata: https://github.com/adafruit/Adafruit_BME680/blob/master/library.properties
