# Communication-fault tracking design

Approved scope: learner requested implementation on 8 November 2026 after the communication-fault checkpoint. Testing is explicitly deferred to Linux.

## Required behavior

- One room, one BME680, one camera; communication messages come from ESP32 over USB serial.
- Use the configured communication timeout, initially 120 seconds; do not hardcode it into tracking logic.
- Before the first message, wait from program startup. No immediate startup alarm.
- Any recognized reading or sensor-error message counts as communication. Parser/measurement validation remains outside this module.
- Alert after a full timeout without recognized messages; continue running.
- Restored communication updates actual contact time and clears the current timeout condition, but an outstanding alert requires acknowledgment.
- Acknowledgment during an outage dismisses the alert and starts another full waiting period. Actual last-contact/startup timestamps must not change.
- If still missing at the end of that wait, alert again. Acknowledgment after recovery dismisses the outstanding alert.
- Remove setup_ubuntu.sh in this draft PR and update obsolete current instructions; retain historical course facts.
- Keep functions focused and separate from file/serial/UI I/O. No new dependencies, hardware setup, sensor-error tracker or actual monitor integration.

## Representation and implementation details

Use an immutable CommunicationFaultState snapshot and four public functions:
- create_communication_state(started_at, timeout_s)
- record_communication_message(state, now)
- evaluate_communication_fault(state, now)
- acknowledge_communication_fault(state, now)

Keep actual last_message_at separate from alert_wait_started_at. timed_out describes current communication age; alert_active describes an alert still requiring attention and can remain true after recovery.

The caller supplies finite, nondecreasing times from one clock domain. The actual runtime clock is not selected here. Functions return a new snapshot; initialization accepts time zero.

Implementation details selected for consistent boundary handling: timeout comparison is >=; a message arriving at that boundary is evaluated against the preceding silence before being recorded, so a delayed periodic check cannot erase a completed outage. Acknowledgment when no alert is outstanding does not extend the wait.

## Test and integration boundary

Write hardware-free pytest cases before the module, but do not execute tests until the learner returns to the pinned Linux environment. Add startup/configured-duration, reset, recovery/latching, late-message, acknowledgment/re-alert, invalid-input and nondecreasing-time cases. The future monitor must evaluate periodically even when serial input is silent, and must call record_communication_message only for recognized messages.

The separate sensor-error timer, measurement timestamp, alert persistence/history and serial reconnect behavior remain future work. No claim of end-to-end monitoring is made by this step.

