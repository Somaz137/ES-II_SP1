# Sharp GP2Y1010AU0F integration

## Plan and implementation status

1. Confirm sensor: user supplied a photo of a bare six-pin sensor with cable, resistor and capacitor.
2. Add experimental ESP32 acquisition in firmware/sharp_dust.h; initialize before BME680 and report independently every three seconds. Implemented.
3. Route separate dust/dust_error records without overwriting BME680 readings or readiness. Implemented in dust.py and monitoring_state.py.
4. Expose retained voltage, age, status and separate timeout in status_output.py. Dust uses the existing configured sensor timeout (120 seconds by default). BME680 silence while dust messages arrive is also exposed. Implemented.
5. Add optional explicit calibration in monitor.py. Default concentration is null. Implemented, then replaced on 15 November 2026 by the automatic baseline below.
8. Show an estimated concentration with a word level and an automatic clean-air baseline, with a system-setup limit. Implemented on 15 November 2026; tests and simulator only.
6. Verify host behavior and document hardware checks. The full pinned Ubuntu suite passed on 15 November 2026. The sketch with `firmware/sharp_dust.h` compiled for the ESP32-S3 on 15 November 2026. Oscilloscope timing and physical calibration are pending.
7. Port to the ESP32-S3: GPIO5 LED drive, GPIO4 analog input, ADC limit aligned with `dust.py`. Implemented and compiled. Correction, 20 November 2026: the pins were swapped (GPIO5 analog input, GPIO4 LED drive). Correction, 25 November 2026: the LED polarity was fixed; dust readings work on the board.

## Wiring design: ESP32-S3

The user selected an ESP32-S3 with an N8R2 module on 15 November 2026. Correction, 17 November 2026: esptool shows the connected board is an N16R8-type module (16 MB flash, 8 MB embedded PSRAM), not an N8R2. It supersedes the DOIT ESP32 DevKit V1. The dust LED drive is GPIO5 (in place of GPIO25). The dust analog input is GPIO4, ADC1 channel 3 (in place of GPIO34). The BME680 I2C pins are SDA GPIO8 and SCL GPIO9. The firmware uses these pins through `firmware/bsec_board_config.h`. History (15 to 20 November 2026): they were not checked against the physical board then. Dust readings passed on the board on 25 November 2026 after the LED polarity fix. The circuit itself is unchanged. Correction, 20 November 2026: the dust pins were swapped to match the user's wiring. The dust analog input is GPIO5, ADC1 channel 4. The dust LED drive is GPIO4. The table below uses these pins.

Verify connector numbering against Sharp's drawing. Cable colours are not a pinout.
Do not connect the sensor's analog output directly to ESP32 GPIO; it goes through the 2:1 divider.

Wiring in use, measured on 25 November 2026: GPIO4 drives sensor pin 3 directly, with no NPN transistor. The LED is on when GPIO4 is LOW. A diagnostic pulse LOW on GPIO4 gave 446 to 528 mV at GPIO5 (mean 470 mV); a pulse HIGH gave 0.8 to 1.8 mV. The firmware assumed the NPN driver until then and so turned the LED off for every sample. `ROOM_DUST_LED_ACTIVE_LOW` in `firmware/bsec_board_config.h` is `true` for this wiring. GPIO4 stays a push-pull output, so off is HIGH (3.3 V). It is not open-drain: a released pin would float toward 5 V through the LED, above the ESP32-S3 pin limit. With the fix (firmware `49029f2`), the board sent 60 of 60 dust records at 892.7 to 1135.0 mV sensor side on 25 November 2026. Before `beginDust()` runs (during reset and boot), GPIO4 is not yet an output, so the LED state in that window is not set by the firmware. A meter check of the GPIO4 voltage and current is a hardware follow-up.

| Sensor pin | Connection |
|---|---|
| 1 V-LED | 5 V through 150 ohm resistor; 220 uF capacitor positive to pin 1, negative to pin 2 |
| 2 LED-GND | Common ground |
| 3 LED | In use (25 November 2026): GPIO4 directly; LOW turns the LED on (`ROOM_DUST_LED_ACTIVE_LOW = true`). Alternative: NPN collector; emitter to common ground; GPIO4 through 1 kohm to base; 10 kohm base-to-emitter pull-down; HIGH turns the LED on (set `ROOM_DUST_LED_ACTIVE_LOW = false`) |
| 4 S-GND | Common ground |
| 5 Vo | 10 kohm to GPIO5 node; another 10 kohm from node to ground (2:1 divider) |
| 6 Vcc | Regulated 5 V |

For the NPN alternative, use an NPN rated to sink at least 20 mA, e.g. a suitable 2N3904; check the actual transistor pinout. This is an external low-side LED driver: GPIO HIGH enables the LED, so set `ROOM_DUST_LED_ACTIVE_LOW` to `false` before flashing. Keep the existing BME680 supply at 3.3 V on I2C GPIO8/GPIO9.

Check that the supplied resistor is 150 ohm and capacitor is 220 uF, rated at least 10 V. Additional parts: two 10 kohm resistors for the divider; the NPN alternative adds a third 10 kohm resistor, one 1 kohm resistor and one NPN transistor. Keep wiring short. Confirm ADC voltage with a meter before attaching GPIO5; the divider produces half the sensor voltage. All grounds must be common. Do not join independent 5 V sources together.

## Acquisition and limitations

Sharp specifies a 10 ms cycle, a 0.32 ms LED pulse and sampling 0.28 ms after LED turn-on. A FreeRTOS task performs acquisition; the main loop alone writes serial output. No added third-party library is required. Existing dependency pins are unchanged.

This firmware is experimental. Arduino ADC call latency and task preemption can violate the pulse window. Detected overruns are discarded; fewer than 100 accepted samples per report or more rejected than accepted samples produces dust_error. When more than half of all samples in that window read 0 mV with good timing, the message is `dust_input_at_zero` (a missing sensor at about 0 V); otherwise it is `dust_acquisition_unavailable`. Added on 20 November 2026. The board sent `dust_input_at_zero` on 20 and 25 November 2026, while the LED polarity was wrong. The software timestamps do not prove the actual ADC aperture. Verify waveform and ADC sampling on the installed ESP32 core before accepting readings. If the ADC cannot meet the timing, acquisition needs a hardware-timed redesign, not relaxed limits.

The sensor has no digital identity or self-test. A plausible analog voltage cannot prove it is connected or healthy. A disconnected or failed sensor can look plausible. The host detects missing/invalid reports, not every physical fault.

## ADC on the ESP32-S3

Reviewed against ESP32 core 3.3.12 (`cores/esp32/esp32-hal-adc.c`) on 15 November 2026. This is a source reading, not a measurement.

- `ADC_11db` is passed to ESP-IDF as `ADC_ATTEN_DB_12`. It is also the core's default attenuation, which the millivolt calibration uses.
- The core applies `analogSetPinAttenuation` only to a pin that is already an ADC channel. The firmware now reads the pin once before setting it. Before this change the call had no effect; the default gave the same attenuation.
- The firmware accepts ADC samples from 1 mV to 2750 mV (`firmware/sharp_dust_limits.h`). With the 2:1 divider that is at most 5500 mV at the sensor, the largest value `dust.py` accepts. Before this change the firmware accepted ADC samples below 3000 mV, so it could report up to 5999.x mV, which `dust.py` rejected as invalid. A C++ host test and `tests/test_dust.py` check the match.
- 2750 mV is below the end of the 12 dB range on the ESP32-S3 (about 3.1 V). That range end was not re-read from Espressif documentation in this step.
- A zero reading means a failed read in the core. It is rejected. Zero readings with good timing are also counted apart for the `dust_input_at_zero` report.

Open points:

- The divider is a wiring assumption. Resistor tolerance changes the reported voltage directly. Measure it.
- The divider's source impedance (about 5 kohm) against the ADC sampling time is not checked.
- The real sampling instant within the LED pulse needs an oscilloscope.

## Estimate and baseline

Decision of 15 November 2026: dust is shown as an estimated concentration with a word level, labelled "estimate". This replaces the earlier rule that dust voltage is a raw signal only. The raw sensor millivolts (divider compensation is done in firmware) stay stored and shown as a system detail.

Estimated ug/m3 = max(0, sensor_mv - baseline_mv) * 1000 / sensitivity. It is never negative.

- Sensitivity: `sensitivity_mv_per_mg_m3` in `config/system.yaml`, 5000. This is Sharp's typical 0.5 V per 0.1 mg/m3. It is typical, unverified against the datasheet on this machine, and not a per-unit calibration.
- Baseline: the lowest fresh sensor voltage in the last `baseline_window_s` (24 hours, at most 7 days), kept as one minimum per minute. No estimate is shown, and the state is "establishing baseline", until an unbroken run of fresh records has lasted `baseline_min_s` (10 minutes).
- A dust error, a stale report, communication loss or a gap of more than `reading_gap_limit_s` between records clears the history. A monitor restart also starts again; the history is in memory only.
- A low outlier lowers the baseline, and raises later estimates, until it leaves the window.
- Word levels: `clean` up to 50, `raised` up to 150, `very high` above. These are project display defaults, not health standards and not official category names.
- Not-connected floor: `disconnected_below_mv` in `config/system.yaml`, default 100 mV (sensor side). Required: the file must contain it. It must be above 0 and at most 5500; other values are refused at load. A dust voltage below it, a 0 mV reading, or the board's `dust_input_at_zero` report all count as "no reading". After `sensor_error_timeout_s` (120 s) with no reading at or above the floor, the dust status is `not_connected` and the dust fault is on. Not yet checked on the bench.
- Limit: `upper_limit` and `hold_s` in `config/system.yaml`, off as shipped. The project supplies no dust limit. The demo uses 100 ug/m3 for 30 s as a demonstration value.

The old `--dust-baseline-mv` and `--dust-sensitivity` options are removed. The estimate is not size-selective PM2.5, an official index, or a medical verdict. Verify against a reference instrument if concentration matters. A retained value is never shown as a current estimate.

## Verification on Ubuntu and hardware

Use the existing approved Python 3.10.12 environment and pinned requirements. Run the existing full python -m pytest check from the project root. Compile for the ESP32-S3 with the installed ESP32 core 3.3.12, BSEC2 1.10.2610 and BME68x 1.3.40408; do not upgrade them for this change. The commands are in [firmware/README.md](../firmware/README.md).

Before flashing, inspect wiring and measure the divider. After flashing, check LED timing with an oscilloscope, accepted/rejected sample counts, and raw voltage stability. Check BME680 continues to report every three seconds. Test BME680 failure while dust continues, missing dust reports while BME680 continues, USB loss, and recovery. A failed dust sensor must not overwrite the last good BME680 reading and vice versa. Missing-data alerts clear on valid fresh input; the existing communication acknowledgment behavior is retained.

The dust fields appear in terminal JSON and in the local dashboard (`dashboard.py`). The dashboard shows the dust estimate with its word level and state, the raw dust voltage as a system detail, its status, and 24-hour trends of `dust_ugm3` and `dust_mv`. A stale dust report raises a Dust fault on the dashboard. A dust limit exists only when set in `config/system.yaml`. The dashboard was checked only with simulated dust records. Camera occupancy is a separate module (`occupancy.py`) and does not use dust data.

## Sources

- https://global.sharp/products/device/lineup/data/pdf/datasheet/gp2y1010au_e.pdf
- https://global.sharp/products/device/lineup/data/pdf/datasheet/gp2y1010au_appl_e.pdf
- https://docs.espressif.com/projects/arduino-esp32/en/latest/api/adc.html (API reference only; not an instruction to change core versions)

## Local verification results

### Windows, before the full run (historical)

245 host tests passed with the two YAML-dependent test modules excluded, including 11 new dust tests. All top-level Python files passed Python 3.10 syntax parsing. These supplemental checks used the available Windows Python 3.14 / pytest 9.1.1, not the approved deployment environment. No dependencies were installed or changed. The full suite could not collect because PyYAML is unavailable. Arduino CLI is unavailable here, so firmware compilation and hardware timing have not been verified. Publication was subsequently authorized by the user; this remains a draft pending deployment and hardware verification.

### Linux, 15 November 2026

The full suite ran in the pinned Ubuntu environment: Python 3.10.12, pytest 8.2.0, PyYAML 6.0.1. It reported 317 passed with exit code 0, including the 11 dust tests. The two YAML-dependent modules were included. `monitor.py --demo` and `dashboard.py --demo` ran together with simulated dust records. No firmware compilation, flashing, oscilloscope check or physical dust measurement took place in that run. Later on 15 November the sketch that includes `firmware/sharp_dust.h` compiled for the ESP32-S3. That is compilation only. See the [15 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-15.md).

### ESP32-S3 board, 17 November 2026, no sensor attached

The firmware was flashed to the ESP32-S3 with nothing wired to it. The dust task ran and sent a dust record every 3 s. With no dust sensor attached, GPIO4 read about 870 to 930 mV with almost no rejected samples. The monitor accepted these as fresh dust records. The most likely cause is the floating ADC pin.

Open point: a disconnected dust sensor cannot currently be told apart from a working one. Candidate fixes, not decided:

- A pull-down resistor on the dust input, so that a disconnected sensor reads near 0 mV.
- A firmware check that compares the signal with the sensor LED on and off.

The user will choose when wiring the sensor. No dust reading, LED pulse or oscilloscope check took place. See the [17 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-17.md).

### ESP32-S3 board, 25 November 2026, sensor wired

- Firmware `f1a9dee` (LED pulse HIGH): `tools/sensor_check.py` saw only `dust_input_at_zero` (41 in 120 s on the old firmware, 60 in 180 s on `f1a9dee`).
- Diagnostic sketch: pulse LOW gave a pulse mean of about 470 mV at GPIO5 (window means 446 to 528 mV). Pulse HIGH gave 0.8 to 1.8 mV. So GPIO4 drives sensor pin 3 directly and LOW turns the LED on.
- Firmware `49029f2` (`ROOM_DUST_LED_ACTIVE_LOW = true`): dust PASS. 60 of 60 records, 892.7 to 1135.0 mV sensor side, mean 1018.9 mV, 0 `dust_input_at_zero`. After the first record, 295 to 298 accepted samples and 2 to 5 rejected per record.
- The monitor on `49029f2` reached a current dust estimate after the 10-minute baseline (baseline 921.5 mV, about 4 µg/m³, "low").
- Not checked: the LED pulse timing on an oscilloscope, the GPIO4 voltage and current, and a real dust disconnect.

See the [25 November verification record](../reference_files/LINUX_VERIFICATION_2026-11-25.md).
