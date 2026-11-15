# Air Quality, Dust Estimate and Profile Label Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this approved scope. Steps use checkbox syntax for tracking.

**Goal:** Show Bosch's air-quality index and an estimated dust concentration with words and states, check them against system-setup limits, and give the patient profile a short label.

**Architecture:** The firmware adds `iaq` to the reading record. `gas_readiness.py` keeps it. `air_quality.py` decides the index state and word band. `dust.py` gains the automatic baseline. `settings.py` loads `config/system.yaml`. `room_session.py` publishes both blocks and runs their sustained checks beside the patient checks. `room_store.py` validates the label. `dashboard.py` and the page show the result.

**Tech Stack:** Python 3.10.12 with the pinned environment; g++ 11.4.0; arduino-cli with ESP32 core 3.3.12, BSEC2 1.10.2610, BME68x 1.3.40408.

**Spec:** docs/superpowers/specs/2026-11-15-air-quality-dust-label-design.md

## Global Constraints

- No new dependencies. No limit values outside the demo settings and tests.
- Write each test before the code it covers. List every changed existing assertion.

## Task 1: Firmware record

**Files:** firmware/bsec_serial_format.h; firmware/tests/test_bsec_serial_format.cpp; firmware/room_environment_safety_control_bme680.ino.

- [ ] Test `iaq` with a value, null for NaN and out of range. Implement. Compile for the S3.

## Task 2: Host parsing and settings

**Files:** gas_readiness.py; status_output.py; settings.py; config/system.yaml; air_quality.py; tests.

- [ ] Test `iaq` parsing and backward compatibility; system settings validation; the state and band rules.
- [ ] Implement.

## Task 3: Dust baseline

**Files:** dust.py; tests/test_dust.py.

- [ ] Test window, minimum run, fault and gap reset, bounded buckets and the floor at 0. Implement.

## Task 4: Session checks and label

**Files:** room_session.py; room_store.py; monitor.py; simulated_input.py; tests.

- [ ] Test published blocks, sustained alerts, pauses with reasons, alarm level 2 and silence, events, stored series, label validation and the `profile_changed` event.
- [ ] Implement.

## Task 5: Dashboard

**Files:** dashboard.py; templates/room.html; static/room.js; tests/test_dashboard.py.

- [ ] Test the label form, escaping, trends and the API blocks. Implement the smallest page change.

## Task 6: Documents and verification

- [ ] Update READMEs, the dust guide, firmware README, Python file guide and the implementation plan.
- [ ] Run both pytest runs, the C++ tests, both compiles and the demo with saved samples and a screenshot.
