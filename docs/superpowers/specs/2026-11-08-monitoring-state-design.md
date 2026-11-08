# Monitoring state and routing design

Approved scope: connect the existing parser and fault trackers, preserve complete readings, and show an empty waiting state before the first measurement. User requested fewer build checkpoints. Routine implementation choices proceed without separate approvals.

## Behavior

- Initialize both trackers at program startup using caller-supplied time and configured durations. Before the first complete reading, values and measurement time are absent, and input status is waiting. Communication still times out after 120 seconds by default.
- Store complete readings as immutable values with the host receipt time. This is not an ESP32 acquisition timestamp. Use the same finite nondecreasing clock domain as the fault trackers. Human calendar time conversion and the actual runtime clock remain future work.
- Every recognized valid/error/incomplete record updates communication. Valid readings replace values/time and clear sensor errors. Incomplete/error records retain previous values/time, indicate the latest input immediately, and start/continue the sensor error period.
- Ignored lines retain input and measurement state but still evaluate timed faults. Periodic checks also work without any line.
- Evaluate communication before sensor timing. On a detected timeout, pause sensor timing at this evaluation time before handling a returning recognized message. Return errors resume the remaining period. Valid return clears sensor errors directly. Do not retroactively subtract an unobserved outage.
- Communication recovery preserves its acknowledgment latch. Acknowledgment during silence starts a new full alert delay, without changing contact facts or resuming sensor timing.
- Expose separate input and fault states. Summary status prioritizes communication_lost over waiting_for_first_measurement, incomplete, sensor_error, or fresh. Fresh describes the latest structurally valid input while communication has not timed out. It does not prove gas readiness, clinical safety, or a new measurement on every dashboard refresh.
- No gas-ready or room-safe assertion. Approved gas warm-up is a separate future feature requiring restart reporting and readiness criteria.

## Files and interfaces

- measurements.py: frozen CommittedReading with four scalar fields and received_at. Frozen ReadingState with last_reading, input_status, diagnostic. commit_reading(state, measurements, now) validates and copies scalar values. record_reading_problem(state, kind, message) retains the snapshot.
- monitoring_state.py: frozen MonitoringState combining reading, communication and sensor states. create_monitoring_state(started_at, communication_timeout_s, sensor_error_timeout_s), evaluate_monitoring_faults(state, now), acknowledge_monitoring_communication(state, now), monitoring_status(state). The same file provides process_serial_line(state, line, now), using the real parser and component functions. No serial I/O or clocks inside the router.
- tests/test_reading_state.py and tests/test_message_router.py exercise actual modules, without mocks or hardware.

## Non-goals

No scheduler, serial framing/reconnect, wall-clock selection, database, dashboard, patient rules, firmware changes, dependencies, warm-up implementation or test execution on Windows. All runtime tests remain deferred to the pinned Linux environment.

## Reference

VIGIL preserves the last committed state during occlusion. Here, incomplete input retains measured values and their original receipt time. VIGIL has no BME680 serial router or gas readiness equivalent.
