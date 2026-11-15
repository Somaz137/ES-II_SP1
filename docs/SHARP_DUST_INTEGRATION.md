# Sharp GP2Y1010AU0F integration

## Plan and implementation status

1. Confirm sensor: user supplied a photo of a bare six-pin sensor with cable, resistor and capacitor.
2. Add experimental ESP32 acquisition in firmware/sharp_dust.h; initialize before BME680 and report independently every three seconds. Implemented.
3. Route separate dust/dust_error records without overwriting BME680 readings or readiness. Implemented in dust.py and monitoring_state.py.
4. Expose retained voltage, age, status and separate timeout in status_output.py. Dust uses the existing configured sensor timeout (120 seconds by default). BME680 silence while dust messages arrive is also exposed. Implemented.
5. Add optional explicit calibration in monitor.py. Default concentration is null. Implemented.
6. Verify host behavior and document hardware checks. Host subset checked; full pinned Ubuntu suite, ESP32 compilation, oscilloscope timing and physical calibration are pending.

## Wiring design: DOIT ESP32 DevKit V1

Verify connector numbering against Sharp's drawing. Cable colours are not a pinout.
Do not connect the sensor's analog output or LED pin directly to ESP32 GPIO.

| Sensor pin | Connection |
|---|---|
| 1 V-LED | 5 V through 150 ohm resistor; 220 uF capacitor positive to pin 1, negative to pin 2 |
| 2 LED-GND | Common ground |
| 3 LED | NPN collector; emitter to common ground; GPIO25 through 1 kohm to base; 10 kohm base-to-emitter pull-down |
| 4 S-GND | Common ground |
| 5 Vo | 10 kohm to GPIO34 node; another 10 kohm from node to ground (2:1 divider) |
| 6 Vcc | Regulated 5 V |

Use an NPN rated to sink at least 20 mA, e.g. a suitable 2N3904; check the actual transistor pinout. This is an external low-side LED driver: GPIO HIGH enables the LED. Keep the existing BME680 supply at 3.3 V and I2C GPIO21/22.

Check that the supplied resistor is 150 ohm and capacitor is 220 uF, rated at least 10 V. Additional parts: three 10 kohm resistors, one 1 kohm resistor and one NPN transistor. Keep wiring short. Confirm ADC voltage with a meter before attaching GPIO34; the divider produces half the sensor voltage. All grounds must be common. Do not join independent 5 V sources together.

## Acquisition and limitations

Sharp specifies a 10 ms cycle, a 0.32 ms LED pulse and sampling 0.28 ms after LED turn-on. A FreeRTOS task performs acquisition; the main loop alone writes serial output. No added third-party library is required. Existing dependency pins are unchanged.

This firmware is experimental. Arduino ADC call latency and task preemption can violate the pulse window. Detected overruns are discarded; fewer than 100 accepted samples per report or more rejected than accepted samples produces dust_error. The software timestamps do not prove the actual ADC aperture. Verify waveform and ADC sampling on the installed ESP32 core before accepting readings. If the ADC cannot meet the timing, acquisition needs a hardware-timed redesign, not relaxed limits.

The sensor has no digital identity or self-test. A plausible analog voltage cannot prove it is connected or healthy. A disconnected or failed sensor can look plausible. The host detects missing/invalid reports, not every physical fault.

## Calibration

Run the existing monitor normally for raw sensor millivolts (divider compensation is done in firmware). Concentration stays null until both --dust-baseline-mv and --dust-sensitivity are supplied. Baseline is the measured clean-air sensor-side voltage. Sensitivity units are mV per mg/m3; Sharp's typical 0.5 V per 0.1 mg/m3 corresponds to 5000, but is not a per-unit calibration guarantee.

Estimated ug/m3 = max(0, sensor_mv - baseline_mv) * 1000 / sensitivity.

Do not automatically zero the sensor at startup in an unknown room. Verify against a reference instrument if concentration matters. The output is estimated dust concentration, not size-selective PM2.5, AQI, or a medical safe/unsafe verdict. No dust health threshold has been invented. Stale retained values remain labelled stale even when a concentration is shown.

## Verification on Ubuntu and hardware

Use the existing approved Python 3.10.12 environment and pinned requirements. Run the existing full python -m pytest check from the project root. Compile with the already installed DOIT board core, BSEC2 1.10.2610 and BME68x 1.3.40408; do not upgrade them for this change.

Before flashing, inspect wiring and measure the divider. After flashing, check LED timing with an oscilloscope, accepted/rejected sample counts, and raw voltage stability. Check BME680 continues to report every three seconds. Test BME680 failure while dust continues, missing dust reports while BME680 continues, USB loss, and recovery. A failed dust sensor must not overwrite the last good BME680 reading and vice versa. Missing-data alerts clear on valid fresh input; the existing communication acknowledgment behavior is retained.

There is no dashboard in the current repository. These fields are available in terminal JSON for its later implementation. Camera processing is unchanged.

## Sources

- https://global.sharp/products/device/lineup/data/pdf/datasheet/gp2y1010au_e.pdf
- https://global.sharp/products/device/lineup/data/pdf/datasheet/gp2y1010au_appl_e.pdf
- https://docs.espressif.com/projects/arduino-esp32/en/latest/api/adc.html (API reference only; not an instruction to change core versions)

## Local verification result

245 host tests passed with the two YAML-dependent test modules excluded, including 11 new dust tests. All top-level Python files passed Python 3.10 syntax parsing. These supplemental checks used the available Windows Python 3.14 / pytest 9.1.1, not the approved deployment environment. No dependencies were installed or changed. The full suite could not collect because PyYAML is unavailable. Arduino CLI is unavailable here, so firmware compilation and hardware timing have not been verified. Publication was subsequently authorized by the user; this remains a draft pending deployment and hardware verification.
