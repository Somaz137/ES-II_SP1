# Dashboard data contract design

Approved scope: the user requested this backend step on 15 November 2026, before the dashboard redesign. It extends the [room software design](2026-11-15-room-software-design.md). Verification is software-only: automated tests and the simulator.

## Goal and constraints

- Give the later dashboard every value it needs in one `GET /api/room` response.
- State the condition and its duration in limit alerts and events, as the course brief requires.
- Move the remaining timing constants into `config/runtime.yaml`.
- Keep 7 days of raw readings. Never prune events.
- Fix four known defects, each with a failing test first.
- No new dependencies. No change to fault trackers, the serial parser, measurement validation or gas readiness.
- The sustained-breach rule stays as built. Retained readings are never presented as current.

## Structured limit state (status record)

`RoomSession.update` publishes three keys. Durations use the monotonic clock. Wall-clock times (UTC epoch seconds) are for display only.

| Key | Content |
|---|---|
| `limit_alerts` | Active alerts. Each: `metric`, `name`, `unit`, `direction` (`low` or `high`), `limit`, `value`, `breach_started_at`, `alert_started_at`, `elapsed_s`. Empty list when no alert is active. |
| `limit_pending` | Breaches that have not yet lasted the sustained duration. Each: `metric`, `name`, `unit`, `direction`, `limit`, `value`, `breach_started_at`, `elapsed_s`, `hold_s`, `remaining_s`. |
| `limit_monitoring` | `state` (`running`, `paused` or `off`), `reason` (null when running normally) and `message`. |

`elapsed_s` is `now` minus the breach start. `remaining_s` is `hold_s` minus `elapsed_s`, never below zero. The alert itself still starts only on a reading receipt, as before.

Reasons, checked in this order:

| Reason | State | Meaning |
|---|---|---|
| `profile_invalid` | `off` | The profile file is invalid and no valid profile was loaded. |
| `no_profile` | `off` | No patient profile exists. |
| `no_limits` | `off` | The profile enables no measurement. |
| `reading_not_current` | `paused` | The BME680 reading is not fresh or is older than the reading-gap limit. |
| `occupancy_unknown` | `paused` | Occupancy is not `occupied`. |
| `profile_invalid` | `running` | The profile file is invalid. Monitoring continues on the last valid profile. |

## Events

Events carry `id`, `at`, `kind` and `message`. Limit messages state the measurement, direction, configured limit and value. End messages also state how long the alert lasted.

| Kind | When |
|---|---|
| `limit_alert` | A breach lasted the sustained duration. |
| `limit_ended` | A reading returned within the limits. |
| `limit_reversed` | A reading crossed to the opposite limit. A new breach timer starts. |
| `limit_reset_profile` | The patient profile changed while the alert was active. |
| `limit_reset_occupancy` | Occupancy became unknown while the alert was active. |
| `limit_reset_reading` | Readings stopped being current, or the gap between readings exceeded the limit. |
| `communication_acknowledged` | A person acknowledged the communication alert on the dashboard. Logged with `fault_ended`. |
| `fault`, `fault_ended` | Unchanged. |

Example: "Temperature above the configured limit of 27 °C for 9 s. Value 31 °C."

## Dashboard response

`GET /api/room` returns:

| Key | Content |
|---|---|
| `status` | The latest monitor record, or null. |
| `profile`, `profile_error` | The patient profile as loaded by the dashboard, or null, and the load error, or null. |
| `trends` | One entry per stored series: `name`, `unit`, `limit_checked`, `buckets`. Each bucket: `at` (minute start), `avg`, `min`, `max`. Past 24 hours, ordered by time. |
| `events`, `events_has_more` | Newest first. `events_before=<id>` returns older events. `limit` defaults to 50; the maximum is 200. Values that are not positive integers return 400. A larger `limit` is reduced to 200. Paging uses two queries: the page, and one row older than it for `events_has_more`. |
| `health` | Derived from the status. See below. |
| `timing` | Effective timing settings published by the monitor, or the defaults when no status exists. |
| `now` | Server time. |

Stored series: `temp_c`, `humidity_pct`, `pressure_hpa`, `gas_ohms`, `dust_mv`. Gas resistance is stored and charted only. It is a raw signal and has no patient limit. (Since the [air quality and dust design](2026-11-15-air-quality-dust-label-design.md) of 15 November 2026, `air_quality` and `dust_ugm3` are also stored, and each trend entry has `estimate`. The raw series stay as system details.) The `?metric=` parameter is removed.

`health` has `monitor`, `serial`, `bme680`, `dust`, `occupancy` and `profile`. Each component has `state`, `reported_state` and its facts. `reported_state` is the last published value. `state` is `unknown` when the status is overdue, so a retained value never shows as current. Ages are recalculated to the server time, so a retained value always shows its true age. `monitor.state` is `waiting`, `current` or `overdue`. `occupancy.source` is `camera`, `simulated` or `none`; `none` means no camera is configured. The monitor publishes it as `occupancy_source`, with `occupancy_observation_age_s`.

## Timing settings

New optional keys in `config/runtime.yaml`. Defaults are defined once, in `settings.RUNTIME_DEFAULTS`. `settings.py` imports PyYAML only inside the loaders, so `monitor.py --demo` uses the same defaults without PyYAML.

| Key | Default | Use |
|---|---|---|
| `reading_gap_limit_s` | 6 | Reading age and gap that restart sustained timers. |
| `status_stale_after_s` | 15 | Status age shown as overdue. Also limits acknowledgment. |
| `dashboard_refresh_s` | 10 | Page refresh interval. |
| `camera_interval_s` | 60 | Camera check interval. Observations expire 5 seconds after it. |
| `readings_retention_days` | 7 | Raw reading retention. |

Values are finite positive numbers. Booleans and numeric strings are rejected. Rejected combinations:

- `status_stale_after_s` not above `fault_check_interval_s` plus `serial_poll_interval_s`. An idle monitor publishes once per fault check, up to one poll interval late. A shorter limit marks a working monitor overdue between publishes.
- `dashboard_refresh_s` above `status_stale_after_s`. The page would show a status as current for longer than the staleness limit.
- `readings_retention_days` below 1. The 24-hour trend would lose data.

The monitor publishes the effective values as `status["timing"]`, with `fault_check_interval_s`. The dashboard reads them from the status. It has no settings copy.

## Retention

`RoomSession` prunes readings older than `readings_retention_days` on its first update and then once per hour of monotonic time. Each prune deletes at most 5000 rows in its own transaction. A full batch schedules the next prune on the next update. An index on `readings(at)` keeps each prune and the trend query short. The dashboard never prunes. Events are never pruned.

## Defects fixed

1. A missing profile file falls back to the legacy stored profile only after validation.
2. The profile form names the field in each error, keeps the typed values and returns 400.
3. Acknowledgment against an incomplete stored status returns 409, not 500.
4. Dashboard routes and the API shape have tests.

## Page changes

The first-draft page reads the new response with the smallest changes. The trend selector redraws from the last response. Alerts read as "Temperature above 27 °C for 2 min 10 s · now 31 °C". Pending breaches show with the prefix "Pending". The page shows the limit-monitoring message. Refresh and staleness come from `timing`. No styling changed.
