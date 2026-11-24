#!/usr/bin/env python3
"""Read-only bench check of the board's serial lines: does the gas reading change,
does the dust input work. It never writes to the board.

This part holds the analysis only. Each line is a (seconds, text) pair.
"""
from collections import Counter
from dataclasses import dataclass
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dust import parse_dust  # noqa: E402
from serial_parser import parse_serial_line  # noqa: E402

# The constant gas resistance the board sent on 20 November.
STUCK_GAS_OHMS = 12917166.0

GAS_NEXT_STEP = ("Check the BME680 part. A constant value suggests a faulty "
                 "or non-genuine gas sensor.")
STUCK_TEXT = ("This matches the stuck value of 20 November "
              "(by the BME68x formula, a raw gas ADC of 0).")
DUST_NEXT_STEP = ("Check with a meter: Vcc 5 V on sensor pins 6 and 1, ground on pins 2 and 4, "
                  "Vo on pin 5, and the divider midpoint to GPIO5.")
REQUEST_NEXT_STEP = ("The board asked for its saved calibration. This tool does not send it. "
                     "Run the monitor to restore it.")


@dataclass(frozen=True)
class Check:
    name: str
    verdict: str  # "PASS" | "FAIL" | "NOT SEEN" | "INFO"
    detail: str
    next_step: str | None = None


def _parse(lines):
    """(time, parsed message, raw JSON object or None) for each text line."""
    out = []
    for at, text in lines:
        if not isinstance(text, str):
            continue
        try:
            raw = json.loads(text)
        except (ValueError, RecursionError):
            continue
        out.append((at, text, parse_serial_line(text), raw if isinstance(raw, dict) else None))
    return out


def _valid(parsed):
    return [(at, msg) for at, _, msg, _ in parsed if msg.kind == "valid_reading"]


def _readings_check(parsed):
    valid = _valid(parsed)
    incomplete = sum(1 for _, _, msg, _ in parsed if msg.kind == "incomplete_reading")
    errors = Counter(msg.message for _, _, msg, _ in parsed if msg.kind == "sensor_error")
    if len(valid) >= 2:
        interval = f"{(valid[-1][0] - valid[0][0]) / (len(valid) - 1):.1f} s"
    else:
        interval = "—"
    error_text = (", ".join(f"{m} ({n})" for m, n in errors.items())
                  if errors else "none")
    detail = (f"{len(valid)} valid readings, mean interval {interval}, "
              f"{incomplete} incomplete, sensor errors: {error_text}")
    return Check("Readings arrive", "PASS" if valid else "NOT SEEN", detail)


def _gas_check(parsed):
    values = [msg.measurements["gas_ohms"] for _, msg in _valid(parsed)]
    name = "Gas resistance changes"
    if len(values) < 2:
        return Check(name, "NOT SEEN", f"{len(values)} valid readings, need at least 2")
    distinct = len(set(values))
    detail = f"{distinct} distinct, min {min(values):.2f} ohm, max {max(values):.2f} ohm"
    if distinct > 1:
        return Check(name, "PASS", detail)
    if values[0] == STUCK_GAS_OHMS:
        detail += ". " + STUCK_TEXT
    return Check(name, "FAIL", detail, GAS_NEXT_STEP)


def _dust_check(parsed, floor_mv):
    records, at_zero, other_errors, below, sensor_mv = 0, 0, 0, 0, []
    seen = False
    for _, text, _, raw in parsed:
        result = parse_dust(text)
        if result is None:
            continue
        seen = True
        value, error = result
        if raw.get("type") == "dust_error" and raw.get("message") == "dust_input_at_zero":
            at_zero += 1
        elif raw.get("type") == "dust" and value is not None:
            records += 1
            sensor_mv.append(value)
        elif error is not None:
            other_errors += 1
        if value is not None and value < floor_mv:
            below += 1
    name = "Dust input"
    if not seen:
        return Check(name, "NOT SEEN", "no dust lines")
    span = (f"min {min(sensor_mv):.1f} mV, max {max(sensor_mv):.1f} mV"
            if sensor_mv else "min — mV, max — mV")
    detail = (f"{records} dust records, {at_zero} dust_input_at_zero, "
              f"{other_errors} other dust errors, {below} below the {floor_mv:g} mV floor, {span}")
    if any(v >= floor_mv for v in sensor_mv):
        return Check(name, "PASS", detail)
    return Check(name, "FAIL", detail, DUST_NEXT_STEP)


def _accuracy_check(parsed):
    valid = _valid(parsed)
    accuracies = [msg.gas.iaq_accuracy for _, msg in valid if msg.gas.iaq_accuracy is not None]
    highest = max(accuracies) if accuracies else "none"
    last_iaq = valid[-1][1].gas.iaq if valid else None
    last = "none" if last_iaq is None else f"{last_iaq:g}"
    return Check("Bosch accuracy", "INFO", f"highest {highest}, last index {last}")


def _bsec_check(parsed):
    kinds = [msg.kind for _, _, msg, _ in parsed]
    restored = []
    for _, _, msg, _ in parsed:
        if msg.kind == "bsec_state_restored" and msg.restore_ok not in restored:
            restored.append(msg.restore_ok)

    def seen(kind):
        return "seen" if kind in kinds else "not seen"

    restored_text = "seen (ok " + ", ".join(str(ok).lower() for ok in restored) + ")" \
        if restored else "not seen"
    detail = (f"request {seen('bsec_state_request')}, state saved {seen('bsec_state')}, "
              f"restored {restored_text}, save failed {seen('bsec_state_save_failed')}")
    next_step = REQUEST_NEXT_STEP if "bsec_state_request" in kinds else None
    return Check("BSEC state messages", "INFO", detail, next_step)


def analyse(lines: list[tuple[float, str]], floor_mv: float) -> list[Check]:
    """Five checks, always in the same order. Lines that do not parse are skipped."""
    parsed = _parse(lines)
    return [
        _readings_check(parsed),
        _gas_check(parsed),
        _dust_check(parsed, floor_mv),
        _accuracy_check(parsed),
        _bsec_check(parsed),
    ]


def breath_change(before: list[tuple[float, str]],
                  during: list[tuple[float, str]]) -> float | None:
    """Lowest gas_ohms during the breath as a percentage of the median before it."""
    before_ohms = [msg.measurements["gas_ohms"] for _, msg in _valid(_parse(before))]
    during_ohms = [msg.measurements["gas_ohms"] for _, msg in _valid(_parse(during))]
    if not before_ohms or not during_ohms:
        return None
    median = statistics.median(before_ohms)
    if median == 0:
        return None
    return 100 * min(during_ohms) / median


def exit_code(checks: list[Check]) -> int:
    """0 when every check that is not INFO passed, else 1."""
    return 0 if all(c.verdict == "PASS" for c in checks if c.verdict != "INFO") else 1


def format_report(checks: list[Check]) -> str:
    out = []
    for c in checks:
        out.append(f"{c.verdict:<8} {c.name}: {c.detail}")
        if c.next_step:
            out.append(f"  Next step: {c.next_step}")
    return "\n".join(out)
