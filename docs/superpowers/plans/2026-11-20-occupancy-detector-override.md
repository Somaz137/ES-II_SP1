# Occupancy Detector, Confirmation, Hold and Override Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the HOG camera detector with a pretrained YOLOX person detector run by OpenCV, add the entry-confirmation and hold rule, and add a three-way manual occupancy override on the dashboard.

**Architecture:** A detector module wraps `cv2.dnn` and answers `detect(frame) -> bool`. A pure occupancy rule turns timed check results into a state. The camera worker feeds the rule. A pure override resolver combines the camera state with the stored manual request. The monitor applies it at each publish. The dashboard stores override requests in SQLite, the same pattern as silence and acknowledge.

**Tech Stack:** Python 3, OpenCV 4.11 (`cv2.dnn`, already pinned), Flask, SQLite, pytest. No new pip package.

**Spec:** `docs/superpowers/specs/2026-11-20-occupancy-detector-override-design.md`

## Global Constraints

- No new pip package. `requirements.txt` stays unchanged.
- No camera frame is written to disk or sent anywhere, in the monitor or in the bench tool.
- Model: OpenCV zoo `object_detection_yolox_2022nov.onnx`, stored in `models/` (git-ignored), checked against a pinned SHA-256. Record its licence (Apache 2.0, from the zoo's LICENSE file) in the README.
- Runtime defaults: `camera_interval_s` 10, `occupancy_confirm_s` 120, `occupancy_confirm_fraction` 0.75, `occupancy_hold_s` 900, `occupancy_override_s` 900, `person_confidence` 0.5. (Task 5b may lower `person_confidence`, by the rule in the spec section "Decision after the bench gate", part A.)
- **Amendment, 23 November 2026.** The gate failed on "lying under a blanket" (4/12). The user chose options A and C plus a MediaPipe comparison on the bench only. See the spec section "Decision after the bench gate". This adds Task 1b and Task 5b, and adds the "assume occupied" step to Tasks 2, 3, 4 and 6. Task numbers 1–6 do not change.
- MediaPipe code lives only in `tools/`. No production module imports it.
- States in the status record: `occupied`, `not_seen`, `unknown`, `not_occupied` (manual only). Only `occupied` allows limit alerts.
- Reason codes: `occupancy_not_seen`, `occupancy_unknown`, `occupancy_manual`.
- Page wording is factual. It never relies on colour alone. `not_seen` uses the amber tone, the same as `unknown`.
- Run the tests with `env/bin/python -m pytest -q -p no:cacheprovider`. The baseline is 667 passed. No existing test may be deleted. A test whose expected text changes because of the new reason codes is updated, and the commit message says so.
- Each commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The camera is unplugged while the room is occupied.** The room stays `occupied` until 900 s after the last sighting, then becomes `unknown`. Tested in Task 2 (`test_camera_failure_keeps_hold_then_unknown`).
2. **A damaged or unknown stored override** (not a mapping, a bad mode, a missing `set_at`) is ignored as `auto`. It does not crash the monitor. Tested in Task 4 (`test_damaged_override_is_ignored`).
3. **A manual setting made while the monitor was stopped.** It is applied at start if still within 900 s, and ignored if expired. Tested in Task 4 (`test_override_survives_restart_until_expiry`).
4. **The model file is missing or has a wrong hash in camera mode.** `monitor.py --camera` exits with a message that names `tools/get_person_model.py`. Demo mode and serial mode without `--camera` do not need the file. Tested in Task 1 and Task 3.
5. **Settings that make the rule impossible:** `occupancy_confirm_s` shorter than `camera_interval_s`, a fraction outside (0, 1], or a confidence outside (0, 1). Each is refused at load. Tested in Task 3.

---

### Task 1: Person detector, model download and bench tool (GATE)

**Files:**
- Create: `person_detector.py`
- Create: `tools/get_person_model.py`
- Create: `tools/occupancy_bench.py`
- Modify: `.gitignore` (add `models/`)
- Test: `tests/test_person_detector.py`

**Interfaces:**
- Produces:
  - `MODEL_PATH: Path` (`<project>/models/object_detection_yolox_2022nov.onnx`) and `MODEL_SHA256: str` in `person_detector.py`.
  - `class ModelError(Exception)`.
  - `check_model(path: Path | None = None) -> None` (None resolves to the module's `MODEL_PATH` at call time, so tests can monkeypatch it). It raises `ModelError` when the file is missing or its SHA-256 differs. The message names `tools/get_person_model.py`.
  - `class PersonDetector: __init__(self, confidence: float = 0.5, path: Path | None = None, net=None)` and `detect(self, frame) -> bool`. `net=None` loads `cv2.dnn.readNet(str(path))` after `check_model`. A test passes a stub net.
  - `person_boxes(raw_output, confidence: float, frame_shape, input_size) -> list` (pure post-processing: COCO class 0 only, score threshold, non-maximum suppression with `cv2.dnn.NMSBoxes`).

- [ ] **Step 1: Write the failing tests** in `tests/test_person_detector.py`:
  - `test_missing_model_raises_with_download_hint`: `check_model(tmp_path / "x.onnx")` raises `ModelError`, and `"tools/get_person_model.py" in str(error)`.
  - `test_wrong_hash_raises`: a file with the bytes `b"not a model"` raises `ModelError`.
  - `test_person_boxes_keeps_only_class_zero_above_threshold`: build a raw output in the YOLOX decoded layout with one person at score 0.9, one person at 0.3 and one dog (class 16) at 0.95. With confidence 0.5, exactly one box is returned.
  - `test_overlapping_person_boxes_are_merged`: two person boxes with IoU above 0.5 return one box.
  - `test_detect_uses_stub_net`: a stub with `setInput(blob)` and `forward()` returning the person-at-0.9 output gives `detect(frame) is True`. A stub returning only the dog gives `False`. Use a `numpy.zeros((480, 640, 3), numpy.uint8)` frame.
- [ ] **Step 2: Run** `env/bin/python -m pytest -q -p no:cacheprovider tests/test_person_detector.py`. Expected: FAIL (module not found).
- [ ] **Step 3: Implement `person_detector.py`.** Follow the zoo's `models/object_detection_yolox/demo.py` and `yolox.py` for the input size (640), letterbox, the grid and stride decoding, and the score as objectness × class score. The frame is a local variable only and is never stored on the object.
- [ ] **Step 4: Implement `tools/get_person_model.py`.** It downloads the pinned URL of the ONNX file from the OpenCV zoo (Hugging Face `opencv/opencv_zoo`, `models/object_detection_yolox/object_detection_yolox_2022nov.onnx`) to `models/`, writes to a temporary name, checks the SHA-256, and renames. On a mismatch it deletes the temporary file and exits 1. Set `MODEL_SHA256` from the file you download, and record the URL and hash in the tool's docstring.
- [ ] **Step 5: Implement `tools/occupancy_bench.py --camera N [--frames 12]`.** For each frame it prints `frame <i>: HOG <yes|no> YOLOX <yes|no>`. At the end it prints `HOG <n>/<total>, YOLOX <n>/<total>`. HOG uses the same call as today's `occupancy.py` (`HOGDescriptor_getDefaultPeopleDetector`, `winStride=(8, 8)`, `scale=1.05`). It captures one frame every 1 s, holds no list of frames, and writes nothing.
- [ ] **Step 6: Run the tests.** Expected: the new tests PASS, and the full suite gives 667 + new tests passed.
- [ ] **Step 7: Run the tools.** Run `env/bin/python tools/get_person_model.py`, then `env/bin/python -I tools/occupancy_bench.py --camera 0 --frames 3` with no person in view. Expected: the hash check passes and three lines plus a total are printed. Record the YOLOX time per frame (measured).
- [ ] **Step 8: Commit** with the message `Add the YOLOX person detector, model download and HOG comparison bench tool`.
- [ ] **Step 9: STOP. Gate.** Report to the main session. The user runs the bench tool in four positions: standing, sitting, lying on a bed or sofa, and lying under a blanket, with 12 frames each. Pass: YOLOX detects 9 or more of 12 frames in each lying position. Do not start Task 2 until the main session reports the result.

> **Gate result (20 November 2026):** standing 12/12, sitting 9/12, lying 11/12, lying under a blanket 4/12 (FAIL), empty room 0/12. The user decided on 23 November 2026 to go on with options A and C (spec, "Decision after the bench gate"). Tasks 2–6 go ahead. The bench-only diagnostic `top_score` and `--confidence` were added in commit `4d06e35`.

### Task 1b: MediaPipe person detector in the bench tool (bench only)

**Files:**
- Create: `tools/mediapipe_person.py`
- Modify: `tools/get_person_model.py` (an option to also fetch the MediaPipe model)
- Modify: `tools/occupancy_bench.py` (an MP column)
- Test: `tests/test_mediapipe_person.py`

**Interfaces:**
- Produces, in `tools/mediapipe_person.py` only:
  - `MP_MODEL_PATH: Path` (`<project>/models/person_detection_mediapipe_2023mar.onnx`) and `MP_MODEL_SHA256: str`.
  - `class MediaPipePerson: __init__(self, confidence: float = 0.5, path: Path | None = None, net=None)`, `detect(frame) -> bool` and `top_score(frame) -> float`. It uses the same `check_model` pattern and the same `ModelError` as `person_detector.py`: reuse them, do not copy them.
  - A pure post-processing function for the raw outputs, with anchor decoding and NMS. Follow the zoo's `models/person_detection_mediapipe/mp_persondet.py` and `demo.py` for the input size, the anchors and the score (sigmoid).

- [ ] **Step 1: Write the failing tests** in `tests/test_mediapipe_person.py`:
  - `test_mp_missing_model_raises_with_download_hint`: a missing path raises `ModelError` that names `tools/get_person_model.py`.
  - `test_mp_postprocess_keeps_scores_above_threshold`: a raw output with one anchor at score logit +3 (about 0.95) and the others at −10. With confidence 0.5, one box. With confidence 0.99, none.
  - `test_mp_detect_uses_stub_net`: a stub net with `setInput` and `forward` gives `detect(frame) is True` for the high-score output and `False` for an all-low output. Use a `numpy.zeros((480, 640, 3), numpy.uint8)` frame.
  - `test_production_modules_do_not_import_mediapipe`: `occupancy.py`, `monitor.py` and `person_detector.py` contain no `mediapipe` import (a text check on the files).
- [ ] **Step 2: Run** the new tests. Expected: FAIL.
- [ ] **Step 3: Implement `tools/mediapipe_person.py`.** The frame is a local variable only and is never stored.
- [ ] **Step 4: Extend `tools/get_person_model.py`** with `--mediapipe`. It downloads `models/person_detection_mediapipe/person_detection_mediapipe_2023mar.onnx` from Hugging Face `opencv/opencv_zoo` the same way as YOLOX: a temporary name, a SHA-256 check, and a rename. Pin the hash from the downloaded file. Record the URL, the hash and the licence (from the zoo's LICENSE file next to the model) in the docstring.
- [ ] **Step 5: Extend `tools/occupancy_bench.py`.** When the MediaPipe model file is present, each line gets ` MP <yes|no> (top <score>)` after the YOLOX part, and the total line gets `MP <n>/<total>`. Print scores with 3 decimals, so that a score just under the threshold does not show as the threshold value (this closes the Task 1 deferred minor about 2 decimals). When the file is missing, print one note at the start and leave out the MP column. The rest of the line format stays the same.
- [ ] **Step 6: Run the full suite.** Expected: PASS. Run `env/bin/python tools/get_person_model.py --mediapipe`, then `env/bin/python -I tools/occupancy_bench.py --camera 0 --frames 3` with no person in view. Record the MediaPipe time per frame (measured).
- [ ] **Step 7: Commit** with the message `Add the MediaPipe person detector to the bench tool for comparison`.
- [ ] **Step 8: Report.** The main session asks the user for one bench session, 12 frames each: lying under a blanket, lying without a blanket, and the empty room with the lights on and the bed with its blanket in view. Task 5b uses the printed top scores. Tasks 2–5 do not wait for this session.

### Task 2: Occupancy rule (pure)

**Files:**
- Create: `occupancy_rule.py`
- Test: `tests/test_occupancy_rule.py`

**Interfaces:**
- Produces: `class OccupancyRule: __init__(self, interval_s: float, confirm_s: float, fraction: float, hold_s: float)`, `add(self, result: str, at: float) -> None` (`result` is `"seen"`, `"not_seen"` or `"failed"`, and `at` is monotonic seconds), and `state(self, now: float) -> dict` with these keys:
  - `state`: `"occupied"`, `"not_seen"` or `"unknown"`
  - `camera_working`: bool
  - `last_seen_at`: float or None
  - `seen`: int (sightings in the confirmation window)
  - `checks`: int (checks in the window)
  - `needed`: int (`ceil(fraction × checks expected in confirm_s)`)
  - `held`: bool (true when occupied only because of the hold)
- Also produces (amendment, option C): `assume_occupied(self, at: float) -> None`. The rule enters `occupied`, and `last_seen_at` becomes `max(last_seen_at, at)`. It adds no check to the window, so `seen` and `checks` do not change. Repeated calls are safe.

Rule (from the spec, section 2):
- Entry needs a full window: the oldest check in the window is at least `confirm_s − interval_s` old. Then `seen / expected ≥ fraction`, where `expected = round(confirm_s / interval_s)`. With the defaults, `expected` = 12 and `needed` = 9.
- Once occupied, the room stays occupied while `now − last_seen_at < hold_s`, whatever the other checks give, including failures.
- The camera is not working when no check other than `"failed"` has arrived within `3 × interval_s`. Not working and not held gives `"unknown"`. Working, not entered and not held gives `"not_seen"`. No check at all gives `"unknown"`.
- Keep only the checks in the window. Memory is bounded.

- [ ] **Step 1: Write the failing tests.** Use `interval_s=10, confirm_s=120, fraction=0.75, hold_s=900`. Feed checks at t = 0, 10, 20, ….
  - `test_nine_of_twelve_enters`: 12 checks, 9 seen (misses at 20, 50, 80). At t=110, `state == "occupied"`.
  - `test_eight_of_twelve_does_not_enter`: 8 seen. At t=110, `state == "not_seen"`, `seen == 8`, `needed == 9`.
  - `test_short_visit_does_not_enter`: seen at t = 0..50 (6 checks), then not seen. At t=110, `not_seen`.
  - `test_window_must_be_full`: 6 checks, all seen (t = 0..50). At t=50, `not_seen`.
  - `test_hold_survives_missed_checks`: enter by t=110, then not seen from t=120 to t=1000. At t=1000, still `occupied` with `held` True (last seen at 110, 1000 − 110 = 890 < 900).
  - `test_hold_ends_after_900_s`: the same, at t=1010. `state == "not_seen"`.
  - `test_camera_failure_keeps_hold_then_unknown`: enter by t=110, then `"failed"` from t=120 to t=1010. At t=1000, `occupied` with `camera_working` False. At t=1010, `unknown`.
  - `test_failed_camera_before_entry_is_unknown`: only `"failed"` from t=0 to t=40. At t=40, `unknown`.
  - `test_no_checks_is_unknown`: `state(0)["state"] == "unknown"`.
  - `test_bounded_memory`: 10 000 checks. Internal storage holds at most `expected + 1` entries.
  - `test_assume_occupied_starts_hold`: `assume_occupied(0)`, then `"not_seen"` checks every 10 s from t=10. At t=890, `occupied` with `held` True. At t=900, `not_seen`.
  - `test_sighting_after_assume_extends_hold`: `assume_occupied(0)`, `"not_seen"` checks, one `"seen"` at t=300. At t=1100, `occupied`. At t=1200, `not_seen`.
  - `test_assume_is_not_a_check`: `assume_occupied(0)` with no checks. At t=0, `state == "occupied"`, `seen == 0`, `checks == 0`, and `camera_working` False.
  - `test_assume_earlier_than_last_sighting_keeps_later`: enter by t=110 (last seen at 110), then `assume_occupied(50)`. `last_seen_at == 110`.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement `OccupancyRule`.**
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** with the message `Add the occupancy rule: 9 of 12 checks to enter, 15-minute hold, camera failure`.

### Task 3: Camera worker, settings and monitor camera start-up

**Files:**
- Modify: `occupancy.py` (the whole `CameraOccupancy` class)
- Modify: `settings.py` (`RUNTIME_DEFAULTS`, `validate_runtime_settings`)
- Modify: `config/runtime.yaml` (document the new optional keys, with the defaults commented)
- Modify: `monitor.py` (camera start-up, the publish fields)
- Test: `tests/test_room_software.py` (replace `test_camera_interval_is_configurable_and_reports_observation_age`), `tests/test_runtime_settings.py`

**Interfaces:**
- Consumes: `PersonDetector`, `check_model`, `ModelError` (Task 1), and `OccupancyRule` (Task 2).
- Produces:
  - `CameraOccupancy(index, timing: dict, detector=None)`. `timing` holds the six runtime keys. With `detector=None` the worker builds `PersonDetector(timing["person_confidence"])` in its thread.
  - `CameraOccupancy.snapshot(now) -> dict`, which is the rule's `state(now)` dict.
  - `CameraOccupancy.record(result, at)`, which the worker calls and tests call directly.
  - `CameraOccupancy.assume_occupied(at)` (amendment, option C), which passes to the rule under the same lock as `record`. Test: `test_camera_assume_occupied_reaches_rule`, where `assume_occupied(0)` gives `snapshot(0)["state"] == "occupied"`.
  - `current(now)` and `observation_age(now)` are removed. Update the callers.

- [ ] **Step 1: Write the failing tests.**
  - `test_camera_feeds_rule`: `CameraOccupancy(0, timing, detector=stub)` with no thread started. Call `record("seen", t)` 12 times at a 10 s step. Then `snapshot(110)["state"] == "occupied"`.
  - In `tests/test_runtime_settings.py`: `RUNTIME_DEFAULTS` includes the six keys with the spec values. Each of these is refused with `ValueError`: `occupancy_confirm_s: 5` (shorter than the interval of 10), `occupancy_confirm_fraction: 1.5`, `occupancy_confirm_fraction: 0`, `person_confidence: 1`, `person_confidence: 0`.
  - `test_camera_mode_without_model_exits_with_hint`: run `monitor.py --port /dev/null --camera 0` with `MODEL_PATH` pointed at a missing file (monkeypatch, or a subprocess with an environment override, whichever the code allows). It exits non-zero, and stderr contains `tools/get_person_model.py`.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - The worker loop: capture one frame and call `detector.detect(frame)`. The result is `"seen"` or `"not_seen"`, and a capture failure or `cv2.error` gives `"failed"`. Release the capture and call `record`. The frame is never kept.
  - `monitor.py`: in camera mode, call `check_model()` before the monitor starts, and call `parser.error(str(error))` on `ModelError`.
  - `publish` sets these fields: `occupancy_camera` (the snapshot), `occupancy_observation_age_s` (now − the last check time, or None), and the automatic occupancy state. The source stays `camera`, `simulated` or `none`.
- [ ] **Step 4: Run the full suite.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `Use the YOLOX detector and occupancy rule in the camera worker; add the occupancy settings`.

### Task 4: Override resolution, monitor wiring and session reasons

**Files:**
- Create: `occupancy_override.py`
- Modify: `monitor.py` (read the override at start and at each fault check, resolve it in `publish`)
- Modify: `room_session.py` (the reasons and texts in `monitoring_state`, the `end_all` calls for occupancy, `air_quality_block`, `update_dust`, and a new `note_event(kind, message)`)
- Test: `tests/test_occupancy_override.py`, `tests/test_room_software.py`

**Interfaces:**
- Consumes: the snapshot dict (Task 3).
- Produces:
  - `MODES = ("auto", "occupied", "not_occupied")`.
  - `parse_override(raw) -> dict | None`. It returns `{mode, set_at, set_from, id}` or None for anything damaged, and for mode `auto`.
  - `resolve(automatic: str, override: dict | None, wall: float, duration_s: float) -> tuple[str, str | None, dict | None]`. It returns `(occupancy, source_override, info)`. `info` is `{mode, set_at, set_from, expires_at}` while a manual mode applies, and None otherwise. `source_override` is `"manual"` or None.
  - `RoomSession.note_event(kind: str, message: str) -> None` appends to `pending_events`.
  - Event kinds: `occupancy_override_set`, `occupancy_override_cleared` (Automatic chosen by hand), `occupancy_override_expired`.

- [ ] **Step 1: Write the failing tests.**
  - `test_manual_occupied_and_not_occupied_apply`: `resolve("not_seen", {mode: "occupied", set_at: 1000, …}, 1100, 900)[0] == "occupied"`. With `not_occupied` and an automatic `occupied`, the result is `"not_occupied"`.
  - `test_override_expires_at_900_s`: at wall 1899 it applies. At 1900 it returns the automatic state with `info` None.
  - `test_damaged_override_is_ignored`: `parse_override` returns None for `"x"`, `{}`, `{"mode": "maybe", "set_at": 1}`, `{"mode": "occupied"}`, and `{"mode": "occupied", "set_at": True}`.
  - `test_override_survives_restart_until_expiry`: a monitor-level test with a fake store holding an override set 300 s ago. The first publish applies it. With one set 1000 s ago, it does not apply, and no event is logged.
  - `test_override_events`: setting `occupied`, then `auto`, then `not_occupied` and letting it expire logs `occupancy_override_set`, `occupancy_override_cleared`, `occupancy_override_set` and `occupancy_override_expired`, in that order. Each message names the mode and the time.
  - `test_manual_occupied_seeds_camera_hold` (amendment, option C). Use a monitor-level test with a fake camera that records `assume_occupied` calls:
    - An `occupied` override set 300 s ago (wall clock) gives one call with `at == monotonic_now − 300`.
    - More publishes with the same `id` give no new call. A new `id` gives one new call.
    - `not_occupied` and `auto` give no call.
    - With no camera (serial mode without `--camera`), nothing is called and nothing raises.
  - In `tests/test_room_software.py`:
    - `occupancy="not_seen"` gives the reason `occupancy_not_seen` and the message `"No person seen. Limit monitoring is paused."`.
    - `occupancy="not_occupied"` gives `occupancy_manual` and `"Set to not occupied by hand. Limit monitoring is paused."`.
    - `"unknown"` keeps `occupancy_unknown`.
    - The alert-end text for `not_seen` reads `"because no person is seen"`. For manual it reads `"because the room was set to not occupied by hand"`.
    - Update `test_alert_end_by_occupancy_names_reason` only if its input changes.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - The monitor reads `store.read("occupancy_override")` at start and in `apply_controls`, and keeps the last parsed value.
  - When the request changes, the monitor logs set or cleared through `session.note_event`. When `resolve` first returns `info` None for a request that was applying, it logs expired.
  - `publish` sets `occupancy` and `occupancy_source` (`"manual"` while an override applies) and `occupancy_override` (`info`).
  - Demo mode uses `"occupied"` as the automatic state.
  - Option C: when an `occupied` request with a new `id` first applies (set while running, or found at start and not expired), call `camera.assume_occupied(monotonic_now − max(0, wall_now − set_at))` once, when a camera exists. Clock jumps make `wall_now − set_at` negative or large: clamp it at 0, and skip the call when it is `occupancy_override_s` or more (the request has expired anyway).
- [ ] **Step 4: Run the full suite.** Expected: PASS.
- [ ] **Step 5: Commit** with the message `Apply the manual occupancy override with a 15-minute expiry; name the occupancy pause reason`.

### Task 5: Dashboard control and page text

**Files:**
- Modify: `dashboard.py` (`POST /occupancy`, `system_health` occupancy entry, defaults)
- Modify: `templates/overview.html` (the override form), `templates/system.html` if needed
- Modify: `static/room.js` (occupancy text and tone, the System row), `static/room.css` (only if the form needs it)
- Test: `tests/test_dashboard.py`, `tests/test_online_dashboard.py`

**Interfaces:**
- Consumes: the status fields from Task 4: `occupancy`, `occupancy_source`, `occupancy_override`, `occupancy_camera`.
- Produces: `POST /occupancy` with the form field `mode` in `MODES` and `next`. It stores `{"mode", "set_at": time.time(), "set_from": "online" if online else "local", "id": uuid4().hex}` under `occupancy_override` and returns 303 to `back()`. A bad mode gives 400.

- [ ] **Step 1: Write the failing tests.**
  - `test_occupancy_override_is_stored_for_the_monitor`: POST mode `occupied` gives 303. `store.read("occupancy_override")["mode"] == "occupied"`, `set_from == "local"`, and `set_at` is within 5 s of now.
  - `test_occupancy_override_rejects_unknown_mode`: mode `maybe` gives 400, and nothing is stored.
  - `test_cross_site_occupancy_post_is_refused`: with `Sec-Fetch-Site: cross-site`, the result is 403.
  - In `tests/test_online_dashboard.py`: `/occupancy` gives 403 without sign-in, and 303 signed in with the CSRF token. The online request stores `set_from == "online"`.
  - `test_overview_has_occupancy_control`: the Overview page has a form with action `/occupancy` and three buttons with the values `auto`, `occupied` and `not_occupied`, labelled "Automatic (camera)", "Occupied" and "Not occupied". Online and not signed in, the buttons are disabled.
  - `test_health_occupancy_entry_reports_manual_and_camera`: `/api/room` `health.occupancy` includes `source`, `override` and `camera` from the status.
- [ ] **Step 2: Run** the tests. Expected: FAIL.
- [ ] **Step 3: Implement.** The `room.js` texts:
  - `occupied` from the camera: "Occupied". If `held` is true and `camera_working` is false: "Occupied · camera not working, held from last sighting at HH:MM".
  - `not_seen`: "No person seen", amber. While `seen > 0`, add "· person seen in S of N checks".
  - `unknown`: "Occupancy unknown", amber (unchanged).
  - Manual: "Occupied: set by hand at HH:MM. Returns to the camera at HH:MM." or "Not occupied: set by hand at HH:MM. Returns to the camera at HH:MM." Add "(online)" when `set_from` is online. `not_occupied` uses the amber tone.
  - The System Camera row shows the model name `YOLOX (OpenCV zoo)`, the last check result and the last sighting time.
  - Follow `DESIGN.md` for the form layout.
- [ ] **Step 4: Run the full suite.** Then run `monitor.py --demo` and `dashboard.py --demo`, set each mode, and check the Overview text. Take a screenshot for the report.
- [ ] **Step 5: Commit** with the message `Add the occupancy override control and the new occupancy text to the dashboard`.

### Task 5b: Set the person threshold from the bench data (waits for the user's bench session)

**Files:**
- Modify: `settings.py` (`RUNTIME_DEFAULTS["person_confidence"]`), `config/runtime.yaml` (the commented default), `person_detector.py` (the `PersonDetector` default, the same value)
- Test: `tests/test_runtime_settings.py` (the default value)

**Input:** the bench output of the user's session from Task 1b Step 8. The main session saves it in the SDD workspace as `bench-<date>.txt`.

- [ ] **Step 1: Apply the rule** in the spec section "Decision after the bench gate", part A. Write a table of each candidate `T` with the blanket count (≥ 9 of 12?) and the empty-room highest top score (below `T − 0.10`?). Put it in the report. Do this by counting the printed scores, not by eye.
- [ ] **Step 2:** If a `T` passes, update the test of the default first (RED), then the three default values (GREEN). If no `T` passes, change no code: the default stays 0.5, and the report says that option C carries the blanket case.
- [ ] **Step 3: Run the full suite.** Expected: PASS.
- [ ] **Step 4: Commit** with the message `Set the person threshold to <T> from the bench top scores` (only if code changed).
- [ ] **Step 5: Report** the table, the chosen `T`, and the MediaPipe counts beside the YOLOX counts. If MediaPipe gets 9 or more of 12 on the blanket and 0 of 12 on the empty room while YOLOX does not, say so. The main session takes the choice of a switch (option B) to the user. This task does not switch.

### Task 6: Documentation

**Files:**
- Modify: `README.md`, `README_HUMAN.md`, `reference_files/PYTHON_FILE_GUIDE.md`
- Modify: `docs/superpowers/specs/2026-11-20-occupancy-detector-override-design.md` (the status line only: implemented, with the date and the bench result)

- [ ] **Step 1:** In both READMEs, replace the HOG description with these items:
  - the detector and its licence, and the model download step
  - the confirmation and hold rule with the default values
  - the override and its 15-minute expiry
  - camera-failure behaviour
  - the new runtime keys
  - the limitation that the detector cannot tell the patient from a visitor
  - the bench result, with its date and measured numbers
  - the gate failure on the blanket (4/12), the chosen threshold and the scores that justify it (Task 5b), and the MediaPipe comparison counts
  - option C: a manual "Occupied" starts the camera hold, and after it expires the camera needs only one sighting per 15 minutes
- [ ] **Step 2:** In `PYTHON_FILE_GUIDE.md`, add `person_detector.py`, `occupancy_rule.py`, `occupancy_override.py` and the three tools (`get_person_model.py`, `occupancy_bench.py`, `mediapipe_person.py`), and record the new test count.
- [ ] **Step 3:** Run the full suite and record the count. Run `grep -n "HOG" README.md README_HUMAN.md`. Each hit must be a history or comparison line, not a description of the current detector.
- [ ] **Step 4: Commit** with the message `docs: occupancy detector, confirmation, hold and override`.
