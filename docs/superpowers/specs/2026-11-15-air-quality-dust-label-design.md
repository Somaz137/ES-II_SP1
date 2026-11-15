# Air quality, dust estimate and profile label design

Approved scope: the user decided on 15 November 2026 how the page shows air quality and dust, that their limits are system setup, and that the patient profile gets a short label. This step builds it. It extends the [dashboard data contract](2026-11-15-dashboard-data-contract-design.md) and the [local alarm](2026-11-15-local-alarm-design.md). Verification is software-only: automated tests, host C++ tests, two ESP32-S3 compiles and the simulator. Nothing here is verified on hardware.

## Decision that replaces the raw-signal rule

Until 15 November 2026 the rule was: gas resistance and dust voltage are raw signals only. The user replaced it on 15 November 2026:

- Air quality is Bosch's BSEC index, shown with a word band and labelled "Bosch estimate".
- Dust is an estimated concentration in µg/m³ with a word level, labelled "estimate".
- Raw gas resistance (`gas_ohms`) and raw dust voltage (`dust_mv`) stay stored, charted and available as system details.

## Constraints

- No new dependencies. No patient or system limit values invented by the software or its authors.
- A retained, calibrating or estimated value is never shown as a fresh measurement.
- The three alert families (communication, sensor, limit) stay separate.
- No "safe" or "unsafe" wording and no medical wording. Dust words are not official air-quality category names.

## Sources used

All sources are on this machine. Nothing was fetched.

- Accuracy. `bsec2/src/inc/bsec_datatypes.h` (BSEC2 1.10.2610), `bsec_output_t::accuracy`: "0 Stabilization / run-in ongoing", "1 Low accuracy, to reach high accuracy(3), please expose sensor once to good air (e.g. outdoor air) and bad air (e.g. box with exhaled breath) for auto-trimming", "2 Medium accuracy: auto-trimming ongoing", "3 High accuracy". The generic table says 0 "Sensor data is unreliable, the sensor must be calibrated", 1 "Reliability of virtual sensor is low, sensor should be calibrated", 2 "Medium reliability, sensor calibration or training may improve performance", 3 "High reliability".
- Index scale. The same header, `BSEC_OUTPUT_IAQ`: "The IAQ scale ranges from 0 (clean air) to 500 (heavily polluted air)", the background calibration "considers the recent measurement history (typ. up to four days) to ensure that IAQ=50 corresponds to typical good air and IAQ=200 indicates typical polluted air."
- Static index. The header says only "Unscaled indoor-air-quality estimate" for `BSEC_OUTPUT_STATIC_IAQ`. The library examples print it but do not say when to prefer it. This is not clear documentation, so the firmware keeps `BSEC_OUTPUT_IAQ`.
- Word bands. No local Bosch document lists word bands. The bands in `config/system.yaml` are the commonly cited bands of the BME680 datasheet. They are marked there as unverified against the Bosch datasheet.
- Dust sensitivity. `docs/SHARP_DUST_INTEGRATION.md` already cites Sharp's typical 0.5 V per 0.1 mg/m³, that is 5000 mV per mg/m³, and states that it is not a per-unit calibration. No local copy of the Sharp datasheet exists. The value is a named setting, marked "typical, unverified against the datasheet on this machine".

## Firmware record

The reading record's `bsec` block gains `iaq`: the `BSEC_OUTPUT_IAQ` signal with two decimals, or `null` when the signal is not finite or outside 0 to 500. The key is last, so older keys keep their place.

`{"type":"reading",...,"bsec":{"stabilization_status":1,"run_in_status":1,"iaq_accuracy":3,"iaq":57.25}}`

The host accepts records without `iaq` as before. `gas_readiness.GasReadiness` gains `iaq`. It is a finite number from 0 to 500, not a bool, and kept only when the three status fields are valid. Otherwise it is null. An invalid `iaq` does not make the reading incomplete.

## Air quality state

`status_record` publishes the latest reported `bsec_iaq` and `bsec_iaq_accuracy` (retained values, for system details). The session publishes `status["air_quality"]`:

| State | When |
|---|---|
| `current` | The BME680 reading is current (the existing `measurement_current` rule), the accuracy is 2 or 3 and an index was reported. |
| `calibrating` | The reading is current and the accuracy is 0 or 1. |
| `unavailable` | Otherwise: no current reading, or no index or accuracy reported. |

Threshold: accuracy 2 or 3 (`air_quality.IAQ_MIN_ACCURACY = 2`). Bosch calls 0 "unreliable" and 1 "low, sensor should be calibrated". At 2 Bosch calls it "medium reliability" with auto-trimming ongoing. The value is a project decision based on these words, not a Bosch recommendation.

`value` and `band` are null unless the state is `current`. The block also carries `name` ("Air quality index"), `unit` (""), `estimate` (true), `source` ("Bosch estimate"), `accuracy`, `limit`, `hold_s` and `check` (below).

## Dust estimate and baseline

The session publishes `status["dust_ugm3"]` with `state` `current`, `establishing_baseline` or `unavailable`, `value`, `level`, `baseline_mv`, `sensitivity_mv_per_mg_m3`, `name` ("Dust estimate"), `unit` ("µg/m³"), `estimate` (true), `source` ("estimate"), `limit`, `hold_s` and `check`. `status["dust"]["estimated_dust_ug_m3"]` carries the same value when current, otherwise null.

Estimate = max(0, sensor_mv − baseline_mv) × 1000 / sensitivity. It is never negative.

Baseline rule (`dust.DustBaseline`):

- The baseline is the lowest sensor voltage among fresh dust records in the last `baseline_window_s` (default 24 h). The current record is included, so the estimate of the lowest record is 0.
- Records are kept as one minimum per 60-second bucket. At most `baseline_window_s / 60` buckets are kept. The window is capped at 7 days.
- Before enough data exists the state is `establishing_baseline` and no estimate is shown. Enough data means an unbroken run of fresh records lasting at least `baseline_min_s` (default 10 min).
- The run is broken, and all history cleared, when the dust status is anything but `fresh` (dust error, stale, communication lost) or when two fresh records are more than `reading_gap_limit_s` apart (a board reset or a stopped stream). A monitor restart also starts again: the history is in memory only.
- A record that is not fresh, or older than `reading_gap_limit_s`, gives `unavailable`.

Known limit: a low outlier lowers the baseline and raises later estimates until it leaves the window. Calibration against a reference instrument is not part of this step.

## Word bands and levels

Display settings in `config/system.yaml`. They are project display defaults, not health standards. Each entry is `{up_to: <number>, word: <text>}`, ascending; the last entry has no `up_to`. A value takes the first entry whose `up_to` it does not exceed.

- Air quality: the Bosch words listed above, unverified against the datasheet.
- Dust: `low` up to 50 µg/m³, `raised` up to 150, `high` above. These words are deliberately not official category names.

## System limits

`config/system.yaml` is loaded and validated at start by `settings.load_system_settings`, like the other files. `settings.SYSTEM_DEFAULTS` holds the same values; a test keeps them equal. Per measurement: `upper_limit` and `hold_s`, both null (off) or both finite and positive; an air-quality limit at most 500. Dust also has `sensitivity_mv_per_mg_m3`, `baseline_window_s` and `baseline_min_s` (positive, the minimum not above the window, the window at most 7 days). The shipped file leaves both limits off.

`--demo` uses `settings.DEMO_SYSTEM_SETTINGS`. These are demonstration values, not recommendations: air quality 150 for 30 s, dust 100 µg/m³ for 30 s, baseline after 30 s. The serial monitor takes `--system` (default `config/system.yaml`). The old `--dust-baseline-mv` and `--dust-sensitivity` options are removed: the baseline is now automatic and the sensitivity is a setting.

## Checks and alerts

The sustained rule is the same as for patient limits: an alert is raised when the value stays above the limit for the hold time, while the room is occupied and the reading is current. Air quality is checked on each new BME680 reading. Dust is checked on each new dust record and uses the dust record's own freshness and gap.

Each block's `check` has `state` (`running`, `paused` or `off`), `reason` and `message`. Reasons in order: `no_limit` (off); `reading_not_current` (paused); `occupancy_unknown` (paused); `calibrating` or `index_unavailable` for air quality, `establishing_baseline` for dust (paused); null (running). A patient-profile change does not affect these checks. `limit_monitoring` keeps describing the patient limits.

Alerts and pending breaches appear in `limit_alerts` and `limit_pending` with the same keys as before, `metric` `air_quality` or `dust_ugm3`, `direction` `high`. They feed the local alarm like other limit alerts: level 2, silenced the same way. Events use the same kinds. A new kind, `limit_reset_estimate`, ends an alert when the index starts calibrating, stops being reported, or the dust baseline is lost. Example: "Air quality index above the configured limit of 150 for 30 s. Value 182."

Current values are stored as series `air_quality` and `dust_ugm3` only while their state is `current`.

## Profile label

The patient profile gets an optional `label`: a string of at most 40 characters, already trimmed, with no control or format characters. Empty is allowed. The form field `label` is trimmed; an empty label is not written to the file. `/api/room` returns `profile.label`, "" when unset. The page escapes it (Jinja autoescape, `textContent`). When the loaded profile changes after the first load, the session logs `profile_changed`, for example: `Patient profile changed. Label "Bed 3". Temperature 20 to 27 °C. Sustained duration 9 s.` No patient name field exists.

## Dashboard response

- `trends` gains `air_quality` and `dust_ugm3`. Every trend entry gains `estimate`. `limit_checked` is true for the two new series only when the published status shows a system limit.
- `status.air_quality` and `status.dust_ugm3` as above.
- The page shows each value with its state and word, "Bosch estimate" or "estimate", the system limits and check messages, and the label. It has no form for system limits. No styling changed.

## Simulator

`SimulatedTransport` reports accuracy 0 for the first 30 s, 1 until 45 s, then 3. The index is about 60, and 182 from 120 s to 210 s of each 300 s. The dust voltage stays near 920 to 1100 mV, and 1600 mV from 220 s to 280 s of each 300 s. With the demo settings this gives an air-quality alert and a dust alert.

## Open points

- Saving BSEC calibration state across power loss is out of scope. After each board reset the index starts calibrating again.
- Bosch word bands and the Sharp sensitivity are not checked against a datasheet on this machine.
- Whether `BSEC_OUTPUT_STATIC_IAQ` suits a fixed room device better is not settled by the local documentation.
