# Occupancy: pretrained person detector, entry confirmation, hold and manual override

Date: 20 November 2026. Status: implemented (27 November 2026) on branch `feature/occupancy`, bench result: YOLOX passed standing 12/12, sitting 9/12 and lying 11/12, and failed lying under a blanket (4/12 on 20 November, 0/12 twice on 27 November). No threshold from 0.50 to 0.25 passed, so `person_confidence` stays 0.5 and a manual "Occupied" setting covers the blanket case.

## Intent

Patient-limit, air-quality and dust alerts start only while the room is occupied. Today the camera uses OpenCV's HOG people detector. It is trained on upright pedestrians. It can miss a patient who lies in bed. A missed patient gives "unknown" occupancy, and then no limit alert can start. This is the largest risk to the assessed task "sustained-breach alert".

The user also wants two protections against wrong occupancy:

- A short visit (for example, someone who enters to fetch something) must not mark the room occupied.
- A caregiver must be able to set the room occupied or not occupied by hand when the camera is wrong.

## Goals

1. Detect a person in any position (standing, sitting, lying, partly hidden) with a pretrained detector.
2. Mark the room occupied only after a person is seen for a confirmation time.
3. Keep the room occupied for a hold time after the last sighting, so one missed photo does not end a real alert.
4. Give the caregiver a manual override with three choices: Automatic (camera), Occupied, Not occupied. A manual choice returns to Automatic by itself after 15 minutes.

## Non-goals

- Telling the patient apart from a visitor. A visitor who stays longer than the confirmation time marks the room occupied. This is a stated limitation.
- Training or fine-tuning our own detector. Fine-tuning is a later step, only if the bench check fails.
- Any change to the limit rules themselves.

## Anti-goals (a failure even if it works)

- A camera frame saved to disk or sent anywhere.
- A manual setting that keeps alerts off with no visible sign on the page.
- A new pip package. OpenCV 4.11 (already pinned) runs the detector.

## Decisions by the user (20 November 2026)

- Direction: a pretrained detector through OpenCV's DNN module, with an occupancy hold. Approved.
- Entry confirmation: 2 minutes. Hold: 15 minutes after the last sighting.
- Manual override: three choices. Both manual choices return to Automatic after 15 minutes (the same length as the hold). The user first chose 1 hour, then changed it to 15 minutes.

## Approaches considered

| Approach | Trade-off | Result |
|---|---|---|
| Train our own detector | Needs thousands of labelled images of lying and sitting people, a GPU and many hours. Too large for a course project. | Rejected |
| Pretrained COCO detector (YOLOX) through `cv2.dnn` | COCO has people in many positions. No new package. The model file is about 35 MB (fp32). | **Chosen**, subject to the bench check |
| MediaPipe person detector from OpenCV's model zoo | It is small. But it comes from a pose pipeline that finds the person by the face and upper body, and its behaviour with a lying person is unclear. | Fallback, if YOLOX fails the bench check |
| MediaPipe package or another framework | New pip dependency. Needs course approval. | Rejected |

Model source: OpenCV model zoo, `object_detection_yolox_2022nov.onnx`. The zoo states Apache 2.0 for this model. The builder must read the licence file next to the model and record it.

## Design

### 1. Detector

- `occupancy.py` replaces HOG with a YOLOX person detector loaded by `cv2.dnn.readNet`. It keeps only COCO class 0 (person) above a confidence threshold, after non-maximum suppression. The default threshold is 0.5, as a setting.
- Each check captures one frame, runs the detector and keeps one result: `seen`, `not_seen` or `failed`. The frame is released at once. It is never written or sent.
- The camera check interval drops from 60 s to 10 s (`camera_interval_s` default 10). A laptop i7 runs one YOLOX inference in well under a second. The builder measures and records it.
- Model file: `tools/get_person_model.py` downloads the file to `models/` (git-ignored) and checks a pinned SHA-256. Camera mode refuses to start, with a clear message, when the file is missing or its hash is wrong. *My call:* this keeps a 35 MB binary out of git.

### 2. Occupancy rule (a pure module, no I/O)

The rule takes the check results with their times. It returns the automatic state.

- **Entry.** The room becomes `occupied` when a person was `seen` in at least 75 % of the checks in the last `occupancy_confirm_s` (default 120 s). At a 10 s interval, that is 9 of 12 checks. The window must be full: a run that is shorter than 120 s does not count.
- **Hold.** While the room is occupied, it stays `occupied` until no check has seen a person for `occupancy_hold_s` (default 900 s).
- **No person.** After the hold ends, the state is `not_seen`. The camera works but has not confirmed a person.
- **Camera failure.** A `failed` check counts as `not_seen` for the entry and the hold. When no check has succeeded for 3 intervals, the camera is "not working". User decision (20 November 2026): while the room is occupied, a camera failure does not end occupancy. The room stays `occupied` until the 15-minute hold, counted from the last sighting, ends. Limit alerts keep running. The page says, for example, "Camera not working. Occupancy held from the last sighting at 14:02." After the hold, the state is `unknown`. When the room is not occupied, a camera failure gives `unknown` after 3 intervals.
- **While confirming.** The status shows the progress, for example "Person seen in 7 of 12 checks".

`occupied` is the only state that allows limit alerts. All other states pause them, as `unknown` does today. The session rule `occupancy != "occupied"` stays.

**Page text and reasons per state.** *My call (builder check, 20 November 2026):* a missed patient must be visible, following the principle "the page states what it does not know".
- `not_seen` shows "No person seen" with the caution tone, the same tone as `unknown`. It does not show a calm "Not occupied".
- The pause and reset texts in `room_session.py` and the reason codes split by cause: `occupancy_not_seen` ("No person seen. Limit monitoring is paused."), `occupancy_unknown` (camera not working, or no camera), and `occupancy_manual` ("Set to not occupied by hand. Limit monitoring is paused."). Update the tests that match these texts.

### 3. Manual override

- The control is on the Overview page, next to the occupancy line. It is a form with three buttons: Automatic (camera), Occupied, Not occupied.
- `POST /occupancy` writes `occupancy_override` to the SQLite settings store: `{mode, set_at, id}`. `mode` is `auto`, `occupied` or `not_occupied`, and `set_at` is the wall-clock time. This uses the same pattern as silence and acknowledge. Online, the existing sign-in and CSRF gate applies.
- The monitor reads the request at each fault check. A manual mode applies until `set_at + occupancy_override_s` (default 900 s). After that time, the monitor uses the camera state again and logs the return to Automatic. A new request replaces the old one.
- **The effect of each mode:**
  - `occupied`: the room is occupied, whatever the camera says.
  - `not_occupied`: the room is not occupied. Limit alerts pause, and active limit alerts end, the same as `unknown` today.
  - `auto`: the camera rule decides.
- **Monitor restart.** *My call:* unlike silence and acknowledge, a stored manual setting is applied at monitor start if `set_at + occupancy_override_s` is still in the future. This way the page never shows a manual setting that the monitor ignores. An expired setting is ignored.
- The request also records where it came from: `set_from` is `local` or `online`. The online origin sets `online`.
- The camera keeps checking during a manual mode. When the manual mode ends, the camera state is already current.
- **Page text:** the page always says when the occupancy comes from a manual setting, who set it ("on this computer" or "online"), and when it returns to the camera. Example: "Occupied: set by hand at 14:02. Returns to the camera at 14:17." The text, not a colour, carries this.
- **Events:** the log records an override set, a return to Automatic set by hand, and an expiry, each with the mode and the time.
- The override works in demo mode and in serial mode without `--camera`. In serial mode without a camera, the Automatic state stays `unknown`, as today.

### 4. Status and settings

- The status record gains these fields: `occupancy` (`occupied`, `not_seen`, `unknown`, or `not_occupied`, which is used only for a manual setting), `occupancy_source` (`camera`, `manual`, `simulated` or `none`), `occupancy_override` (`{mode, set_at, set_from, expires_at}` or null) and `occupancy_camera` (last result, last sighting time and confirmation progress).
- `config/runtime.yaml` gains these optional keys, with defaults: `camera_interval_s` 10, `occupancy_confirm_s` 120, `occupancy_confirm_fraction` 0.75, `occupancy_hold_s` 900, `occupancy_override_s` 900, `person_confidence` 0.5. They are validated like the other runtime keys. Older files still load.
- The System page "Camera" row shows the model in use, the last check result and the time of the last sighting.

## Tests

- The occupancy rule: entry at exactly 9 of 12 and not at 8 of 12, a short visit (60 s) that does not enter, the hold across missed checks, expiry after 900 s, failures that lead to `unknown`.
- The detector wrapper: a stub network that returns known boxes. Person class only, threshold, suppression. No camera is needed.
- The override: set, replace, expiry at 900 s, `not_occupied` that ends active limit alerts, events written. The dashboard route: sign-in and CSRF online, 303 on success, refusal of a bad mode.
- The existing 667 tests must still pass.

## Bench check (the user, with the laptop webcam): a gate

*My call (builder check):* the bench check is the first task and a gate. The rule, override and page work start only after YOLOX passes.

- `tools/occupancy_bench.py` captures live frames and runs HOG and YOLOX on each frame. It prints one line per frame with both results. It stores no frame. HOG stays only in this tool, and `occupancy.py` no longer uses it.
- Record the detection rate for standing, sitting, lying on a bed or sofa, and lying under a blanket.
- Pass: YOLOX detects the person in at least 9 of 12 frames in each lying position. That is the same fraction as the entry rule.
- The detector sits behind one small interface (`detect(frame) -> bool`), so another model can replace it. MediaPipe is not built now. If YOLOX fails, the plan stops, and the MediaPipe fallback comes back to the user before any fine-tuning.

## Decision after the bench gate (23 November 2026)

Gate result (20 November 2026, laptop webcam, threshold 0.5, 12 frames each): standing 12/12, sitting 9/12, lying 11/12, **lying under a blanket 4/12 (fail)**, empty room 0/12. The blanket frames were nearly overexposed (mean brightness about 235 of 255).

The user chose options A and C, plus a MediaPipe comparison on the bench only (23 November 2026). Option B (switch the production detector to MediaPipe) is not chosen now.

### A. Threshold from measured top scores

- The bench tool prints the top YOLOX person score of each frame (commit `4d06e35`). The user runs one bench session: lying under a blanket, lying without a blanket, and the empty room with the lights on and the bed with its blanket in view. Each run has 12 frames.
- **Rule for the threshold `T`.** Try `T` = 0.50, 0.45, 0.40, 0.35, 0.30, 0.25, in that order. Pick the first `T` for which both are true:
  1. At least 9 of the 12 blanket frames have a top score ≥ `T`.
  2. The highest top score in all empty-room frames is below `T − 0.10`. The 0.10 margin guards against false sightings.
- If no `T` passes, `person_confidence` stays 0.5 and option C covers the blanket case.
- The chosen `T` becomes the default of `person_confidence`. The value and the scores that justify it are recorded in the README.

### C. A manual "Occupied" starts the camera hold

- When a manual `occupied` setting starts to apply, the monitor tells the camera rule that a person was assumed at the time of the setting (`set_at`, converted to the monitor's clock). The rule enters `occupied`, and the hold starts from that time.
- This does not add a check to the confirmation window. "Person seen in S of N checks" stays a count of real sightings.
- A later real sighting moves the hold forward as usual. When the manual setting expires after 15 minutes, the room stays occupied as long as the camera has seen the person at least once in the last 15 minutes. If the camera has not seen anyone since the setting, the hold ends at the same moment as the manual setting.
- Each new manual `occupied` request (a new `id`) does this once. A stored setting that is applied at monitor start does it too, with its original `set_at`. `not_occupied` and `auto` do not change the rule.
- Without a camera (demo mode, or serial mode without `--camera`), this has no effect.
- Use case: a caregiver who sees the patient under a blanket sets "Occupied" once. After that, the camera only needs one sighting every 15 minutes.

### MediaPipe comparison (bench only)

- The bench tool also runs the MediaPipe person detector from the OpenCV model zoo (`person_detection_mediapipe_2023mar.onnx`) through `cv2.dnn`. It prints its result and top score next to the YOLOX result. The model is downloaded to `models/` with a pinned SHA-256, the same way as YOLOX. No new pip package. Record its licence.
- MediaPipe code lives only in `tools/`. `occupancy.py` and the monitor do not use it.
- If MediaPipe does clearly better than YOLOX in the same runs, the choice of a switch (option B) goes back to the user.

## Left to the builder

- The exact YOLOX pre- and post-processing (input size, letterbox, output decoding). Follow the zoo's `demo.py`.
- The pinned download URL and its SHA-256.
- The exact wording of the page text, following `DESIGN.md` and the product principles.
