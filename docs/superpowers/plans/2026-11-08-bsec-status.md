# BSEC Status Implementation Plan

> For agentic workers: use superpowers:executing-plans. User requested fewer checkpoints and inline continuation.

**Goal:** Consume reported Bosch gas status without a host warm-up timer.

**Architecture:** A pure module validates immutable gas metadata. The existing parser/router retains it separately from complete measurements and fault timing.

**Tech Stack:** Existing Python 3.10-compatible standard library and pytest pins. No new Python dependency.

**Spec:** ../specs/2026-11-08-bsec-status-design.md

## Global constraints

- All test/application execution remains deferred to Linux. Write tests before implementation, but claim no observed RED/GREEN cycle.
- Base on PR #6 without merging it. Use isolated bsec-step snapshot and a stacked draft PR.
- Preserve both two-minute fault defaults, current firmware, requirements and sampling rate.
- Do not claim that completed warm-up proves calibration or safety.

## Task 1: Status module and parser/router integration

Interfaces and expected values are in the spec.

- [ ] Write tests/test_gas_readiness.py and real-parser/router cases first.
- [ ] Add gas_readiness.py, parser result metadata, monitor metadata and router updates.
- [ ] Check Python 3.10 grammar without importing application modules.
- [ ] Obtain fresh read-only source review. Document unresolved runtime checks.
- [ ] Update the human guide, README, implementation plan and Linux handoff. Supersede the timer proposal explicitly.
- [ ] Publish a draft PR and fetch content to check publication.

## Review focus

- Legacy valid input must leave gas status unknown rather than inventing readiness.
- Malformed metadata must not corrupt valid measurements or reset fault semantics.
- Ready flags must not hide ongoing calibration.
- Ignored input, silence, recovery and error packets must not present stale readiness as current.
- Numeric Boolean lookalikes and mutable payloads must not bypass validation or change retained state.

## Linux follow-up

Run the full pinned pytest suite before merge readiness. Agree LP three-second sampling and exact firmware dependencies before BSEC firmware replacement. Current hardware operation remains unverified.
