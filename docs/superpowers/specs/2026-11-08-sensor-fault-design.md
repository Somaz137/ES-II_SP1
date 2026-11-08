# Sensor-fault tracking design

Approved scope: the learner selected "implement this step" on 8 November 2026, confirming preserved elapsed error time during communication loss and automatic clearing on a valid measurement. All test execution remains deferred to Linux.

## Required behavior

- One room, one BME680, one camera; use the separately configured sensor_error_timeout_s (initially 120 seconds).
- Startup alone is not a sensor error. Begin the episode on a recognized explicit sensor-error message.
- Repeated sensor errors do not restart the timer.
- A valid measurement resets accumulated error time, clears the episode and automatically clears the sensor alert without acknowledgment.
- Pause sensor-error timing when the communication tracker reports timed_out. Acknowledging its alert does not restore communication and must not resume the sensor timer.
- Preserve accumulated active error time across the pause. Exclude paused time. Another error message resumes the remaining wait; a valid measurement resets it.
- Resumed messages count as communication even if the separate communication alert remains unacknowledged.
- Retain the actual last-valid-measurement timestamp during errors and outages.
- Keep pure sensor-state functions in sensor_fault.py, hardware-free cases in tests/test_sensor_fault.py, and unchanged communication/configuration modules and dependency pins.

## Representation and boundary details

Use an immutable SensorFaultState and four public functions:
- create_sensor_state(started_at, timeout_s)
- record_sensor_error(state, now)
- record_valid_measurement(state, now)
- evaluate_sensor_fault(state, now, communication_timed_out=...)

The caller supplies finite nondecreasing times from the same domain as communication/message timing. The actual runtime clock is not selected here.

Track error_started_at as the actual beginning of the episode, error_elapsed_s as active unpaused time, last_valid_measurement_at as an actual valid arrival, and last_updated_at for accumulation. Do not alter event timestamps to account for pauses.

Explicit implementation details:
- A pause begins when the caller reports communication_timed_out=True at the supplied evaluation time. Time before that transition counts; this does not retroactively exclude the whole physical outage.
- No new sensor alert is raised while paused, including if both timeouts reach their boundary together. Already-raised sensor alerts remain until a valid measurement; pausing does not claim the sensor recovered.
- The boundary is >=. If accumulated time already meets the threshold at pause, an error on resume has no waiting time remaining and alerts immediately. A valid measurement instead clears/reset without raising a transient alert.
- Error and valid-measurement receipt resume this sensor's communication-dependent pause, because a recognized message has arrived. The caller must also update the communication tracker; sensor functions do not mutate it.
- For periodic evaluation pass communication.timed_out, not communication.alert_active. Retain every returned immutable state.

## Scope limits and tests

Write tests before implementation but do not execute them on Windows. Cover startup, configurable duration, repeated errors, recovery, paused duration exclusion, repeated outages, simultaneous boundaries, existing alert preservation, actual measurement timestamps, immutable snapshots, invalid inputs and backwards time. Include tests using the actual communication module to show that acknowledgment does not resume a sensor pause and unacknowledged recovery does not prolong it.

Source/syntax checks are not a passing runtime test result. Parser recognition, actual polling/scheduling, database/history, real hardware and notifications remain unimplemented. Update the Linux handoff so the next AI runs all three feature test files before claiming verification.

