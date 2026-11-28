# Serial runtime design

The user authorized continuation from BSEC firmware to laptop serial monitoring. Preserve the agreed behavior. This is a terminal integration, not a complete room-safety application.

## Responsibilities

| File | Responsibility |
|---|---|
| monitor.py | Thin CLI; explicitly selected port, startup settings, JSON publisher |
| settings.py | Runtime YAML loading and validation |
| serial_transport.py | Nonblocking bounded reads, newline framing, reconnect attempts |
| monitoring_loop.py | Host monotonic timing, real parser/router, periodic faults |
| status_output.py | Retained measurement, age, estimated UTC, current gas/alert facts |

Existing fault, parser, retention and gas modules are unchanged. No new dependency or version. Startup reads config/alerts.yaml and config/runtime.yaml once. Both alert durations remain 120 seconds. Host fault checks default to five seconds; transport retry five seconds and polling 0.05 seconds are implementation settings, not additional fault durations or BME680 sampling controls.

## Transport and scheduling

Open only the explicit port at 115200 baud by default. No auto-selection, firmware configuration commands or sensor warm-up sleeps. Pyserial timeout=0 gives nonblocking reads. Each poll reads at most 4096 bytes. Accumulate partial records across polls; decode only complete newline-delimited records. Discard an oversized record through its next newline. Discard invalid UTF-8 records. Neither kind resets communication. Reset framing when a connection is lost so old and new fragments cannot combine.

Open/read OSError (including pyserial SerialException) closes transport and schedules a retry. A successful reopen only reports transport connectivity; recognized packets establish ESP communication. No restart of MonitoringState or timestamps on retry. Changed Linux device names require explicit restart with the correct port; a stable /dev/serial/by-id path can be selected when verified by the user. Do not guess a device or change permissions automatically.

Use time.monotonic throughout fault and receipt logic. Periodic checks continue with no port or no messages. Schedule from startup, skip missed ticks, and never replay old timestamps after a delay. Existing router evaluation may also detect an elapsed fault on a message; five seconds is the periodic check interval, not a ban on event-driven evaluation. OS delays, opening a port, and slow output consumers can delay checks; no real-time guarantee. Polling sleeps avoid a busy loop. Close transport on exit, including KeyboardInterrupt and unexpected errors.

Opening some ESP32 ports can reset the board. Reconnection therefore does not promise BSEC continuity. Physical readiness must still come from the firmware's reports.

## Output and boundaries

Publish JSON startup and changed snapshots, including scheduled updates. This terminal stream is not a ten-second dashboard. Preserve last valid reading/time and show measurement age, input status, actual timeout, both alert flags, transport error, and gas statuses. UTC receipt time is an explicitly labeled estimate derived from a single startup UTC/monotonic anchor. Wall-clock corrections do not change fault timing. These are host receipt times, not ESP acquisition times; previously buffered records cannot be proven newly acquired by this protocol.

Mask both gas calibration and warm-up as unavailable when communication times out or latest input is not fresh. No raw resistance conversion, safety verdict, IAQ thresholds or fixed gas readiness timer. A port being open does not mean a working sensor.

No acknowledgment CLI/UI is introduced in this step. The existing pure acknowledgment API remains; terminal communication alerts stay latched for the process lifetime unless a future integrated controller invokes it. Restart is not recorded as acknowledgment; persistence and control remain future work. No database, notifications, camera, patient profiles, web process, services, remote exposure, firmware build/flash or library installation.

## VIGIL comparison

VIGIL coordinates camera processing in monitor.py with a separate dashboard. This project uses the same conceptual separation, but USB framing/reconnect is new. No VIGIL source is copied. Its database-backed acknowledgments and history are not provided by this terminal milestone.

## Verification

Write hardware-free tests with real router/fault modules, fake time and fake serial endpoints. Cover framing, invalid UTF-8, oversized records, retry boundaries, connection recovery, retained values, silence, noise, active sensor errors, delayed ticks, unavailable gas metadata, and cleanup. Runtime YAML tests use real files. Do not run tests or application imports in this session; the user deferred them to their Linux setup. Syntax parsing is not runtime verification.

API reference: https://pyserial.readthedocs.io/en/stable/pyserial_api.html (nonblocking timeout=0, bounded read, SerialException). Continue using the existing pyserial==3.5 pin.
