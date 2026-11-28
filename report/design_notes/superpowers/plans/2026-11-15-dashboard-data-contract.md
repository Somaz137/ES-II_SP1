# Dashboard Data Contract Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this approved scope. Steps use checkbox syntax for tracking.

**Goal:** One complete dashboard response, accurate alert text and events, timing settings, 7-day retention and four defect fixes.

**Architecture:** `room_session.py` builds the limit state and events. `room_store.py` stores, queries and prunes. `dashboard.py` assembles the response and health block. `settings.py` owns the timing defaults.

**Tech Stack:** Python 3.10.12; Flask, PyYAML and pytest from the pinned environment.

**Spec:** docs/superpowers/specs/2026-11-15-dashboard-data-contract-design.md

## Global Constraints

- No new dependencies. No network use.
- Fault trackers, serial parser, measurement validation and gas readiness stay unchanged.
- Sustained-breach rule and "Behavior to preserve" stay unchanged.
- No patient limits outside the simulator and tests.
- Write each test before the code it covers.

## Task 1: Timing settings

**Files:** settings.py; config/runtime.yaml; tests/test_runtime_settings.py.

- [x] Test optional keys, defaults, invalid values, rejected combinations and a PyYAML-free import.
- [x] Add `RUNTIME_DEFAULTS`, lazy PyYAML import and combination checks.

## Task 2: Limit state, events and retention

**Files:** room_session.py; room_store.py; occupancy.py; monitor.py; tests/test_room_software.py.

- [x] Test active and pending alerts, monitoring reasons, end-event kinds, acknowledgment event, gas storage and pruning.
- [x] Test the validated legacy profile fallback.
- [x] Implement the structured state, events, event ids, all-series trends and pruning.

## Task 3: Dashboard response and defects

**Files:** dashboard.py; tests/test_dashboard.py.

- [x] Test the response keys, health, paging, form errors and incomplete acknowledgment status.
- [x] Implement the response and fixes.

## Task 4: Page and documents

**Files:** static/room.js; templates/room.html; README.md; README_HUMAN.md; reference_files/PYTHON_FILE_GUIDE.md; room software design.

- [x] Smallest page changes for the new response.
- [x] Update timing tables, limitations and test counts.
- [x] Run the full suite, with and without `-W error`, and the demo with a scratch database.
