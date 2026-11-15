# Local Alarm Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this approved scope. Steps use checkbox syntax for tracking.

**Goal:** A local LED and buzzer alarm commanded by the host, with a dashboard silence control, that can fail without affecting monitoring.

**Architecture:** `alarm.py` decides the level and the reachability state. `room_session.py` runs it after the limit state is built. `serial_transport.py` sends with a bounded write. `serial_parser.py` and `monitoring_state.py` keep the board's reply. `dashboard.py` takes the silence request. `firmware/alarm_command.h` is the testable firmware core.

**Tech Stack:** Python 3.10.12; Flask, PyYAML, pyserial 3.5 and pytest from the pinned environment; g++ 11.4.0 for the firmware host test.

**Spec:** docs/superpowers/specs/2026-11-15-local-alarm-design.md

## Global Constraints

- No new dependencies. No network use.
- The `.ino` sketch, the pin definitions and the board check stay unchanged. Sketch wiring belongs to the firmware port step.
- `status["limit_alerts"]` and the existing contract stay unchanged.
- No patient limits outside the simulator and tests.
- Write each test before the code it covers.

## Task 1: Alarm tracker

**Files:** alarm.py; tests/test_alarm.py.

- [x] Test the level rules, silence by alert id, a new alert sounding again, command timing, reconnect, mismatched replies, timeout and transition events.
- [x] Implement `AlarmTracker`.

## Task 2: Reply record and transport send

**Files:** serial_parser.py; monitoring_state.py; serial_transport.py; simulated_input.py; tests/test_serial_parser.py; tests/test_message_router.py; tests/test_serial_transport.py.

- [x] Test that the reply is its own kind, is kept as `alarm_reply`, and changes neither readings, sensor timing nor communication contact.
- [x] Test `send()`: success, closed port, write timeout, OSError, short write with resync, and a full pseudo-terminal returning within the bound.
- [x] Test the simulated echo, silent and failing modes.
- [x] Implement.

## Task 3: Session, monitor and settings

**Files:** room_session.py; monitor.py; settings.py; config/runtime.yaml; tests/test_alarm_link.py; tests/test_runtime_settings.py.

- [x] Test `alarm_confirm_timeout_s` validation.
- [x] Test the published alarm block, events and silence through the session.
- [x] Test independence with `run_monitor`: with failing and silent transports, readings, fault checks, limit alerts, events and publication continue, and the alarm is unreachable.
- [x] Implement.

## Task 4: Dashboard

**Files:** dashboard.py; templates/room.html; static/room.js; tests/test_dashboard.py.

- [x] Test `POST /silence` acceptance and each 409 case, the Origin check and `health["alarm"]`.
- [x] Implement the route, health entry and the smallest page change.

## Task 5: Firmware core

**Files:** firmware/alarm_command.h; firmware/tests/test_alarm_command.cpp.

- [x] Write the host test, then the header. Compile with `g++ -std=c++11 -Wall -Wextra -pedantic` and run.

## Task 6: Documents and verification

**Files:** README.md; README_HUMAN.md; reference_files/PYTHON_FILE_GUIDE.md; firmware/README.md; reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md.

- [x] State what exists, what is simulated only and what is open.
- [x] Run the full suite, with and without `-W error`, both C++ tests and the demo with a scratch database.
