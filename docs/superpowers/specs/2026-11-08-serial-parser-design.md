# Serial parser and measurement validation design

Approved scope: learner selected "implement this" on 8 November 2026 after the parser implementation checkpoint. Test execution remains deferred to Linux.

## Required behavior

- Current prototype: one room, one BME680, one camera; ESP32 sends decoded JSON lines to the laptop through the existing serial approach.
- Use the experimental firmware's type=reading fields: temp_c, humidity_pct, pressure_hpa and gas_ohms.
- A valid reading requires all four fields to be finite int/float values. Reject booleans, numeric strings, missing and other unusable values. Do not invent patient or physical-range thresholds here.
- Classify a recognized reading with unusable/missing measurements as incomplete_reading. The future consumer preserves the last committed values and original timestamp, indicates incomplete current input immediately, and starts/continues sensor-error timing without resetting it.
- Classify type=error as sensor_error. Both error and incomplete records are recognizable communication; integration will update communication timing separately.
- Ignore decoder failures, non-object JSON and unknown/missing record types. Ignored input must not reset communication time, update committed readings or directly change sensor-error state; periodic fault checks continue.
- Only valid_reading results carry committable measurements. Never supply a partial replacement dictionary for invalid input.
- Keep parsing and validation separate. No serial I/O, tracker mutation, measurement storage, hardware or scheduling in these modules.

## Interfaces and implementation details

- measurements.validate_measurements(data: object) -> None: raise ValueError naming missing/invalid fields; expose MEASUREMENT_FIELDS as the shared schema.
- serial_parser.parse_serial_line(line: str) -> ParsedSerialMessage: accepts decoded text and returns kind, optional measurements and optional diagnostic message.
- Kinds: valid_reading, sensor_error, incomplete_reading, ignored.
- A fresh valid result contains just the four expected measurement fields; extra metadata is not committed.
- An error record remains recognized even with absent/unusable diagnostic text, using a generic message.
- Match the existing starter's standard json.loads approach. If that decoder accepts NaN/Infinity or numeric overflow, measurement validation still rejects nonfinite reading fields as incomplete. Non-object results are ignored.
- Non-text arguments indicate caller misuse and raise TypeError rather than being silently stringified.
- Classifying a line does not decide patient safety, clear communication acknowledgments, update the last valid arrival time or implement a display.

## VIGIL comparison and learning preference

VIGIL has no BME680 serial parser. Its pose_engine.py extracts a common representation before posture.py applies decision rules; this separation is the reference pattern, not copied protocol behavior. Unusable camera input preserves previous state rather than inventing a fresh successful observation.

After each checkpoint answer, explain verified corresponding VIGIL behavior; explicitly identify situations with no direct equivalent.

## Tests and remaining integration

Write tests before the modules but do not execute them on Windows. Use real JSON strings and literal expected output, including whitespace, metadata, errors, incomplete fields, invalid measurements, overflow, garbled/unrecognized/non-object input and programmer input errors.

Preservation of committed measurements and routing into the two existing trackers is the next separate step; a stateless parser alone does not implement that state. Actual clock/polling, serial reconnect/framing, history and UI remain open. Firmware library/core approvals and hardware verification are unchanged.

