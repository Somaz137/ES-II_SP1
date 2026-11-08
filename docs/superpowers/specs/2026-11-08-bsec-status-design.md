# BSEC status integration design

The user approved investigating a compatible Bosch BSEC integration instead of a fixed gas warm-up timer. Implement the independent Python status consumer now. Firmware installation, flashing and all runtime tests remain deferred.

## Contract

Recognized reading/error JSON may contain bsec with integer fields stabilization_status (0 or 1), run_in_status (0 or 1), and iaq_accuracy (0 through 3). Reject bools, floats, strings, missing fields and invalid values as unknown metadata. Preserve structural measurement classification independently: bad metadata must not turn a complete reading into a sensor error. Missing metadata from the legacy firmware stays unknown.

gas_readiness.py owns a frozen GasReadiness snapshot, parse_gas_readiness(data), gas_warmup_status(state) and gas_calibration_status(state). The parser result carries that snapshot. MonitoringState retains the snapshot from every recognized record, including an unknown snapshot when metadata is absent or unusable. Ignored input cannot change it.

Warm-up status is unknown without usable metadata, warming_up when either stabilization/run-in flag is zero, and warmup_complete when both are one. IAQ accuracy remains separate: 0 stabilizing, 1 calibration_required, 2 calibrating, 3 calibrated. These labels describe reported algorithm status, not measurement certification or room safety. No IAQ values, thresholds or availability policy are introduced.

current_gas_warmup_status(monitoring_state) reports unavailable when actual communication timed out or latest recognized input is not fresh. Otherwise it returns the reported warm-up status. An acknowledgment latch after communication recovery does not block this status. The raw snapshot remains available for historical context, but callers must not present it as live when unavailable. Caller must continue scheduled fault evaluation.

No elapsed-time readiness inference. No countdown, new timer or gas_warmup_s key. This supersedes the earlier planned timer/YAML warm-up approach. Fault YAML and both 120-second defaults remain unchanged.

## Firmware handoff and consequential choice

Current firmware remains the experimental Adafruit reader and sends no BSEC metadata. This Python change alone cannot activate BSEC.

Bosch BME680 datasheet Revision 1.9 describes LP gas updates every 3 seconds, while CONT 1 Hz is short-term/testing only. The user previously selected continuous 1-second acquisition. Ask once whether to adopt 3-second LP operation before replacing firmware. Do not relabel repeated values as fresh one-second acquisitions.

Bosch BSEC2 wrapper release 1.10.2610 (algorithm 2.6.1.0) was inspected as a candidate, not installed or approved as an exact dependency. Bosch-BME68x-Library is an additional firmware dependency. Exact ESP32/core/library combination and BME680 configuration remain to verify on Linux. Do not substitute Bosch README's IDE/core suggestions for the course-pinned Arduino IDE.

Future firmware must produce the four existing fields in existing units plus the bsec object from one corresponding output cycle. Use null/missing for unknown status rather than fabricating ready flags. Preserve error communication and avoid blocking the loop with sleeps. Pressure from BSEC is Pa and must convert to hPa. Gas readings remain provisional during warm-up. Do not copy example temperature offsets for a different board. State save/restore is supported by Bosch, but storage/wear/version behavior is not selected or implemented here.

## Evidence and non-goals

- Bosch status definitions: https://github.com/boschsensortec/Bosch-BSEC2-Library/blob/1.10.2610/src/inc/bsec_datatypes.h
- Bosch releases: https://github.com/boschsensortec/Bosch-BSEC2-Library/releases/tag/1.10.2610
- Bosch example: https://github.com/boschsensortec/Bosch-BSEC2-Library/blob/1.10.2610/examples/generic_examples/basic/basic.ino
- Bosch BME680 datasheet: https://www.bosch-sensortec.com/media/boschsensortec/downloads/datasheets/bst-bme680-ds001.pdf
- Adafruit BSEC guide: https://learn.adafruit.com/adafruit-bme680-humidity-temperature-barometic-pressure-voc-gas/bsec-air-quality-library

No firmware/library/core installation, compilation, flashing, runtime tests, scheduler, database, UI or environmental safety rule. VIGIL has no equivalent gas readiness mechanism.
