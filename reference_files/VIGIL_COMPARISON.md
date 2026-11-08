# VIGIL and Room Environment Safety Control

Updated: 8 November 2026.

## Evidence

The original VIGIL source was inspected directly in the learner-provided local folder `vigil_v0.8/vigil`. Core sources examined: config.yaml (excluding secret values), README.md, requirements.txt, calibrate_bed.py, pose_engine.py, posture.py, alarm.py, db.py, monitor.py, server.py, templates/dashboard.html, systemd service units, and test_safety.py. solutions/ex5_notify.py was read; the other exercise/manual-generator files were inventoried by their definitions and descriptions, not fully audited.

This replaces the earlier manual-only comparison and the previous inability to read the ZIP source. The original Module 3.4 PDF pp. 3-7 and 9-17 was also read. Inspection was static: eight core Python files parsed successfully using the available Windows interpreter; the 18 defined tests were counted but not executed. No camera, service, tunnel, notification transport or installation was started. Original VIGIL files were not modified.

Current project name: **Room Environment Safety Control**. The original course title and SAFE-ROOM codename are historical source facts. A name change does not itself select environmental actuators.

## How VIGIL works

1. Calibration maps four clicked mattress corners to normalized bed coordinates and saves bed_zone.json.
2. monitor.py loads config.yaml once, initializes SQLite, calibration, classifier, alarm manager, optional Jetson GPIO, MediaPipe and camera.
3. Camera defaults are 640x480 at a requested 30 fps, processing every third captured frame. Actual throughput is hardware-dependent.
4. pose_engine.py wraps MediaPipe and produces a PoseResult. The decision pipeline relies on shoulders and hips; no MediaPipe import is needed until its engine is constructed.
5. posture.py first handles no person / insufficient visibility, then checks fall, outside bed, sitting, edge risk, and finally safe. Occlusion does not overwrite the alarm manager's committed state.
6. alarm.py commits a state after eight consecutive classifications, emits alarms on qualifying transitions, applies per-type cooldown checks and duration-based escalation, and queues events for monitor.py. NO_PERSON escalates after 120 seconds; unchanged safe posture prompts repositioning after 7200 seconds.
7. monitor.py records committed state changes, alarms, optional skeleton snapshots and health heartbeats. Returning to SAFE_IN_BED clears open alarm conditions in SQLite.
8. server.py independently serves Flask APIs and dashboard HTML. It reads state/health/history, and writes acknowledgment fields. The browser polls status every 2 seconds, alarms/log every 10 seconds and the 24-hour summary every 60 seconds.
9. systemd can supervise monitor/web/tunnel separately. Cloudflare is a separate remote-access process, not a requirement for local monitoring.

## Decisions compared

| Area | Actual VIGIL source | Our confirmed requirements/decisions |
|---|---|---|
| Purpose | Bed posture, bed-exit and fall monitoring | Occupied-room environmental monitoring with patient-specific limits |
| Hardware | Jetson camera/GPIO; optional CSI pipeline | Ubuntu laptop + ESP32/BME680 and webcam; Windows development currently |
| Configuration | Central config.yaml; loaded at startup/import, no application live-reload path found | Dedicated YAML fault timeouts, 120 seconds each, loaded at startup; patient-profile updates during monitoring are a separate selected future feature |
| Alarm filtering | Eight-frame debounce; 60-second suppression check on qualifying transitions; CRITICAL configured types bypass suppression | Time-based communication and sensor-error tracking, each 120 seconds; environmental breach duration still undecided |
| Communication | Health heartbeat normally every 15 seconds. /api/status marks stale at three heartbeat intervals (45 seconds by default); /healthz uses a separate hardcoded 60-second cutoff | Recognized ESP32 reading/error messages update last-contact time; error receipt must not make measurements fresh |
| Acknowledgment | Database ack flag, name, timestamp. No acknowledgment feedback into AlarmManager. Still-open acknowledged conditions remain in the active query | Communication alert acknowledgment during silence dismisses it and starts another 120-second wait; this needs new logic |
| Recovery | SAFE_IN_BED clears open alarm conditions; cleared but unacknowledged rows remain active because DB query uses open OR unacknowledged | Communication alerts require acknowledgment after recovery. Sensor-error alerts clear automatically on a valid measurement, without acknowledgment |
| Storage | state_log stores transitions, not every frame; alarms and device_health are separate tables | Need environmental readings for 24-hour numeric trends in addition to event/fault history; posture schema cannot be copied unchanged |
| Notifications | Base monitor has local GPIO signaling; network notifier exists separately in solutions/ex5_notify.py and is not wired into main | Independent, non-blocking notification path required; channel remains unselected |
| Code organization | Mostly separated modules, but monitor.py also contains GPIO, capture, preview, snapshot and health functions | Smaller focused modules/functions and a thin entry point, per learner request |

## Suitable reference code

- YAML: adapt yaml.safe_load usage, then agree and implement validation/loading behavior in focused functions.
- SQLite: adapt short-lived connections, parameterized SQL and separation of condition-clear versus human-acknowledged fields. Replace posture-specific schema and retention behavior where needed.
- Monitoring boundary: borrow separate monitor/dashboard pattern; the web process must not own sensor sampling.
- Alarm interface: borrow update/event-queue separation and injectable time for tests, not bed-state rules or defaults.
- Tests: borrow synthetic input/time-based scenarios and database round-trip pattern. Implement our selected timeout and acknowledgment cases.
- Notifications: solutions/ex5_notify.py provides queue/worker/retry patterns. Reuse requires reviewing failure semantics and selecting a transport; it is not an already-integrated feature.
- Dashboard: borrow stale-data display and independent polling concepts; use Impeccable for our environmental UI.

## Concrete issues to avoid copying unchanged

1. **API key exposure:** server.py dashboard() has no require_key decorator but embeds CFG["server"]["api_key"] into its HTML. A visitor reaching the unprotected page can obtain the API key; the API decorators alone do not enforce confidentiality. An independently configured external access gate is not present in the supplied service definitions.
2. **Blocking buzzer:** Annunciator.signal() sleeps on the monitor thread (roughly 0.6 seconds for warning, 0.8 seconds for critical). Its top-level non-blocking description does not apply to this path. solutions/ex1_annunciator.py is an extension candidate, not integrated behavior.
3. **Cooldown is not a repeat scheduler:** _on_commit() is called on state changes. Holding one dangerous state does not automatically emit another alarm when 60 seconds expires. CRITICAL bypass applies to all types mapped CRITICAL, not only FALL.
4. **Acknowledgment does not implement our snooze:** db.ack_alarm() only updates the database. AlarmManager does not observe the action, so our acknowledgment-triggered 120-second re-alert behavior must be implemented explicitly.
5. **Retention comment differs from SQL:** purge() says only closed-and-acknowledged alarms are deleted, but the alarm DELETE checks age and acked=1 without checking ts_cleared. An old acknowledged but ongoing alarm can be deleted.
6. **Historical chart boundary:** state_durations() filters out transitions before the requested start, so it can omit a state that began before and continued into the 24-hour window. Our numeric trend queries need their own window semantics.
7. **Camera failure/heartbeat coupling:** failed cap.read() continues before health logging. The stale warning indicates processing stopped, but does not distinguish process failure from camera acquisition failure. The program does not reopen the camera in that branch.
8. **Startup and clocks:** initialization runs before the guarded main loop, and timing uses time.time(). The source is a teaching prototype rather than proof of unconditional recovery. Our startup, clock and restart behavior remains to be agreed.

## Current scope and next verification

The learner selected startup loading for technical timeouts and live patient-profile updates as a later feature. Current prototype scope is one room, one BME680 and one camera; expansion and Jetson migration are deferred. Technical configuration modules and their tests are written; full pytest and YAML-integration verification awaits the approved Windows/Ubuntu environment. Reference-code permission does not add dependencies or select unapproved hardware versions.

