# Technical Alert Configuration Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this approved scope. Steps use checkbox syntax for tracking.

**Goal:** Read and validate the two startup-only technical timeout settings.

**Architecture:** Keep YAML in config/alerts.yaml, file parsing and pure validation in settings.py. The caller keeps a validated settings snapshot.

**Tech Stack:** Python 3.10; PyYAML==6.0.1; pytest==8.2.0.

**Spec:** docs/superpowers/specs/2026-11-08-alert-configuration-design.md

## Global Constraints

- One room, one BME680, one camera.
- Both initial timeout values: 120 seconds.
- Technical settings load at startup; patient live updates are separate.
- Keep existing package pins and firmware behavior unchanged.

## Review Focus

- YAML booleans must not count as numeric timeout values.
- NaN, infinity and non-positive values must not enter timing logic.
- Both required fields must be checked independently.
- Empty or malformed YAML must fail clearly.
- Existing settings must not change when the source file is edited.

## Task 1: Configuration and tests

**Files:** config/alerts.yaml; settings.py; tests/test_config.py.

**Interfaces:** load_alert_settings(path: str | Path) -> dict; validate_alert_settings(data: object) -> None, raising ValueError on invalid settings.

- [x] Write pytest cases using actual temporary YAML files and hand-derived expected values.
- [x] Check available interpreters and pinned dependencies before execution.
- [ ] Run tests before implementation in the pinned environment; blocked by unavailable approved dependencies. A standard-library validator smoke check instead observed the missing module before implementation.
- [x] Implement the approved configuration and two functions.
- [x] Run limited host-only validator checks: one valid and 27 invalid inputs passed; Python 3.10 grammar checks passed for the new Python files.
- [x] Obtain a read-only source review; no implementation findings. Full verification remains blocked.
- [ ] Run the full suite with python -m pytest; expect all cases to pass.
- [x] Prepare a reviewable draft based on the existing rename branch; preserve pending full-verification status.

## Environment constraint

The learner subsequently deferred testing to their Linux setup. Resume in the existing Ubuntu env using reference_files/LINUX_AI_HANDOFF.md. Do not create the previously discussed Windows environment or select Python 3.10.11. The notes below explain the earlier Windows limitation, not an outstanding request for Windows installation.

Available Windows Python is 3.14.7 with pytest 9.1.1 and no PyYAML; another Python is 3.12.12 with neither dependency. Do not use those dependency versions as a replacement for the pinned environment. The learner subsequently authorized required downloads in C:/Users/User/OneDrive/Desktop/ES-II_SP1, which is outside this session's writable roots. Python.org supplies no Windows installer for 3.10.12; interpreter selection needs agreement before a substitution.

