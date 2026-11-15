# Room software design (as built)

**Written after implementation on 15 November 2026.** This record describes the code on branch `feature/sharp-dust-integration` at commit 5e2de1b. It was not an approved design before the code was written. The code is the authority. Where this record and the code differ, the code is correct and this record needs a correction.

Everything described here is verified only in software: automated tests and the simulator. No physical ESP32, BME680, dust sensor or camera was used. Nothing here establishes clinical safety or calibrated air quality.

## Responsibilities

| File | Responsibility |
|---|---|
| room_store.py | SQLite status, readings and events. Patient profile file beside the database. Profile validation. |
| room_session.py | Per-metric patient limits, sustained-breach timing, occupancy gating, live profile reload, event logging. |
| occupancy.py | OpenCV HOG person check on a background thread. |
| simulated_input.py | Hardware-free serial records for the demo. |
| monitor.py | Connects the transport, monitoring loop, session, camera and acknowledgment requests. |
| dashboard.py, templates/room.html, static/room.js, static/room.css | Local Flask dashboard. Reads SQLite. Writes the profile file and acknowledgment requests only. |

The monitor owns all sensor input and all alert decisions. The dashboard owns no sensor input. Closing the dashboard does not stop monitoring. This follows the VIGIL monitor/dashboard separation. No VIGIL source is copied.

## Storage

`RoomStore(path)` opens one SQLite file and sets WAL journal mode. The default file is `room.sqlite3` in the project root. Demo mode uses `room-demo.sqlite3`. Both programs accept `--db` and must use the same path. The `.gitignore` excludes the database files and both default profile files.

| Table | Columns | Use |
|---|---|---|
| settings | key TEXT PRIMARY KEY, value TEXT (JSON) | `status`: the latest monitor record. `communication_ack`: the latest acknowledgment request. `profile`: legacy profile location from the first draft. |
| readings | metric, at, value; primary key (metric, at) | `temp_c`, `humidity_pct`, `pressure_hpa` and `dust_mv` samples. `at` is UTC epoch seconds. Duplicate keys are ignored. |
| events | id, at, kind, message | `limit_alert`, `limit_ended`, `fault`, `fault_ended`. |

`publish()` writes the status, new samples and new events in one transaction. `history(metric, now)` returns one-minute averages for the past 24 hours. `events()` returns the latest 50 events, newest first.

Gas resistance is stored only inside the status record. It has no trend and no limit.

No pruning exists. The readings and events tables grow without limit. The 24-hour chart is a query window, not a retention rule.

## Patient profile

The profile file is the database path with the suffix `.profile.yaml`, for example `room.profile.yaml`. Format:

```yaml
limits:
  temp_c: [low, high]
hold_s: seconds
```

Validation (`validate_profile`):

- The root is a mapping with exactly the keys `limits` and `hold_s`.
- `limits` is a mapping. Its keys are a subset of `temp_c`, `humidity_pct` and `pressure_hpa`. An empty mapping is valid and disables all patient-limit checks.
- Each value is a list of two finite numbers (int or float, not bool), with low strictly less than high.
- `hold_s` is a finite positive number. It applies to every metric.

Loading tries JSON first, then PyYAML `safe_load`. Saving validates first, then writes YAML (or JSON if PyYAML is absent) to a temporary file in the same folder and replaces the profile file. If the profile file does not exist, the store returns the legacy `profile` settings value. That legacy value is not validated.

No limits ship with the project. In demo mode only, the monitor writes the example profile `temp_c: [20, 27]`, `hold_s: 9` when no profile exists. These values exist only to exercise the simulator. They are not patient limits.

## Sustained-breach rule

`RoomSession.update(status, now, wall, occupancy)` runs on every monitor publish. `now` is the monotonic clock; `wall` is UTC time.

1. Reload the profile file. On a read or validation error, keep the last valid profile in memory and set `profile_error`.
2. If the loaded profile differs from the previous one, clear all breach timers.
3. The reading counts as current only when `input_status` is `fresh` and the last BME680 receipt is at most 6 seconds old.
4. If the reading is not current, occupancy is not `occupied`, or no profile exists, clear all breach timers.
5. Otherwise, for each new BME680 reading and each enabled metric: a value below low is `low`; above high is `high`; inside the limits (inclusive) clears that metric's timer. A breach timer starts at the receipt time of the first reading in the breach. It restarts when the direction changes or when more than 6 seconds passed since the previous BME680 reading.
6. An alert is active when the breach has lasted at least `hold_s`, measured between reading receipt times.

Consequences:

- An alert can start only when a reading arrives, so the actual delay rounds up to the next three-second reading.
- A single in-range reading ends the alert. There is no cooldown or hysteresis.
- A profile change, unknown occupancy or a stale reading clears an active alert and logs `limit_ended`. The alert starts again only after a full new `hold_s`.

Events are logged on transitions only: `limit_alert` with text such as "Temperature remained high." and `limit_ended` with text such as "Temperature high alert ended." Fault transitions log `fault` and `fault_ended` for Communication, BME680, Dust and Patient profile. The text names the measurement and direction. It does not state the limit, value or duration.

Fault alerts do not depend on occupancy. Patient-limit alerts do.

## Occupancy

`CameraOccupancy(index)` runs a daemon thread. Every 60 seconds it opens the camera, reads one frame, releases the camera and runs OpenCV's default HOG people detector (`winStride (8, 8)`, `scale 1.05`). Frames smaller than 128 x 64 are not checked.

- One or more detections: `occupied`.
- No detection, failed capture or an OpenCV error: `unknown`.
- An observation older than 65 seconds: `unknown`.

There is no `absent` state. Frames stay in memory and are never saved or sent.

Without `--camera` in serial mode, occupancy is always `unknown`, so patient-limit alerts never start. Demo mode always reports `occupied`. `--camera` is rejected in demo mode.

The HOG detector is trained on upright pedestrians. It can miss seated, lying or occluded people. Unknown occupancy suppresses patient-limit alerts. The detector has not been checked with a camera.

## Simulator

`monitor.py --demo` replaces the serial transport with `SimulatedTransport` and uses fixed settings: both fault timeouts 120 seconds, fault checks 5 seconds, polling 0.05 seconds. The YAML settings files are not read.

Every 3 seconds the simulator emits one BME680 reading and one dust record. Humidity is 48 %, pressure 1008 hPa, gas resistance 12000 ohms. Dust voltage is `920 + round(elapsed) % 180` mV. Temperature follows a 90-second cycle: 24 °C before 18 s, 31 °C from 18 s until 60 s, then 24 °C. With the example profile, the alert starts at 27 s and ends at 60 s. Readings carry no BSEC metadata, so gas status shows unknown.

## Dashboard routes

`dashboard.py` serves Flask on 127.0.0.1, port 5000 by default.

| Route | Action |
|---|---|
| GET / | Page with live values, 24-hour trend, alerts, recent events and the limits form. |
| GET /api/room?metric= | Status, latest 50 events, trend for one metric (`temp_c`, `humidity_pct`, `pressure_hpa` or `dust_mv`) and server time. Other metrics return 404. |
| POST /profile | Converts form fields to a profile and saves it. A metric with both fields blank is disabled. Invalid input returns 400 with the page. A write failure returns 503. Success redirects (303). |
| POST /acknowledge | Writes a communication acknowledgment request. See below. |

Local-only checks run before every request:

- The Host header must be `localhost` or `127.0.0.1`, with any port. Other hosts get 403. This guards against DNS rebinding. IPv6 `[::1]` is rejected.
- For POST, `Sec-Fetch-Site: cross-site` gets 403. A present Origin header that differs from the request host URL gets 403. A POST with neither header is accepted.

There is no login, no CSRF token and no remote access.

The page script refreshes every 10 seconds. A status older than 15 seconds is shown as overdue. Alerts then show as unavailable and occupancy as unknown. The trend draws minute averages and breaks the line at gaps longer than 120 seconds.

## Acknowledgment handshake

The communication alert remains latched after contact recovers, as before. The dashboard now provides the acknowledgment control.

1. When the communication alert becomes active, the monitor creates a random token and publishes it as `communication_alert_id`. The token stays the same while that alert remains active.
2. The page shows "Acknowledge communication recovery" only when the status is current, a token exists and communication is not timed out.
3. POST /acknowledge accepts the token only when it equals the stored token, communication is not timed out and the status is at most 15 seconds old. Otherwise it returns 409. On success it stores the token as `communication_ack`.
4. On each periodic fault check, the monitor reads `communication_ack`. If it changed, equals the current token, the alert is active and communication is not timed out, the monitor calls `acknowledge_monitoring_communication`.
5. The alert clears. The session logs `fault_ended` "Communication alert cleared."

The dashboard cannot acknowledge during an outage. No separate acknowledgment event exists; the event history shows only the cleared fault. The acknowledgment takes effect within one fault-check interval.

## Constants in code

These values are not YAML settings:

| Value | Location |
|---|---|
| 6-second BME680 reading-gap limit | room_session.py |
| 60-second camera interval; 65-second observation expiry | occupancy.py |
| 15-second dashboard staleness limit | static/room.js and dashboard.py |
| 10-second dashboard refresh | static/room.js |
| 50 latest events; 24-hour window; one-minute averages | room_store.py |

## Known limitations

- Verified only in simulation and automated tests. No hardware or camera check.
- The HOG detector can miss seated, lying or occluded people. Unknown occupancy suppresses patient-limit alerts.
- No database pruning. The event query returns the latest 50.
- Alert text does not state the limit, value or duration.
- Caregiver alerts stay inside the dashboard. No independent notification path exists.
- The legacy profile fallback is not validated.
- The constants above are not configurable.
- Dust voltage and gas resistance have no patient limits.

## Decided after implementation, not implemented

On 15 November 2026 the user decided: an ESP32-S3 (N8R2 module) board in place of the DOIT ESP32 DevKit V1, a local ESP32 buzzer and LED alarm with a dashboard "Silence alarm" control, 7-day retention of raw readings, and a dashboard redesign. The host software described here does not depend on the board model. Decided ESP32-S3 pins: I2C SDA GPIO8, I2C SCL GPIO9, dust analog input GPIO4, dust LED drive GPIO5, alarm LED GPIO6, and buzzer module GPIO7. The firmware still targets the classic ESP32 and does not use these pins. See the [implementation plan](../../../reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md). None of this exists in the code described above.
