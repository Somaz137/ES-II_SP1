# Linux verification results - 8 November 2026

The user ran the checks and supplied their results in the project conversation.
The assistant reviewed the supplied results. The assistant did not independently rerun the checks.

| Check | Result |
|---|---|
| Required Python package versions | Setup diagnostic reported matching versions. |
| Python test suite | 301 tests collected. All displayed cases completed without reported failures. Final summary and exit code were not supplied. |
| Firmware JSON formatting test | User reported success. |
| Complete ESP32 firmware compilation | Arduino Verify succeeded for DOIT ESP32 DEVKIT V1. |
| Missing serial port | Monitor continued running and raised a communication alert. |
| Valid simulated readings | Monitor accepted readings and updated receipt times. |
| Paused simulated sender | Monitor retained previous measurements and raised a communication alert. |
| Communication recovery | Fresh readings resumed. Timeout cleared. Communication alert remained active as required. |
| Repeated simulated sensor errors | Communication stayed active. Sensor alert became active. Previous measurements were retained. |
| Sensor-error recovery | A valid reading cleared the sensor alert and diagnostic. |
| Simulated Bosch readiness changes | Status changed from warming_up/calibrating to warmup_complete/calibrated. |
| Stop command | User confirmed return to the terminal prompt during earlier checks. |

The runtime checks used a Linux virtual serial port.
They did not use a physical ESP32 or BME680.
Simulated calibrated status does not establish actual sensor calibration.

## Software versions

These values come from the user's setup output, installation messages, and compiler checks.
They are recorded for reproducibility.

| Component | Recorded version |
|---|---|
| Python | 3.10.12 |
| NumPy | 1.26.4 |
| opencv-python | 4.11.0.86 |
| pyserial | 3.5 |
| Flask | 3.0.3 |
| PyYAML | 6.0.1 |
| pytest | 8.2.0 |
| SQLite | 3.37.2 |
| g++ | 11.4.0 |
| Espressif ESP32 board package | 3.3.12 |
| Bosch BSEC2 | 1.10.2610 |
| Bosch BME68x Sensor library | 1.3.40408 |

The course requires Arduino IDE 2.3.10.
A separate check of the installed IDE version was not supplied in this session.
Firmware compilation succeeded with the recorded ESP32 board package and Bosch library versions.
This establishes compilation, not physical hardware operation.

## Remaining checks

- Upload firmware to the physical DOIT ESP32 DevKit V1.
- Check actual BME680 wiring, supply, sensor units, readings, and acquisition timing.
- Check physical USB disconnection, reconnection, and board reset behavior.
- Check actual gas readiness and sensor failure behavior.
- Check compilation rejects an incorrect chip target and an invalid supply setting.
- Check camera capture and implement the agreed occupancy and patient-rule behavior.

Manual communication acknowledgment is not available in the terminal interface.
The recovery check tested alert retention, not a user acknowledgment control.
Do not repeat completed checks without a change, failure, or specific unresolved concern.
