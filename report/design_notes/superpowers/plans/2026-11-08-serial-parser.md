# Serial Parser Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this approved scope. User instruction defers all test execution to Linux.

**Goal:** Classify incoming text records and validate complete numeric measurements without hardware or tracker side effects.

**Architecture:** measurements.py owns the four-field schema and validation; serial_parser.py uses it after JSON decoding and returns a classification. Only valid results carry committable values.

**Tech Stack:** Python 3.10 standard library; existing pytest==8.2.0 for deferred tests.

**Spec:** docs/superpowers/specs/2026-11-08-serial-parser-design.md

## Global Constraints

- One room, one BME680, one camera.
- Four-field finite numeric validation; no new patient/physical thresholds.
- Invalid recognizable readings are incomplete sensor errors; unreadable/unknown input is ignored.
- Actual data/clock/serial/hardware mutation and all test execution remain outside this Windows step.
- No new dependencies or ESP32 configuration command.

## Review Focus

- Boolean/numeric-string/nonfinite values must not become valid measurements.
- Every expected field is required, and incomplete results must expose no partial values to commit.
- Unknown or unreadable input must not be presented as recognizable sensor communication.
- Explicit error records must not accidentally carry valid values.
- Parser and validator must not change trackers, committed measurements or timestamps.

## Task 1: Measurement validator

**Files:** measurements.py, tests/test_measurement_validation.py.
**Produces:** MEASUREMENT_FIELDS; validate_measurements(data: object) -> None, raising ValueError for unusable measurements.

- [x] Write finite/missing/type-validation and no-patient-threshold cases before implementation.
- [x] Implement the pure validator.

## Task 2: Serial classification

**Files:** serial_parser.py, tests/test_serial_parser.py, README/status/Linux handoff.
**Consumes:** MEASUREMENT_FIELDS and validate_measurements.
**Produces:** parse_serial_line(line: str) -> ParsedSerialMessage with four documented kinds.

- [x] Write real JSON-line cases before implementation.
- [x] Implement classification without state/hardware side effects.
- [x] Update reference workflow and deferred Linux verification instructions.
- [x] Source review: no implementation findings; no tests or application modules executed.
- [x] Publish draft PR #5 (https://github.com/Somaz137/ES-II_SP1/pull/5); runtime verification remains pending.
- [ ] On Linux, run the full pinned suite and record results before claiming verification.

## Execution policy

Tests are written but not executed, as explicitly requested. Record static grammar/link/tree checks separately; they do not prove runtime correctness. No Windows interpreter substitution, package installation, firmware operation or merge is part of this step.

