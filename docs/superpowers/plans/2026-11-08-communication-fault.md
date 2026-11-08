# Communication Fault Tracking Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for the approved scope; user instructions defer test execution until Linux.

**Goal:** Implement pure communication-fault timing and remove the obsolete setup shell installer.

**Architecture:** One immutable state snapshot and focused initialization, message, evaluation and acknowledgment functions. Hardware, parsing, runtime clock selection and persistence remain external.

**Tech Stack:** Python 3.10 standard library; existing pinned pytest==8.2.0 for deferred tests.

**Spec:** docs/superpowers/specs/2026-11-08-communication-fault-design.md

## Global Constraints

- One room, one BME680, one camera.
- Normal startup timeout is 120 seconds via existing YAML configuration.
- Communication alerts require acknowledgment; outage acknowledgment restarts the wait without faking contact.
- Remove setup_ubuntu.sh in this draft PR.
- No dependency/version changes, hardware operations or test execution on Windows.

## Review Focus

- Time zero is valid; the first missing-message wait starts at startup.
- Equality at the timeout boundary triggers, and a late message must not erase a completed outage.
- Recovery and acknowledgment are separate.
- Acknowledgment preserves actual contact time and only starts another wait for an outstanding alert.
- Periodic evaluation must work without received messages; caller integration remains unimplemented.

## Task 1: Tracker, scenarios and cleanup

**Files:** communication_fault.py, tests/test_communication_fault.py, README.md, project status and Linux handoff; delete setup_ubuntu.sh.

**Interfaces:** create_communication_state(started_at: float, timeout_s: float) -> CommunicationFaultState; record_communication_message(state, now), evaluate_communication_fault(state, now), acknowledge_communication_fault(state, now) each return a state snapshot.

- [x] Write tests for the approved transitions and listed boundaries.
- [x] Implement the four pure functions and independent contact/alert timing.
- [x] Remove the legacy shell script and update current references.
- [ ] Execute tests in the pinned Linux environment; intentionally deferred by user.
- [ ] Record actual Linux results before merge readiness is claimed.
- [x] Review the source; no implementation findings. Corrected stale branch-selection and YAML-decision text in the handoff/status documents.
- [ ] Publish a draft change; keep full-verification status pending.

## Verification policy

User instruction overrides test-execution workflow: tests are written but not executed on Windows. Read-only source review, syntax parsing and documentation/tree checks may be recorded separately; none replaces a full pytest run. Resume with reference_files/LINUX_AI_HANDOFF.md.

