# BME680 gas heater: decision record (25 November 2026)

**Status:** open. No option chosen (25 November 2026). The user chooses.

**Scope:** the BME680 gas resistance and the Bosch air-quality index (BSEC IAQ). Temperature, humidity and pressure work and are not part of this decision.

## Problem

With the normal firmware (Bosch BSEC2 1.10.2610, low-power configuration `bme680_iaq_33v_3s_4d`), almost every gas reading is the same value, 12917166.00 ohm. By the BME68x formula this value is a raw gas ADC of 0 at gas range 0. It is not a measurement.

| Run (25 November 2026) | Firmware | Gas readings stuck at 12917166.00 ohm | Other gas values |
|---|---|---|---|
| Sensor check, 180 s | `f1a9dee` | 55 of 58 | 114682.80, 48249.22, 43419.32 ohm, 12 to 18 s after the first reading |
| Sensor check, 60 s, after the diagnostic | `f1a9dee` | 16 of 19 | minimum 32844 ohm |
| Sensor check, 60 s, after the sweep | `f1a9dee` | 16 of 19 | — |
| Sensor check, 180 s | `49029f2` | 55 of 58 | 133538.53, 38634.82, 30399.80 ohm, 12 to 18 s after the reset |

On 20 November 2026 (firmware `1c74995`) every reading for about 15 minutes was the same value.
Bosch accuracy reached only 1 in these short runs. In a longer monitor run (firmware `49029f2`, from 02:28:21) accuracy reached 2 at 02:40:50 and 3 at 02:41:50, and the board saved its state (`bsec_state_saved`, "accuracy 3, BSEC 2.6.1.0"). The gas reading stayed stuck: 552 of 556 stored gas readings from 02:28 to 02:56 were 12917166 ohm. The index stayed about 50 most of the time (272 of 307 stored index values round to 50), with short peaks after the first index (200 at 02:40:50) and after the I2C bus restart (385 at 02:50:21). So the Bosch index reaches accuracy 3 but has no meaning while the gas is stuck. The dashboard shows it as current. This is an open issue (no fix chosen).

## Findings

Sensor identity (diagnostic, 25 November 2026): only address 0x76 answered on the I2C bus. Chip id 0x61, variant 0 (the BME680 low-gas variant).

Diagnostic (forced mode, no BSEC, every 3 s, two settings alternating):

| Heater | Readings | Not stuck | gas_ohms min / median / max |
|---|---|---|---|
| 320 °C, 150 ms | 35 | 1 (the first one, heat_stab not set) | 23145 / 12917166 / 12917166 |
| 200 °C, 100 ms | 35 | 35 | 6405 / 52862 / 55405 |

Heater sweep (forced mode, no BSEC, 540 s, 20 cycles of 9 steps, 178 measurements, raw gas ADC read from registers 0x2A/0x2B):

| Setting | n | Real | Gas ADC 0 | Real values (kΩ) | Value of a failed reading |
|---|---|---|---|---|---|
| 200 °C / 150 ms | 19 | 19 | 0 | 33.3 to 34.9 | — |
| 240 °C / 150 ms | 19 | 19 | 0 | 21.1 to 22.3 | — |
| 260 °C / 150 ms | 20 | 20 | 0 | 18.4 to 21.3 | — |
| 280 °C / 150 ms | 20 | 1 | 19 | 64.5 (one value) | range 6: 201.8 kΩ |
| 300 °C / 150 ms | 20 | 3 | 17 | 750.6 to 778.4 | range 5: 403.4 kΩ |
| 320 °C / 150 ms | 20 | 0 | 20 | — | range 0: 12917.2 kΩ |
| 320 °C / 100 ms | 20 | 0 | 20 | — | range 0: 12917.2 kΩ |
| 320 °C / 50 ms | 20 | 0 | 20 | — | range 0: 12917.2 kΩ |
| 200 °C / 50 ms | 20 | 20 | 0 | 43.7 to 46.5 | — |

- From 200 to 260 °C, 78 of 78 readings were real (18.4 to 46.5 kΩ): 58 of 58 at 150 ms (200, 240 and 260 °C) and 20 of 20 at 200 °C / 50 ms.
- The threshold is between 260 °C (res_heat 106, idac 182 to 183) and 280 °C (res_heat 112, idac 188).
- At 320 °C a shorter heater time (100 ms, 50 ms) did not help. At 200 °C, 50 ms and 150 ms both worked.
- No carry-over: after a 320 °C failure, the next 200 °C / 50 ms reading was real 20 of 20 times.
- Every measurement had status 0xB0 (new data, GASM_VALID, HEAT_STAB). The status bits do not show the failure.
- No I2C errors, retries or recoveries in the sweep. The bus still answered at the end.
- The rare real values at 280 and 300 °C (64.5 kΩ, about 750 kΩ) are much higher than at 260 °C (18.9 kΩ median). A working metal-oxide layer normally drops in resistance as it gets hotter. This is general sensor behaviour, not measured here.
- The sweep cycle always rises in temperature. It cannot show whether 280 and 300 °C behave differently after a cool step.

## Inference

- The failure follows the heater set point, so the heater drive, and not the heater time.
- Two causes fit the data: a supply sag at the higher heater current, or a contact or sensing layer that fails when it is hot. The data cannot separate these. A meter on the BME680 supply during a 320 °C measurement, or the same sweep on a known-good BME680, would separate them.
- The BSEC configuration in use heats to about 320 °C. Reason: its readings show exactly 12917166 ohm (gas ADC 0 at range 0). In the sweep only the 320 °C steps gave this value. The 280 and 300 °C failures gave other values. The heater profile inside the Bosch configuration blob was not read.
- So the Bosch air-quality index cannot work with this module as it is.
- New evidence (25 November 2026, 02:49 to 02:59, firmware `49029f2`): the BME680 dropped off the I2C bus twice. At 02:49:20 it stopped; after two bus restarts it started again (02:50:03, from the RAM copy of the state). At 02:56:48 it stopped again; each restart after that (about every 30 s, 4 by 02:59) gave `bsec_initialization_failed`. Inference: a Wire restart is not always enough, and the drop-outs lean toward a hardware cause (supply or contacts). It is not proven. The sweep itself had no I2C errors.

## Options

### B: hardware

A person does one of these:

1. Adds a 10 µF capacitor (plus a 100 nF capacitor) across the BME680 power pins, close to the module.
2. Powers the BME680 from a stronger 3.3 V supply.
3. Replaces the BME680 module.

| | |
|---|---|
| Cost | Parts and a person at the bench. No code change. |
| Changes | Nothing in the code or the dashboard. BSEC and the Bosch index stay. |
| Result if it works | Real gas values at 320 °C. The Bosch index then has a meaning at accuracy 3. (Accuracy 3 and a state save already happened on 25 November on the stuck signal.) A restore from the laptop file can then be checked with a real state. If the cause is the supply or the contacts, the I2C drop-outs may also stop (inference). |
| Risk | Items 1 and 2 help only if the cause is a supply sag. If the sensing element itself fails, only item 3 helps. |

### C: software

Run the gas heater at or below 260 °C without BSEC, for example with the Bosch BME68x library in forced mode, as in the sweep.

| | |
|---|---|
| Cost | Firmware and host work. It needs a design first. |
| Changes | No BSEC, so no Bosch index, no Bosch accuracy and no BSEC state save. The gas resistance is real. The dashboard needs its own simpler indication, for example a change from a clean-air baseline, as for dust. The air-quality system limit, the "calibrating" state and the BSEC state feature would need a new meaning or removal. |
| Result | A working gas signal on this module. It is not a calibrated index. |
| Risk | A project-made indication has no Bosch validation. Its word bands and limits would be project defaults, not standards. |

No option is chosen. The two options do not exclude each other: B can be tried first, and C stays possible.

## How to check again after a change

1. Flash the normal firmware (the build commands are in the [firmware guide](../../../firmware/README.md#build-commands)).
2. Stop the monitor. Run `tools/sensor_check.py --port /dev/ttyACM0 --seconds 180`.
3. Expected result after a successful fix: "Gas resistance changes" PASS: more than one value and no reading equal to 12917166.00 ohm.
4. To see the heater threshold again, repeat the sweep. The sweep sketch is described in the heater-sweep report: the BME68x library in forced mode, no BSEC, one measurement every 3 s through the cycle 200/150, 240/150, 260/150, 280/150, 300/150, 320/150, 320/100, 320/50 and 200/50 (°C/ms), with the raw gas ADC and range read from registers 0x2A/0x2B. The sketch is not in the repository. The report and the scratch files are outside it.

## Evidence

- Heater sweep report, diagnostic report and hardware run report: `wt-bsec-state/.superpowers/sdd/2026-11-25-sensor-check/` (not in git).
- Flash and verify report for `49029f2`: `wt-sensor-fixes/.superpowers/sdd/2026-11-25-dust-led-and-i2c-restart/flash-report.md` (not in git).
- The [25 November verification record](../../../reference_files/LINUX_VERIFICATION_2026-11-25.md).
