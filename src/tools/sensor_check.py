#!/usr/bin/env python3
"""Read-only bench check of the board's serial lines: does the gas reading change,
does the dust input work. It never writes to the board.

Usage:
    env/bin/python src/tools/sensor_check.py --port /dev/ttyACM0 [--seconds 120] [--breath] [--log FILE]

Exit codes: 0 all checks pass, 1 a check failed or was not seen, 2 port, config or log file error.
The analysis works on (seconds, text) pairs. The serial loop only collects them.
"""
import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

import serial

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dust import parse_dust  # noqa: E402
from serial_parser import parse_serial_line  # noqa: E402
from settings import load_system_settings  # noqa: E402

_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "system.yaml"
BREATH_SECONDS = 30

# The constant gas resistance the board sent on 20 November.
STUCK_GAS_OHMS = 12917166.0

GAS_NEXT_STEP = ("The gas element of this BME680 is faulty (confirmed 28 November 2026, "
                 "see the README section \"BME680 gas: decision\"). "
                 "Only a new module fixes it.")
STUCK_TEXT = ("This matches the stuck value of 20 November "
              "(by the BME68x formula, a raw gas ADC of 0).")
DUST_NEXT_STEP = ("Check with a meter: Vcc 5 V on sensor pins 6 and 1, ground on pins 2 and 4, "
                  "Vo on pin 5, and the divider midpoint to GPIO5.")
DUST_SAMPLE_NEXT_STEP = ("The board could not sample the dust input. "
                         "Reset the board and run again.")
WIRING_NEXT_STEP = "Check the BME680 wiring (I2C SDA GPIO8, SCL GPIO9) and its power."
SHARED_PORT_TEXT = ("Stop the monitor first: two programs on one port "
                    "each get only part of the lines.")
NO_LINES_TEXT = "No lines came. Check that the cable is in the CH343 port and that the board runs."
REQUEST_NEXT_STEP = ("The board asked for its saved calibration. This tool does not send it. "
                     "Run the monitor to restore it.")


@dataclass(frozen=True)
class Check:
    name: str
    verdict: str  # "PASS" | "FAIL" | "NOT SEEN" | "INFO"
    detail: str
    next_step: str | None = None


def _count(n, word):
    """'1 reading', '2 readings'."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


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
    detail = (f"{_count(len(valid), 'valid reading')}, mean interval {interval}, "
              f"{incomplete} incomplete, sensor errors: {error_text}")
    if valid:
        return Check("Readings arrive", "PASS", detail)
    return Check("Readings arrive", "NOT SEEN", detail, WIRING_NEXT_STEP if errors else None)


def _gas_check(parsed):
    values = [msg.measurements["gas_ohms"] for _, msg in _valid(parsed)]
    name = "Gas resistance changes"
    stuck = sum(1 for v in values if v == STUCK_GAS_OHMS)
    if stuck:
        # A raw gas ADC of 0 is not a real measurement, so one such reading fails the check.
        verb = "matches" if stuck == 1 else "match"
        detail = (f"{stuck} of {_count(len(values), 'reading')} {verb} the stuck value of "
                  f"20 November, {len(set(values))} distinct, min {min(values):.2f} ohm, "
                  f"max {max(values):.2f} ohm. {STUCK_TEXT}")
        return Check(name, "FAIL", detail, GAS_NEXT_STEP)
    if len(values) < 2:
        return Check(name, "NOT SEEN", f"{_count(len(values), 'valid reading')}, need at least 2")
    distinct = len(set(values))
    detail = f"{distinct} distinct, min {min(values):.2f} ohm, max {max(values):.2f} ohm"
    if distinct > 1:
        return Check(name, "PASS", detail)
    return Check(name, "FAIL", detail, GAS_NEXT_STEP)


def _dust_check(parsed, floor_mv):
    records, at_zero, below, sensor_mv = 0, 0, 0, []
    other_errors = Counter()
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
            message = raw.get("message")
            if raw.get("type") != "dust_error":
                message = "invalid sensor_mv"
            elif not isinstance(message, str):
                message = "dust_error"
            other_errors[message] += 1
        if value is not None and value < floor_mv:
            below += 1
    name = "Dust input"
    if not seen:
        return Check(name, "NOT SEEN", "no dust lines")
    span = (f"min {min(sensor_mv):.1f} mV, max {max(sensor_mv):.1f} mV"
            if sensor_mv else "min — mV, max — mV")
    error_text = (", ".join(f"{m} ({n})" for m, n in other_errors.items())
                  if other_errors else "none")
    detail = (f"{_count(records, 'dust record')}, {at_zero} dust_input_at_zero, "
              f"other dust errors: {error_text}, {below} below the {floor_mv:g} mV floor, {span}")
    if any(v >= floor_mv for v in sensor_mv):
        return Check(name, "PASS", detail)
    if not records and not at_zero:
        # Only acquisition errors: the board did not sample, so a meter check comes later.
        return Check(name, "FAIL", detail, DUST_SAMPLE_NEXT_STEP)
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


def port_holders(port: str, proc: str = "/proc") -> list[int]:
    """Pids of other processes with an open file descriptor on the port device.
    pyserial 3.5 and the monitor do not lock the port, so the open alone does not tell."""
    target = os.path.realpath(port)
    holders = []
    try:
        entries = os.listdir(proc)
    except OSError:
        return []
    for entry in entries:
        if not entry.isdigit() or int(entry) == os.getpid():
            continue
        fd_dir = os.path.join(proc, entry, "fd")
        try:
            fds = os.listdir(fd_dir)
        except OSError:  # PermissionError, FileNotFoundError: not ours to read, or gone
            continue
        for fd in fds:
            try:
                link = os.readlink(os.path.join(fd_dir, fd))
            except OSError:
                continue
            if link == target:
                holders.append(int(entry))
                break
    return sorted(holders)


def listen(port, seconds: float, clock, log=None) -> tuple[list[tuple[float, str]], str | None]:
    """Read lines for `seconds`. Return the lines and a stop note, or None for a full run."""
    lines = []
    pending = b""
    start = clock()
    try:
        while clock() - start < seconds:
            pending += port.readline()
            if not pending.endswith(b"\n"):
                continue  # empty read, or a line cut at the 1 s timeout: wait for the rest
            text = pending.decode("utf-8", errors="replace").strip()
            pending = b""
            if not text:
                continue
            lines.append((clock(), text))
            if log is not None:
                log.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")
    except KeyboardInterrupt:
        return lines, f"Stopped early after {clock() - start:.0f} s."
    except (serial.SerialException, OSError):
        return lines, f"The port closed after {clock() - start:.0f} s."
    return lines, None


def _positive_seconds(value):
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("must be a finite number more than 0")
    return seconds


def _arguments(argv):
    parser = argparse.ArgumentParser(
        description="Read the board's serial lines and check the gas and dust readings. "
                    "This tool only reads; it sends nothing to the board.")
    parser.add_argument("--port", required=True, help="serial port, for example /dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--seconds", type=_positive_seconds, default=120.0,
                        help="listen time in seconds (default 120)")
    parser.add_argument("--breath", action="store_true",
                        help="after the listen time, ask for a breath on the BME680 "
                             f"and listen {BREATH_SECONDS} s more")
    parser.add_argument("--log", metavar="FILE", help="write each line with a timestamp")
    parser.add_argument("--config", default=str(_DEFAULT_CONFIG),
                        help="system settings file (default src/config/system.yaml)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None, opener=serial.Serial, clock=time.monotonic,
         proc: str = "/proc") -> int:
    args = _arguments(argv)
    try:
        floor = float(load_system_settings(args.config)["dust"]["disconnected_below_mv"])
    except Exception as error:  # noqa: BLE001 - any config problem ends the run
        print(f"Cannot read {args.config}: {error}")
        return 2
    holders = port_holders(args.port, proc)
    if holders:
        print(f"{args.port} is open in another program (pid {holders[0]}). {SHARED_PORT_TEXT}")
        return 2
    try:
        # exclusive=True: a second sensor_check run cannot open the same port.
        port = opener(args.port, args.baud, timeout=1, exclusive=True)
    except (serial.SerialException, OSError) as error:
        print(f"Cannot open {args.port}: {error}. {SHARED_PORT_TEXT} "
              "Check that the cable is in the CH343 port.")
        return 2
    log = None
    try:
        if args.log:
            try:
                log = open(args.log, "w", encoding="utf-8")
            except OSError as error:
                print(f"Cannot write {args.log}: {error}")
                return 2
        print(f"Listening on {args.port} for {args.seconds:g} s. "
              "This tool only reads; it sends nothing to the board.")
        lines, note = listen(port, args.seconds, clock, log)
        if args.breath and note is None:
            print("Breathe on the BME680 for 5 seconds now.")
            during, note = listen(port, BREATH_SECONDS, clock, log)
            change = breath_change(lines, during)
            lines += during
            if change is None:
                print("INFO     Breath test: no gas readings to compare.")
            else:
                print(f"INFO     Breath test: lowest gas resistance {change:.0f}% "
                      "of the value before.")
        if note:
            print(note)
        count = f"Lines received: {len(lines)}."
        print(f"{count} {NO_LINES_TEXT}" if not lines else count)
        checks = analyse(lines, floor)
        print(format_report(checks))
        return exit_code(checks)
    finally:
        if log is not None:
            log.close()
        port.close()


if __name__ == "__main__":
    sys.exit(main())
