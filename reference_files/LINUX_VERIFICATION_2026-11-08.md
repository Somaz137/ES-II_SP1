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
