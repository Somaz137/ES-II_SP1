# Monitoring State Implementation Plan

> For agentic workers: use superpowers:executing-plans. User authorized inline implementation and reduced checkpoints.

**Goal:** Connect parsed serial input, retained readings, and fault trackers without hardware I/O.

**Architecture:** Immutable reading snapshots retain complete values and receipt time. A combined state exposes both trackers. A router consumes decoded serial lines.

**Tech Stack:** Existing Python 3.10-compatible standard library and pinned pytest. No new dependency.

**Spec:** ../specs/2026-11-08-monitoring-state-design.md

## Global constraints

- Tests and application execution remain deferred to Linux by explicit user instruction. Write tests first, but do not claim observed RED/GREEN or runtime verification.
- Preserve existing fault semantics and package pins.
- Gas readiness and room safety remain undetermined.
- Use an isolated monitoring-step snapshot and a feature branch. Native clone was unavailable earlier. Preserve all unrelated remote blobs.

## Review focus

- Returning input exactly at timeout must preserve the communication alert.
- Ignored input during silence must still allow timeout evaluation.
- Acknowledgment must not resume paused sensor timing or change receipt times.
- Caller mutation of a measurement dictionary must not corrupt committed readings.
- Valid recovery at a sensor deadline must clear its error, while incomplete input retains original measurement time.

## Task 1: Reading snapshots and routing

Interfaces are defined in the spec. Reading snapshots feed MonitoringState. The router consumes the real parser and both trackers.

- [ ] Write test_reading_state.py and test_message_router.py first. Cover waiting/empty startup, replacement, retention, ignored lines, distinct contact/measurement times, both timeout boundaries, pause/resume, acknowledgment/re-alert, valid recovery, custom durations, invalid/backwards time, and dictionary isolation.
- [ ] Implement measurements.py, monitoring_state.py.
- [ ] Check Python 3.10 grammar without importing application modules. Expected: all Python sources parse. This does not prove runtime correctness.
- [ ] Obtain one fresh read-only source review and address substantive findings.
- [ ] Update human guide, README, implementation plan and Linux handoff. Check links and preserve unrelated blobs.
- [ ] Publish a draft PR with tests explicitly unrun. Fetch published files to check content.

## Deferred Linux verification

Run python3 -m pytest in the existing approved environment. Expected: full suite passes. Record actual failures without assuming they originate in new code. No test execution is authorized on Windows.
