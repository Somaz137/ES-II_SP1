# Sensor Fault Tracking Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this approved scope; the user's instruction defers all test execution until Linux.

**Goal:** Track persistent sensor errors with communication-driven pause/resume and automatic valid-reading recovery.

**Architecture:** A separate immutable sensor state with caller-supplied times. Preserve actual error/measurement timestamps; accumulate only unpaused error time and use the communication tracker's timed_out flag.

**Tech Stack:** Python 3.10 standard library; existing pytest==8.2.0 for deferred tests.

**Spec:** docs/superpowers/specs/2026-11-08-sensor-fault-design.md

## Global Constraints

- One room, one BME680, one camera.
- Configured sensor-error timeout initially 120 seconds.
- Repeated errors preserve the episode; valid measurements reset and auto-clear it.
- Pause during actual communication timeout, not while an acknowledged/recovered alert merely remains latched.
- No new dependencies, hardware operations, clock selection or Windows test execution.

## Review Focus

- Error time zero must not be mistaken for no episode.
- Paused time must never be added to error_elapsed_s.
- Repeated errors/outages preserve elapsed active time.
- Valid readings clear even at a paused boundary; errors on resume use only the remaining wait.
- Errors/outages cannot update the last valid measurement timestamp.
- The actual communication timeout flag must control pause independently of its acknowledgment latch.

## Task 1: Sensor state and scenarios

**Files:** sensor_fault.py; tests/test_sensor_fault.py; README.md, implementation status and Linux handoff.

**Interfaces:** create_sensor_state(started_at: float, timeout_s: float) -> SensorFaultState; record_sensor_error(state, now), record_valid_measurement(state, now), evaluate_sensor_fault(state, now, *, communication_timed_out: bool) each return a sensor state.

- [x] Write the scenario tests before the module, without executing them.
- [x] Implement pure sensor-state functions and explicit pause semantics.
- [x] Update the Linux handoff for all configuration/communication/sensor tests and unresolved integration choices.
- [x] Review the source; no implementation findings. No tests or application modules executed.
- [x] Publish draft PR #4 (https://github.com/Somaz137/ES-II_SP1/pull/4); runtime verification remains pending.
- [ ] On Linux, verify the pinned environment and run the full suite; record actual results before claiming merge readiness.

## Execution evidence

Test execution is intentionally deferred by the user. Only static syntax/source/link/tree checks are allowed in this Windows step; no tests or application modules are executed. Keep all existing config/communication modules, their tests, package pins and firmware unchanged.

