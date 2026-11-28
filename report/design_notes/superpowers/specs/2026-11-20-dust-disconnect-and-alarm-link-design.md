# Dust sensor "not connected" and LED blink when the laptop link is lost

Date: 20 November 2026. Status: short design, for approval. Two small changes, approved in principle by the user on 20 November 2026.

## A. Dust sensor "not connected" (host only)

**Why.** On 17 November, with nothing wired to GPIO4, the dust input read about 870 to 930 mV and was accepted as a fresh reading. A missing sensor looked like a working one.

**Finding.** The documented wiring has a 2:1 divider with 10 kΩ from GPIO4 to ground. With the divider wired, that resistor pulls the pin to about 0 V when the sensor is missing. The 17 November reading had no divider. Sharp's typical clean-air output is about 0.9 V, so a working sensor stays well above 100 mV.

**Approaches.** We considered three: a host voltage floor (chosen), an extra pull-down resistor (not needed, because the divider already acts as one), and a firmware check with the sensor LED on and off (more work, kept in reserve if the bench check fails).

**Design.**
- New setting `dust.disconnected_below_mv` in `config/system.yaml`, default 100 (sensor-side mV, after the divider is undone).
- A dust record below the floor is not a reading. It gives no estimate, and it does not go into the clean-air baseline. It does not reset the "fresh record" time.
- When there have been no records at or above the floor for the existing sensor timeout (`sensor_error_timeout_s`, 120 s), the dust status is `not_connected` and the dust fault alert is active. That lights the LED (level 1), the same as other faults. The page says "Dust sensor not connected (reading below 100 mV)".
- One record at or above the floor clears the fault. The baseline then needs its normal 10 minutes of unbroken fresh records.
- Tests: below, at and above the floor, the fault after 120 s, recovery, and the baseline not fed.
- Bench check: wire the divider, unplug the sensor, and confirm the reading is below 100 mV.

**Builder finding (20 November 2026):** the firmware rejects 0 mV samples, so a missing sensor at about 0 V arrived as a generic dust_error. The board now sends dust_error `dust_input_at_zero` when more than half the samples in a window read 0, and the host treats it, and a 0 mV reading, as below the floor.

## B. LED blink when the laptop link is lost (board only)

**Why.** The board does not decide alerts. The laptop decides them and sends `ALARM,<level>` on every change and at every fault check (every 5 s). If the cable comes out, or the laptop sleeps or stops, the board keeps its last state, and nothing shows the failure.

**Approaches.** We considered three: do nothing, blink the LED (chosen by the user), or blink the LED and beep (rejected because it wakes the patient each time the laptop restarts).

**Design.**
- New constant `ROOM_ALARM_LINK_TIMEOUT_MS` in `bsec_board_config.h`, default 30000 (6 missed host commands).
- If no valid `ALARM` command has arrived for that time, the board enters "link lost". The LED blinks 1 s on and 1 s off. A steady LED keeps its present meaning, the alarm.
- **Buzzer:** it keeps its last commanded state. If an alarm was sounding when the link was lost, it keeps sounding, because a real alert must not go quiet when the laptop stops. If it was off, it stays off. (User decision, 20 November 2026.)
- The count starts at boot. A board that never hears from the laptop blinks after 30 s.
- The next valid command ends "link lost" and applies the commanded level. Malformed lines do not count as commands.
- The board prints no new line for this, because the laptop cannot read it anyway.
- The logic goes in a pure function in `alarm_command.h`, for example `alarmLed(level, msSinceCommand, nowMs)`, tested in `firmware/tests/test_alarm_command.cpp` with g++. The `millis()` wrap must be handled.
- Bench check (with the LED wired): unplug USB power to the laptop side or stop `monitor.py`, and confirm the blink starts after about 30 s and stops at the next command.
- Docs: the firmware guide and the README local-alarm section.
