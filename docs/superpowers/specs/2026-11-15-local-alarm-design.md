# Local alarm design

Approved scope: the user decided on 15 November 2026 that the independent notification path is a local alarm on the ESP32: one LED and one 3-pin buzzer module. This step builds the host side and the testable source core of the firmware side. It extends the [dashboard data contract](2026-11-15-dashboard-data-contract-design.md). Verification is software-only: automated tests, a host C++ test and the simulator. Nothing here is verified on hardware.

## Goal and constraints

- The buzzer sounds for patient-limit alerts only.
- Communication, BME680 sensor and dust alerts light the LED silently.
- The dashboard has a "Silence alarm" button. Silencing stops the buzzer. The LED stays on. The silence is logged. A new limit alert sounds again.
- The three alert families (communication, sensor, patient-limit) stay separate. `status["limit_alerts"]` and the existing contract stay unchanged.
- The alarm path must never delay reading input, fault checks or status publication.
- No new dependencies. No patient limits outside the simulator and tests.

## Alarm level

One level with three values. A buzzer without the LED is impossible by construction.

| Level | Meaning | When |
|---|---|---|
| 0 | LED off, buzzer off | Otherwise. |
| 1 | LED on, buzzer off | No unsilenced limit alert, and either an active limit alert that was silenced, or an active communication, BME680 sensor or dust alert. |
| 2 | LED on, buzzer on | At least one active patient-limit alert that has not been silenced. |

The inputs are the published `limit_alerts` (through the session's breach records), `communication_alert_active`, `sensor_alert_active` and `dust.alert_active`. A patient profile load error does not light the LED. It is not one of the three alert families.

## Wire protocol

- Host to board: the line `ALARM,<0|1|2>\n`. After a failed or partial write the next command starts with an extra `\n`, so a fragment left on the line ends as a malformed command.
- Board to host: one JSON line `{"type":"alarm","state":<n>}` after the board applies a command.
- The board discards malformed commands, empty lines and lines longer than its buffer. It does not reply to them.
- The board starts at level 0 after a reset. The later firmware step should also print the reply line once at start-up, so the host sees the reset at once.

## Host parsing

`serial_parser.parse_serial_line` returns the new kind `alarm_state` with `alarm_level` for a record whose `state` is the integer 0, 1 or 2. Other `alarm` records are `ignored`. Booleans and strings are not levels.

`monitoring_state.process_serial_line` keeps the latest reply as `MonitoringState.alarm_reply` (`level`, `received_at`). The record is not a sensor reading. It does not refresh measurement freshness, gas readiness or dust, and it does not raise a sensor error.

**An alarm reply does not count as communication contact.** The host asks for a reply at every fault check. If replies counted, they would keep the communication alert clear while the firmware's measurement loop had stopped, and the BME680 reading would show as fresh with no sensor alert (`input_status` only becomes stale through a communication timeout or, with dust records, `bme_measurement_stale`). The alarm link has its own reachability state instead. Dust records still count as contact, as before: they are measurement data the board sends unasked.

## Alarm tracker (`alarm.py`)

`AlarmTracker` is pure. It has no I/O and no clock of its own. Times are monotonic host times passed in. It holds:

- the wanted level, the requested level (last command written) and the last confirmed level with its receipt time;
- a reachability state: `pending`, `confirmed` or `unreachable`, with a reason for `unreachable`: `not_connected`, `send_failed` or `no_confirmation`;
- the silence set and the time of the last applied silence.

Rules:

- A command is due when the wanted level differs from the requested level, after each fault check (a board reset is corrected within one fault-check interval), after a reconnect, and after a reply that does not match the requested level.
- No command is sent while the serial port is not connected. The state is then `unreachable` (`not_connected`).
- A failed send gives `unreachable` (`send_failed`). The next attempt is at the next fault check or the next change of the wanted level, so a stalled port costs at most one bounded write per fault check.
- A reply equal to the requested level gives `confirmed`. Another reply records the board's level and stays `pending`.
- If no matching reply arrives within `alarm_confirm_timeout_s` of the first unanswered command, the state is `unreachable` (`no_confirmation`). Resends do not restart this timer.
- While a resend of an already confirmed level waits for its reply, the state stays `confirmed`.

Events, once per transition, never once per check:

| Kind | When |
|---|---|
| `alarm_confirmed` | The state becomes `confirmed`. The message names the level, for example "Local alarm confirmed at level 2: LED on, buzzer on." |
| `alarm_unreachable` | The state becomes `unreachable`. The message names the reason. |
| `alarm_silenced` | A silence was applied. The message names the silenced conditions and states that the LED stays on. |

`pending` is transient and is not logged.

## Silence

- Each active limit alert has an id. It is assigned when the session first reports the alert, keyed by measurement, direction and alert start time. The id has a random per-process prefix, so a request stored by an earlier monitor run never matches.
- The published `silence_token` lists the ids of the unsilenced active alerts. It is null when there are none.
- `POST /silence` with field `token` follows the acknowledgment pattern. It is local-only and has the same Origin and `Sec-Fetch-Site` checks. It returns 409 with a short reason when the status is missing, overdue, has no alarm block, has no unsilenced limit alert, or the token does not match. Otherwise it stores the token as `alarm_silence` and redirects with 303.
- The monitor reads `alarm_silence` at each fault check, as it does `communication_ack`. It applies the silence only when the token equals the current token. Then it logs `alarm_silenced`. A stale or repeated token changes nothing and logs nothing. Latency is at most one fault-check interval.
- A silence covers exactly the alerts in the token. An alert on another measurement, or the same measurement alerting again after its alert ended, has a new id and sounds again.

## Serial transport send

`SerialTransport.send(line)` returns `True` when the whole line was written, otherwise `False` and records `last_send_error`. It never raises. It returns `False` at once when the port is not open. A send failure does not close the port; the next read detects a lost device as before.

pyserial 3.5 on Linux was checked against a pseudo-terminal whose output buffer was full:

- `write_timeout=0` loops without end inside `Serial.write`: `os.write` raises `EAGAIN`, pyserial ignores it and retries. It must not be used.
- `write_timeout=None` (the default) blocks until the buffer drains.
- A positive `write_timeout` returns the full count or raises `SerialTimeoutException` (an `OSError`) after the timeout. Bytes already written stay on the line.

`open_serial_port` therefore sets `write_timeout=0.02`. A send blocks the loop for at most about 20 ms, which is below the 50 ms poll interval. This is a transport constant, like the 4096-byte read limit, not a runtime setting. A short count or an exception counts as a failed send and sets the resynchronising `\n` prefix for the next command.

## Monitor wiring

The limit alerts are computed in `RoomSession.update`, inside the publisher. The alarm therefore runs there, after the limit and fault state is updated and before the status is stored:

1. Feed the latest `alarm_reply` from the monitoring state.
2. Compute the wanted level.
3. Send the command when the tracker says so, and record the result.
4. Add `status["alarm"]` and the alarm events.

`monitor.py` passes the reply and the transport to the session. Its `apply_controls` (run at each fault check) also applies a stored silence request and marks the resend. `monitoring_loop.py` is unchanged: reading input, fault checks and publication keep their schedule. An exception raised by a transport's `send()` is caught and reported as `unreachable` (`send_failed`), so it cannot stop the publication.

## Published state

`status["alarm"]`:

| Key | Content |
|---|---|
| `wanted_level` | 0, 1 or 2. |
| `requested_level` | Last level written to the port, or null. |
| `confirmed_level` | Last level the board reported, or null. |
| `state` | `pending`, `confirmed` or `unreachable`. |
| `reason` | Null, `not_connected`, `send_failed` or `no_confirmation`. |
| `silenced` | True when an active limit alert is silenced. |
| `silenced_at` | Wall time of the last applied silence while it still covers an active alert, otherwise null. |
| `silence_token` | Token for `POST /silence`, or null. |
| `confirmation_age_s` | Seconds since the last reply, or null. |
| `send_error` | The last send error text, or null. |

`/api/room` returns it inside `status` unchanged. `health` gains `alarm`: `state` (`unknown` when the status is overdue), `reported_state`, `wanted_level`, `confirmed_level`, `silenced` and `confirmation_age_s` (recalculated to server time).

## Timing setting

| Key | Default | Use |
|---|---|---|
| `alarm_confirm_timeout_s` | 2 | Wait for a matching board reply before the alarm shows as unreachable. |

It is optional in `config/runtime.yaml`, defined once in `RUNTIME_DEFAULTS`, and must be finite, positive and above `serial_poll_interval_s` (the reply is read at a later poll). `monitor.py --demo` uses the default without PyYAML.

## Simulator

`SimulatedTransport(alarm="echo")` accepts `send()` and returns the reply line at the next poll, so `monitor.py --demo` shows the whole loop. Tests also use `alarm="silent"` (accepts, never replies) and `alarm="fail"` (every send fails).

## Dashboard page

The smallest change. The alerts panel shows the alarm in words, for example "Local alarm · LED and buzzer on · confirmed by the board". A "Silence alarm" button appears only when the status is current and `silence_token` is not null. No styling changed.

## Firmware source core

`firmware/alarm_command.h` is pure C++11 with no Arduino dependency and no dynamic allocation:

- `AlarmLineReader` collects characters into a fixed 32-byte buffer. It reports a level, an invalid line or no complete line. Over-long lines are discarded up to the next newline. A trailing `\r` is accepted.
- `parseAlarmCommand` accepts exactly `ALARM,0`, `ALARM,1` or `ALARM,2`.
- `alarmOutputs` maps a level to LED and buzzer on/off.
- `formatAlarmReply` writes `{"type":"alarm","state":<n>}` into a caller buffer.

`firmware/tests/test_alarm_command.cpp` tests it with g++ on Linux.

**The sketch is not changed in this step.** The `.ino` sketch, the pin definitions and the board check stay as they are. The firmware port step, once the ESP32-S3 toolchain can compile the sketch, must:

1. Include `alarm_command.h`.
2. Read `Serial` without blocking in `loop()` and feed each byte to one `AlarmLineReader`.
3. Drive the alarm LED on GPIO6 and the buzzer module on GPIO7 from `alarmOutputs`, and set both to level 0 in `setup()`.
4. Check the buzzer module polarity (active high or active low) and whether it needs a tone or a steady level, and the LED wiring and series resistor, on the real board.
5. Print the reply line with `formatAlarmReply` after each applied command and once at start-up.
6. Confirm that reading `Serial` does not delay BSEC sampling, and that GPIO6 and GPIO7 are free on the chosen ESP32-S3 board.

## Open point

When the USB link is down the host cannot command the LED or buzzer. The dashboard then shows the alarm as unreachable. A firmware fallback, for example the board lighting its LED when it stops hearing from the host, is a possible later decision for the user. It is not implemented.
