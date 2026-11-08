# Room Environment Safety Control — Linux AI Handoff

Updated: 8 November 2026.

## Start here

Continue this existing project rather than generating a replacement. First read this handoff, the implementation plan, the manual reference, and the configuration design/test files listed below.

The user explicitly deferred testing **until returning to Linux**. Do not set up a Windows test environment, select a substitute Windows Python, or infer permission to change dependencies. The immediate Linux task is to verify the implemented configuration step in the existing approved environment, then report the results before progressing through unresolved design decisions.

## Repository state at handoff

- Repository: https://github.com/Somaz137/ES-II_SP1
- Current project name: **Room Environment Safety Control**.
- Initial prototype: **one room, one BME680, one camera**.
- Runtime target: Ubuntu 22.04 laptop, recorded Python 3.10.12, existing virtual environment named env.
- ESP32 supplies environmental measurements to the laptop over USB serial. Camera connection and occupancy method are not yet selected.
- Multi-room monitoring, extra sensor buses/hubs and Jetson migration were discussed but **deferred**. Do not implement them.
- Rename/reference work: draft PR #1, https://github.com/Somaz137/ES-II_SP1/pull/1
- Configuration step: draft PR #2, https://github.com/Somaz137/ES-II_SP1/pull/2
- At this handoff both PRs are unmerged. PR #2 targets the rename branch, not main.
- Working branch: codex/technical-alert-config, with implementation commit c8ad133bc37ae2bf29698e5675857eaa4ffb3af8 followed by this handoff update.
- Check current GitHub/checkout state before acting: the user may merge or change branches after this snapshot. Do not assume main already contains these files. Do not merge either PR automatically.

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

The original PDFs and VIGIL source are not included in this repository. The prior AI inspected the user's original VIGIL folder on Windows; do not pretend it exists at that path on Linux. Use the comparison for findings, and obtain the original source if adapting a snippet not available in the checkout.

## User constraints and learning workflow

- Follow course-prescribed versions and procedures. Flag missing specifications and obtain the user's agreement before introducing alternatives, unpinned dependencies, hardware procedures or algorithms.
- Do not recreate, rename or upgrade the existing working Ubuntu env by default.
- Keep distinct responsibilities in small Python files and focused functions; related helpers may share a file. A thin entry point connects them.
- VibeWise learning mode is active. Explain unfamiliar concepts; ask for the learner's approach on meaningful unresolved decisions. Implement only the scope they agree to; an explanation or suggestion is not their design decision.
- Use Impeccable for dashboard work. Use the user's requested GitHub/Superpowers/Computer/Browser/Plugin Management capabilities where relevant; load available instructions before use.
- Appropriate VIGIL snippets may be adapted after inspection. Attribute their origin and preserve our confirmed behavior. Do not copy VIGIL's posture thresholds, Jetson wiring, installer, security issue or alarm lifecycle unchanged.
- Treat this as an educational prototype. Do not invent patient limits or claim clinical validation.
- Do not run setup_ubuntu.sh, install services, flash firmware, enable tunnels, or expose a dashboard remotely as part of resuming tests.

## Step 1 — Resume the correct checkout safely

Work in the user's actual Linux repository directory. Inspect the current branch and uncommitted work before changing branches:

```bash
git status --short
git branch --show-current
git fetch origin
```

If the configuration feature is not merged into the current branch, use the codex/technical-alert-config branch. If it exists only on origin and the working tree is clean, create a tracking checkout with:

```bash
git switch --track origin/codex/technical-alert-config
```

If the local branch already exists, use git switch codex/technical-alert-config instead. Do not run both switch commands indiscriminately. Preserve user changes; do not force checkout, reset, clean, delete or silently stash them. If the PR has since merged, use the branch containing that merged code instead.

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

## Step 3 — Run configuration tests on Linux

From the repository root in the pinned environment:

```bash
python3 -m pytest --version
python3 -m pytest
```

Confirm pytest reports 8.2.0 before treating the run as pinned-environment verification.

The tests exercise:
- Both required timeouts independently, accepting finite positive numeric values.
- Rejection of non-mapping roots, missing fields, bools, strings and other nonnumeric values, nonpositive values, NaN and infinity.
- Real YAML loading with distinct values, rather than hardcoded defaults.
- Malformed/empty YAML and missing files.
- A previously returned settings snapshot remaining unchanged after a file edit; a new explicit load sees the new settings.

Expected: full collection and all tests pass. Inspect any collection/import failures as well as assertion failures. Do not replace PyYAML with a mock or parser workaround.

Prior verification was limited: one valid and 27 invalid direct validator inputs passed on the Windows host; new files parsed against Python 3.10 grammar; an independent source review found no implementation issues. **No full pytest or real PyYAML loading run has been completed yet.** Do not repeat those limited checks and call the full step verified.

On failure, diagnose the cause before editing code. Add a regression test for a real implementation defect, make the smallest scoped fix, then rerun the full suite. Seek agreement before changing the confirmed behavior or package versions.

Record the actual interpreter, dependency versions, command, pass/fail output and any remaining limitation in the implementation plan, feature checklist and PR #2. Mark verification complete only after real evidence. Do not automatically merge.

## Confirmed behavior to preserve

- config/alerts.yaml holds communication_timeout_s: 120 and sensor_error_timeout_s: 120.
- Technical settings load once at startup initially. Patient-profile updates will apply while monitoring continues; that later feature is not implemented.
- Track last recognized ESP32 message, last valid measurement, and beginning of the current sensor-error episode separately.
- Recognized sensor-error messages reset communication timing, but do not make measurements fresh.
- No recognized communication for 120 seconds raises a communication alert while the application keeps running.
- Communication alerts require acknowledgment even after communication resumes.
- Acknowledgment while communication is still missing dismisses that alert and begins another 120-second wait; if still missing, alert again. It must not alter actual last-contact/last-measurement timestamps.
- Persistent sensor errors trigger a separate alert after 120 seconds. Repeated errors do not restart that episode's timer.
- A valid measurement resets the sensor-error waiting period and automatically clears its alert. It does not remove a separate communication alert's acknowledgment requirement.
- The dashboard must show when the last successful measurement arrived. Stale values must not appear freshly measured.

The configuration functions exist; these fault trackers and their integration **do not**.

## Remaining milestones after configuration verification

These are an ordered roadmap, not approval to invent unresolved choices.

| Stage | Next work | Decisions/evidence needed before implementing |
|---|---|---|
| Fault-state design | Define independent communication/sensor fault state and acknowledgment handling in focused modules | Startup grace period, recognized/valid record criteria, mixed silence/error episodes, exact clock mechanism and restart/persistence behavior |
| Hardware-free fault tests | Use synthetic messages and injected times to exercise 120-second boundaries, recovery and acknowledgment/re-alert | Approved state transitions, including what happens at the exact boundary and during repeated faults |
| Serial integration | Feed parsed records into fault tracking; evaluate silence even when no records arrive; keep last valid reading distinct | Serial schema/units, invalid messages, USB disconnect/reconnection behavior and actual port; avoid blocking timer evaluation |
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
| setup_ubuntu.sh | Strongest removal/archive candidate. Legacy installer creates a different .venv, upgrades pip and installs system packages; current working env is already reported installed. Do not use it to resume this project. |
| docs/superpowers/plans/2026-11-08-alert-configuration.md | Temporary feature checklist; useful until Linux tests finish. Afterwards archive or consolidate into the main implementation plan if desired. |
| docs/superpowers/specs/2026-11-08-alert-configuration-design.md | Useful record of the agreed function/validation contract, though not required to run the app. |
| reference_files/VIGIL_COMPARISON.md | Learning/reference document; not runtime code, but preserves verified reuse decisions and prototype defects. |
| tools/check_setup.py | Useful Linux diagnostic; metadata-only limitation is documented. Keep. |
| tools/read_sensor.py and firmware/room_environment_safety_control_bme680.ino | Useful experimental hardware starting point, not a completed or verified monitor. Keep pending approved hardware validation. |
| Configuration modules, tests, requirements.txt, .gitignore, README and manual reference | Active code, checks, dependency pins or necessary guidance. Keep. |

Do not delete files merely because they are not runtime dependencies. The user requested identification of useless files, not deletion. There is no evidence that the original VIGIL manual generators/exercise files are in this GitHub repository; do not confuse the local VIGIL folder with project contents.
