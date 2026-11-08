# Room Environment Safety Control — Linux AI Handoff

Updated: 8 November 2026.

## Start here

Continue this existing project rather than generating a replacement. First read this handoff, the implementation plan, the manual reference, and the configuration design/test files listed below.

The user explicitly deferred testing **until returning to Linux**. Do not set up a Windows test environment, select a substitute Windows Python, or infer permission to change dependencies. The immediate Linux task is to verify the implemented configuration, fault-tracker and serial-parser/measurement-validation steps in the existing approved environment, then report the results before progressing through unresolved design decisions.

## Repository state at handoff

- Repository: https://github.com/Somaz137/ES-II_SP1
- Current project name: **Room Environment Safety Control**.
- Initial prototype: **one room, one BME680, one camera**.
- Runtime target: Ubuntu 22.04 laptop, recorded Python 3.10.12, existing virtual environment named env.
- ESP32 supplies environmental measurements to the laptop over USB serial. Camera connection and occupancy method are not yet selected.
- Multi-room monitoring, extra sensor buses/hubs and Jetson migration were discussed but **deferred**. Do not implement them.
- Rename/reference work: draft PR #1, https://github.com/Somaz137/ES-II_SP1/pull/1
- Configuration step: draft PR #2, https://github.com/Somaz137/ES-II_SP1/pull/2
- Rename PR #1 and configuration PR #2 were unmerged at the last check. PR #2 targets the rename branch, not main.
- Communication-fault tracker: draft PR #3, https://github.com/Somaz137/ES-II_SP1/pull/3
- Sensor-fault tracker: draft PR #4, https://github.com/Somaz137/ES-II_SP1/pull/4
- Serial parser: draft PR #5, https://github.com/Somaz137/ES-II_SP1/pull/5
- Current working branch: codex/serial-parser, based on codex/sensor-faults. Its draft PR targets the sensor branch; inspect the active PR listing for current merge status.
- Prior configuration implementation commit: c8ad133bc37ae2bf29698e5675857eaa4ffb3af8; prior handoff commit: c533280a24437e534edb87b3807de6184279ec24.
- Check current GitHub/checkout state before acting: the user may merge or change branches after this snapshot. Do not assume main already contains these files. Do not merge PRs automatically.

## Read these files

| File | Authority / purpose |
|---|---|
| README.md | Short current entry point |
| reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_PROJECT8_IMPLEMENTATION_PLAN.md | Project status, confirmed choices and remaining milestones |
| reference_files/ROOM_ENVIRONMENT_SAFETY_CONTROL_MANUAL_REFERENCE.md | Extracted manual facts, version sources and hardware/setup gaps |
| reference_files/VIGIL_COMPARISON.md | Actual VIGIL-source comparison and limitations on reuse |
| docs/superpowers/specs/2026-11-08-alert-configuration-design.md | Approved configuration contract |
| docs/superpowers/plans/2026-11-08-alert-configuration.md | Configuration implementation and verification checklist |
| config/alerts.yaml | Technical timeout settings |
| config_loader.py | load_alert_settings(path) |
| config_validation.py | validate_alert_settings(data) |
| tests/test_config.py | Real-file configuration and validation tests |
| communication_fault.py | Pure startup, contact, timeout and acknowledgment tracking |
| tests/test_communication_fault.py | Communication scenarios; written but not run |
| sensor_fault.py | Sensor-error timing and communication-driven pause/resume |
| tests/test_sensor_fault.py | Deferred sensor scenarios and actual communication-state interaction cases |
| measurement_validation.py | Four-field structural numeric validation |
| serial_parser.py | Stateless decoded-line classification; no partial committable payloads |
| tests/test_measurement_validation.py, tests/test_serial_parser.py | Deferred validator and real JSON-line cases |
| docs/superpowers/specs/2026-11-08-serial-parser-design.md | Agreed classifications, data contract and state-integration boundary |
| docs/superpowers/plans/2026-11-08-serial-parser.md | Parser implementation and deferred-verification checklist |
| docs/superpowers/specs/2026-11-08-sensor-fault-design.md | Confirmed sensor behavior and explicit pause-boundary details |
| docs/superpowers/plans/2026-11-08-sensor-fault.md | Sensor implementation and deferred-verification checklist |
| docs/superpowers/specs/2026-11-08-communication-fault-design.md | Required fault behavior and explicit boundary details |
| docs/superpowers/plans/2026-11-08-communication-fault.md | Communication implementation and deferred-verification checklist |

The original PDFs and VIGIL source are not included in this repository. The prior AI inspected the user's original VIGIL folder on Windows; do not pretend it exists at that path on Linux. Use the comparison for findings, and obtain the original source if adapting a snippet not available in the checkout.

## User constraints and learning workflow

- Follow course-prescribed versions and procedures. Flag missing specifications and obtain the user's agreement before introducing alternatives, unpinned dependencies, hardware procedures or algorithms.
- Do not recreate, rename or upgrade the existing working Ubuntu env by default.
- Keep distinct responsibilities in small Python files and focused functions; related helpers may share a file. A thin entry point connects them.
- VibeWise learning mode is active. Explain unfamiliar concepts; ask for the learner's approach on meaningful unresolved decisions. Implement only the scope they agree to; an explanation or suggestion is not their design decision.
- After every checkpoint answer, explain the verified corresponding VIGIL behavior. State when it has no direct equivalent rather than inventing reference behavior.
- Use Impeccable for dashboard work. Use the user's requested GitHub/Superpowers/Computer/Browser/Plugin Management capabilities where relevant; load available instructions before use.
- Appropriate VIGIL snippets may be adapted after inspection. Attribute their origin and preserve our confirmed behavior. Do not copy VIGIL's posture thresholds, Jetson wiring, installer, security issue or alarm lifecycle unchanged.
- Treat this as an educational prototype. Do not invent patient limits or claim clinical validation.
- The legacy setup shell installer has been removed at the user's request. Do not recreate it, install services, flash firmware, enable tunnels, or expose a dashboard remotely as part of resuming tests.

## Step 1 — Resume the correct checkout safely

Work in the user's actual Linux repository directory. Inspect the current branch and uncommitted work before changing branches:

```bash
git status --short
git branch --show-current
git fetch origin
```

If the checkout does not contain serial_parser.py, measurement_validation.py and both new test files as well as earlier configuration/fault files, use codex/serial-parser (or a merged successor containing them). Earlier feature merges alone do not establish that this parser is present. If it exists only on origin and the working tree is clean, create a tracking checkout with:

```bash
git switch --track origin/codex/serial-parser
```

If the local branch already exists, use git switch codex/serial-parser instead. Do not run both switch commands indiscriminately. Preserve user changes; do not force checkout, reset, clean, delete or silently stash them. If the PR has since merged, use the branch containing that merged code instead.

## Step 2 — Verify the existing Linux environment

Activate the already-created env using its actual path. If it is at the repository root, the recorded activation is:

```bash
source env/bin/activate
```

Do not create a new environment if that path is absent; locate the user's existing one or ask for its location.

Recorded manual checks:

```bash
python3 --version
python3 -c "import numpy as np; print('NumPy', np.__version__)"
python3 -c "import cv2; print(cv2.__version__)"
```

Expected: Python 3.10.12, NumPy 1.26.4, cv2 4.11.0.

Pinned distributions in requirements.txt:

| Distribution | Version |
|---|---|
| numpy | 1.26.4 |
| opencv-python | 4.11.0.86 |
| pyserial | 3.5 |
| Flask | 3.0.3 |
| PyYAML | 6.0.1 |
| pytest | 8.2.0 |

The existing diagnostic can report package metadata and Linux device visibility:

```bash
python3 tools/check_setup.py
```

Read every CHECK / NOT INSTALLED result: the script does not fail its exit code on version mismatches, and metadata does not prove successful imports. Missing USB/camera devices do not block hardware-free configuration tests. If dependencies differ, report the mismatch and consult the manual/user before reinstalling or upgrading. The user previously reported requirements installation successful; do not repeat it automatically.

## Step 3 — Run the full configuration, fault and parser suite on Linux

From the repository root in the pinned environment:

```bash
python3 -m pytest --version
python3 -m pytest
```

Confirm pytest reports 8.2.0 before treating the run as pinned-environment verification.

The configuration tests exercise:
- Both required timeouts independently, accepting finite positive numeric values.
- Rejection of non-mapping roots, missing fields, bools, strings and other nonnumeric values, nonpositive values, NaN and infinity.
- Real YAML loading with distinct values, rather than hardcoded defaults.
- Malformed/empty YAML and missing files.
- A previously returned settings snapshot remaining unchanged after a file edit; a new explicit load sees the new settings.

The new communication tests cover startup at time zero, configurable durations, exact timeout boundaries, recognized-message resets, regular communication, restored-but-unacknowledged alerts, late messages, acknowledgment/re-alert timing, no-op acknowledgment, recovery during a waiting period, immutable snapshots and invalid/backwards times. They use supplied times rather than real two-minute waits. No communication tests have been executed yet.

The sensor tests cover explicit-error startup, independent duration, repeated errors, valid-reading reset/auto-clear, excluded paused time, repeated pause/resume, simultaneous timeout boundaries, preserved existing alerts and last-valid-measurement time, immutable states and invalid/backwards inputs. Two cases use the actual communication module to distinguish its timeout status from its acknowledgment latch. No sensor tests or application modules have been executed.

The new validator/parser tests cover every required field, finite numbers, bool/string/nonfinite rejection, no invented patient thresholds, real JSON lines, explicit errors, missing/unusable diagnostic text, partial fields, whitespace, extra metadata, overflow, garbled/unknown/non-object input, deep decoder input and decoded-text caller contract. These tests also remain unexecuted. Run all five test files through the full suite command above.

Expected: full collection and all tests pass. Inspect any collection/import failures as well as assertion failures. Do not replace PyYAML with a mock or parser workaround.

Prior verification was limited: one valid and 27 invalid direct validator inputs passed on the Windows host; new files parsed against Python 3.10 grammar; an independent source review found no implementation issues. **No full pytest or real PyYAML loading run has been completed yet.** Do not repeat those limited checks and call the full step verified.

On failure, diagnose the cause before editing code. Add a regression test for a real implementation defect, make the smallest scoped fix, then rerun the full suite. Seek agreement before changing the confirmed behavior or package versions.

Record the actual interpreter, dependency versions, command, pass/fail output and any remaining limitation in the implementation plan, feature checklists and the current serial-parser PR. Mark verification complete only after real evidence. Do not automatically merge.

## Selected execution intervals

These are design decisions, not an implemented monitoring loop.

| Operation | Selected interval | Current control/status |
|---|---|---|
| BME680 acquisition | Approximately 1 second | Existing experimental ESP32 firmware timing; actual hardware rate unverified |
| Camera occupancy processing | 60 seconds | Latest learner choice; supersedes the earlier 5-second proposal; Python scheduling not implemented |
| Fault evaluation | 5 seconds | Selected for future Python monitoring loop |
| Dashboard refresh | 10 seconds | Selected for future dashboard |

The future Python-side technical settings should load at startup. The camera processing interval does not select a capture frame rate or buffering policy; those remain open. Occupancy may reflect the previous observation until the next one-minute processing check. When five-second fault evaluation is integrated, timeout detection occurs on the next check, potentially almost five seconds after the duration expires plus scheduling/processing delay.

## Future side note — ESP32 sampling configuration (deferred)

The learner explicitly declined adding ESP32 startup configuration now and requested that the idea be kept for later.

Possible later extension: read a desired acquisition interval from laptop YAML and send it to the ESP32 over USB serial at startup, with agreed firmware handling and confirmation. No command format, firmware implementation, dependency version, or automatic action is selected or authorized by this note.

For the current prototype, leave the ESP32's approximately one-second acquisition timing in its firmware. Do not add a YAML field that appears to control actual acquisition without implementing the ESP32 path; changing Python read/poll delays would not change the sensor's firmware sampling interval. This defers actual YAML-to-ESP32 interval control, rather than implementing a misleading host-only setting.

## Confirmed behavior to preserve

- config/alerts.yaml holds communication_timeout_s: 120 and sensor_error_timeout_s: 120.
- Technical settings load once at startup initially. Patient-profile updates will apply while monitoring continues; that later feature is not implemented.
- Track last recognized ESP32 message, last valid measurement, and beginning of the current sensor-error episode separately.
- Recognized sensor-error messages reset communication timing, but do not make measurements fresh.
- No recognized communication for 120 seconds raises a communication alert while the application keeps running. Before the first message, start the usual timeout at program startup.
- Communication alerts require acknowledgment even after communication resumes.
- Acknowledgment while communication is still missing dismisses that alert and begins another 120-second wait; if still missing, alert again. It must not alter actual last-contact/last-measurement timestamps.
- Persistent sensor errors trigger a separate alert after 120 seconds. Repeated errors do not restart that episode's timer.
- A valid measurement resets the sensor-error waiting period and automatically clears its alert. It does not remove a separate communication alert's acknowledgment requirement.
- Sensor-error time pauses on communication.timed_out, preserving elapsed active time and excluding paused time. Another sensor-error message resumes the remaining wait; a valid measurement resets it. Acknowledgment alone never resumes timing.
- The dashboard must show when the last successful measurement arrived. Stale values must not appear freshly measured.

The configuration functions, both pure fault trackers, serial classification and measurement validation exist. Committed-measurement state and actual serial/UI/history integration **do not**. Communication calls return immutable snapshots: retain each returned state, evaluate periodically even during serial silence, and supply finite nondecreasing times from one clock domain. `timed_out` can clear on recovery while `alert_active` remains latched until acknowledgment. Equality at the timeout boundary triggers; a message received at/after that point first preserves the elapsed fault. Acknowledgment with no outstanding alert cannot postpone detection.

Sensor pauses start at the supplied timeout-status transition, not retroactively at the last message. Time before that pause still counts. Existing sensor alerts remain until a valid reading; no new sensor alert is raised while paused. If no waiting time remains when an error resumes, alert immediately; if the returned message is valid, reset/clear instead. The future loop must update communication, synchronize its actual timeout status with the sensor tracker, process recognized sensor records, and publish the final resulting snapshots rather than transient intermediate states. Real polling and clock selection are not yet implemented.

Serial parsing now returns valid_reading, sensor_error, incomplete_reading or ignored. Recognized readings need all four expected finite numeric fields; bools and numeric strings are invalid. Incomplete readings must preserve the last complete committed values/time, immediately indicate incomplete input, and count as sensor errors. Ignored input must not reset communication. Only valid_reading carries measurements. The stateless parser does not itself perform these state updates or connect to hardware; this routing/retention is the next integration step.

## Remaining milestones after configuration verification

These are an ordered roadmap, not approval to invent unresolved choices.

| Stage | Next work | Decisions/evidence needed before implementing |
|---|---|---|
| Verify communication state | Run the written startup, message, acknowledgment and re-alert cases; fix scoped defects with evidence | Existing startup choice is normal timeout from program start; retain documented boundary behavior; actual runtime clock and persistence remain open |
| Verify sensor state | Run the written error, valid-reading, pause/resume and interaction cases using the full suite | Pause/resume and auto-clear are agreed; do not reimplement them. Message classification/finite validation is now implemented; actual timing/scheduling and persistence remain open |
| Verify fault interaction | Run the written actual-module interaction cases as part of the full Linux suite | Use communication.timed_out for pause; acknowledgment latch alone must neither pause nor resume sensor timing |
| Reading-state and serial integration | Route the already-classified results into fault trackers, preserve last committed values/time, and evaluate silence independently of record receipt | Parsed kinds/finite-field checks are implemented. Agree runtime clock/order, committed-state interface, USB disconnect/reconnection/framing and actual port; avoid blocking five-second fault evaluation |
| BME680 verification | Confirm board/breakout, actual readings and failure records using the single-sensor starting point | Arduino IDE 2.3.10 status; missing Modules 4.2/4.3 or agreed external procedure; ESP32 core and BME680 library/version approval; wiring before flashing |
| Camera occupancy | Acquire camera input and determine occupied/absent/uncertain/failure behavior | Camera type/connection and approved detection method; motion alone must not be assumed equivalent to occupancy; no new vision dependency without agreement |
| Patient profiles and room rules | Load/select a profile, edit patient limits through a form, and apply sustained-breach decisions | Profile format/identity, monitored metrics/units, safe limits, breach duration, changed-limit effect on running timers, recovery/cooldown, occupancy gating, invalid profile behavior |
| Persistence | Store numeric measurements plus events/fault state suitable for the required 24-hour trends | Schema, sampling/retention, time-window semantics and restart behavior; do not copy VIGIL's posture-only schema unchanged |
| Dashboard | Show live values, last valid measurement time, distinct fault states, patient settings, trends and history | Agreed APIs, access/acknowledgment policy, update rate and chart approach; use Impeccable; keep acquisition independent from web requests |
| Notifications | Send agreed alerts independently of monitoring and local records | Transport, retries/offline behavior, queue policy and optional local alarm wiring; no synchronous network calls in sampling logic |
| Integrated demonstration | Verify real sensor/camera input, simulated failures, profile changes and non-blocking delivery | Run hardware-free suite plus separate hardware demonstrations; document actual results rather than assuming operation |

The book's ten-minute environmental breach example is not a selected default. Do not reuse the 120-second technical-fault timeouts as patient-breach durations.

## Repository cleanup assessment

| File/group | Assessment |
|---|---|
| setup_ubuntu.sh | Removed in the communication feature at explicit user request. Do not restore or recreate it when resuming the approved environment. |
| docs/superpowers/plans/2026-11-08-alert-configuration.md | Temporary feature checklist; useful until Linux tests finish. Afterwards archive or consolidate into the main implementation plan if desired. |
| docs/superpowers/specs/2026-11-08-alert-configuration-design.md | Useful record of the agreed function/validation contract, though not required to run the app. |
| reference_files/VIGIL_COMPARISON.md | Learning/reference document; not runtime code, but preserves verified reuse decisions and prototype defects. |
| tools/check_setup.py | Useful Linux diagnostic; metadata-only limitation is documented. Keep. |
| tools/read_sensor.py and firmware/room_environment_safety_control_bme680.ino | Useful experimental hardware starting point, not a completed or verified monitor. Keep pending approved hardware validation. |
| Configuration/fault/parser/validation modules, tests, requirements.txt, .gitignore, README and manual reference | Active code, checks, dependency pins or necessary guidance. Keep. |

Do not delete files merely because they are not runtime dependencies. The user originally requested identification, then explicitly authorized removing only setup_ubuntu.sh in the next draft PR. There is no evidence that the original VIGIL manual generators/exercise files are in this GitHub repository; do not confuse the local VIGIL folder with project contents.



