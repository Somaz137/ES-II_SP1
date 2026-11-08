# BSEC Firmware Implementation Plan

> For agentic workers: use superpowers:executing-plans. User approved three-second LP sampling and inline continuation.

**Goal:** Prepare ESP32 BSEC acquisition and JSON reporting for the existing Python consumer.

**Architecture:** BSEC owns LP timing. A small sketch collects current callback values and sends JSON through an independent portable formatter. Errors continue reporting without panic loops.

**Tech Stack:** ESP32 Arduino C++, Bosch BSEC/BME68x APIs, existing Python test pins. No installations.

**Spec:** ../specs/2026-11-08-bsec-firmware-design.md

## Global constraints

- Keep 115200 baud, I2C21/22, address fallback, all four measurement units and both120-second host faults.
- User defers all tests, builds, imports and hardware checks to Linux. Write tests first, but do not claim RED/GREEN or compilation.
- No exact new dependency version becomes installed/approved by this source preparation.
- Require confirmed sensor supply before compilation. Do not guess breakout voltage or copy board-specific offsets.
- Branch/snapshot on top of unmerged PR #7. Do not merge automatically.

## Task 1: Wire format and BSEC sketch

- [ ] Write portable formatter tests and a real Python consumer fixture case.
- [ ] Implement formatter, guarded board configuration and BSEC sketch.
- [ ] Inspect version-specific pressure conversion, callback signatures, status handling and scheduling against upstream source.
- [ ] Check Python3.10 grammar/JSON/doc links without application execution. Obtain fresh read-only source review.
- [ ] Update human guide, implementation status and Linux handoff. Publish draft PR with tests/builds explicitly pending.

## Review focus

- Pressure double conversion and fixed-point units.
- Stale status reuse across callbacks or missing output fields.
- Silent successful run() calls without any measurement output.
- Nonfinite data, buffer truncation and JSON numeric status typing.
- Startup/measurement failures must report sensor faults without halting or inventing valid readings.

## Deferred Linux verification

Approve exact core/BSEC/BME68x versions and sensor supply. Build/run firmware formatter tests using an available C++11 toolchain, full pinned pytest, then compile the sketch through the approved Arduino setup. Confirm real units, three-second fresh output, flags, and startup/runtime error behavior. No command execution from this section is authorized on Windows.
