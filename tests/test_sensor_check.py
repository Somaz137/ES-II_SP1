import importlib.util
import json
from pathlib import Path

from bsec_state_store import is_bsec_version

_PATH = Path(__file__).resolve().parent.parent / "tools" / "sensor_check.py"
_SPEC = importlib.util.spec_from_file_location("sensor_check", _PATH)
sensor_check = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sensor_check)
Check = sensor_check.Check


def reading(gas, acc=0, iaq=None):
    return json.dumps({
        "type": "reading", "temp_c": 21.0, "humidity_pct": 40.0, "pressure_hpa": 1000.0,
        "gas_ohms": gas,
        "bsec": {"stabilization_status": 0, "run_in_status": 0, "iaq_accuracy": acc, "iaq": iaq},
    })


def dust(mv):
    return json.dumps({"type": "dust", "sensor_mv": mv, "samples": 10, "rejected_samples": 0})


def dust_zero():
    return '{"type":"dust_error","message":"dust_input_at_zero"}'


def timed(texts):
    return [(float(i), text) for i, text in enumerate(texts)]


def check(checks, name):
    return next(c for c in checks if c.name == name)


def gas_check(texts):
    return check(sensor_check.analyse(timed(texts), 100), "Gas resistance changes")


def test_five_checks_in_order():
    names = [c.name for c in sensor_check.analyse([], 100)]
    assert names == ["Readings arrive", "Gas resistance changes", "Dust input",
                     "Bosch accuracy", "BSEC state messages"]


def test_varying_gas_passes():
    result = gas_check([reading(50000.0), reading(50210.5), reading(49980.0)])
    assert result.verdict == "PASS"
    assert "3 distinct" in result.detail


def test_constant_stuck_gas_fails_and_names_20_november():
    result = gas_check([reading(12917166.0)] * 3)
    assert result.verdict == "FAIL"
    assert "matches the stuck value of 20 November" in result.detail
    assert result.next_step.startswith("Check the BME680 part")


def test_other_constant_gas_fails_without_stuck_text():
    result = gas_check([reading(40000.0)] * 3)
    assert result.verdict == "FAIL"
    assert "20 November" not in result.detail


def test_one_reading_gas_is_not_seen():
    assert gas_check([reading(40000.0)]).verdict == "NOT SEEN"


def test_dust_at_zero_fails_with_meter_step():
    result = check(sensor_check.analyse(timed([dust_zero()] * 3), 100), "Dust input")
    assert result.verdict == "FAIL"
    assert "3 dust_input_at_zero" in result.detail
    assert "pins 6 and 1" in result.next_step


def test_dust_above_floor_passes():
    result = check(sensor_check.analyse(timed([dust(910.0)]), 100), "Dust input")
    assert result.verdict == "PASS"


def test_dust_only_below_floor_fails():
    result = check(sensor_check.analyse(timed([dust(40.0)]), 100), "Dust input")
    assert result.verdict == "FAIL"


def test_no_lines_gives_not_seen_everywhere():
    checks = sensor_check.analyse([], 100)
    assert [c.verdict for c in checks[:3]] == ["NOT SEEN"] * 3
    assert sensor_check.exit_code(checks) == 1


def test_sensor_errors_are_listed_with_counts():
    line = '{"type":"error","message":"bsec_initialization_failed"}'
    result = check(sensor_check.analyse(timed([line, line]), 100), "Readings arrive")
    assert result.verdict == "NOT SEEN"
    assert "bsec_initialization_failed (2)" in result.detail


def test_bsec_request_gives_restore_hint():
    assert is_bsec_version("2.6.1.0")
    line = '{"type":"bsec_state_request","bsec_version":"2.6.1.0"}'
    result = check(sensor_check.analyse(timed([line]), 100), "BSEC state messages")
    assert "This tool does not send it" in result.next_step


def test_accuracy_reports_highest_and_last_index():
    lines = [reading(50000.0, 0, None), reading(50001.0, 2, 41.0), reading(50002.0, 1, 44.5)]
    result = check(sensor_check.analyse(timed(lines), 100), "Bosch accuracy")
    assert result.verdict == "INFO"
    assert "highest 2" in result.detail
    assert "44.5" in result.detail


def test_breath_change_percent():
    before = timed([reading(100000.0), reading(100000.0), reading(102000.0)])
    during = timed([reading(60000.0), reading(80000.0)])
    assert sensor_check.breath_change(before, during) == 60.0


def test_breath_change_with_no_readings_is_none():
    assert sensor_check.breath_change([], []) is None


def test_exit_code_ignores_info():
    checks = [Check("a", "PASS", ""), Check("b", "PASS", ""), Check("c", "PASS", ""),
              Check("d", "INFO", ""), Check("e", "INFO", "")]
    assert sensor_check.exit_code(checks) == 0


def test_report_format():
    report = sensor_check.format_report(
        [Check("Gas resistance changes", "FAIL", "1 distinct", "Check it.")])
    assert report == "FAIL     Gas resistance changes: 1 distinct\n  Next step: Check it."


# --- command line -----------------------------------------------------------

import pytest  # noqa: E402
import serial  # noqa: E402

_CONFIG = str(Path(__file__).resolve().parent.parent / "config" / "system.yaml")


class FakePort:
    """Read-only fake: no write method, so a write raises AttributeError."""

    def __init__(self, texts, fail_after=None, error=None):
        self.queue = [t.encode("utf-8") + b"\n" for t in texts]
        self.fail_after = fail_after
        self.error = error
        self.reads = 0
        self.closed = False

    def readline(self):
        if self.fail_after is not None and self.reads >= self.fail_after:
            raise self.error
        self.reads += 1
        return self.queue.pop(0) if self.queue else b""

    def close(self):
        self.closed = True


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 1.0
        return self.now


def run(port, args, capsys):
    opened = []

    def opener(name, baud, timeout):
        opened.append((name, baud, timeout))
        return port

    code = sensor_check.main(["--port", "/dev/ttyFAKE", "--config", _CONFIG, *args],
                             opener=opener, clock=FakeClock())
    assert opened == [("/dev/ttyFAKE", 115200, 1)]
    return code, capsys.readouterr().out


def varying():
    return [reading(50000.0 + i) for i in range(5)] + [dust(910.0)]


def test_main_reports_and_returns_0_when_all_pass(capsys):
    port = FakePort(varying())
    code, out = run(port, ["--seconds", "20"], capsys)
    assert code == 0
    assert "This tool only reads; it sends nothing to the board." in out
    assert "PASS     Gas resistance changes" in out
    assert port.closed


def test_main_returns_1_on_stuck_gas(capsys):
    port = FakePort([reading(12917166.0)] * 4 + [dust(910.0)])
    code, out = run(port, ["--seconds", "20"], capsys)
    assert code == 1
    assert "FAIL     Gas resistance changes" in out


def test_busy_port_prints_one_line_and_exits_2(capsys):
    def opener(name, baud, timeout):
        raise serial.SerialException("[Errno 16] Device or resource busy")

    code = sensor_check.main(["--port", "/dev/ttyFAKE", "--config", _CONFIG],
                             opener=opener, clock=FakeClock())
    out = capsys.readouterr().out
    assert code == 2
    assert "Stop the monitor first" in out
    assert "Traceback" not in out
    assert len(out.strip().splitlines()) == 1


def test_port_closed_mid_run_still_prints_summary(capsys):
    port = FakePort(varying(), fail_after=2, error=serial.SerialException("gone"))
    code, out = run(port, ["--seconds", "10"], capsys)
    assert "The port closed after" in out
    assert "Readings arrive" in out
    assert port.closed


def test_ctrl_c_prints_summary(capsys):
    port = FakePort(varying(), fail_after=2, error=KeyboardInterrupt())
    code, out = run(port, ["--seconds", "10"], capsys)
    assert "Stopped early after" in out
    assert "Readings arrive" in out
    assert "Gas resistance changes" in out
    assert port.closed


def test_breath_step_prints_percentage(capsys):
    port = FakePort([reading(50000.0 + i) for i in range(12)])
    code, out = run(port, ["--seconds", "10", "--breath"], capsys)
    assert "Breathe on the BME680 for 5 seconds now." in out
    assert "INFO     Breath test: lowest gas resistance" in out


def test_breath_step_with_no_readings_says_so(capsys):
    port = FakePort([])
    code, out = run(port, ["--seconds", "3", "--breath"], capsys)
    assert "INFO     Breath test: no gas readings to compare." in out


def test_log_writes_each_line(tmp_path, capsys):
    texts = varying()
    log = tmp_path / "run.log"
    run(FakePort(texts), ["--seconds", "20", "--log", str(log)], capsys)
    logged = log.read_text(encoding="utf-8").splitlines()
    assert len(logged) == len(texts)
    for line, text in zip(logged, texts):
        assert line.endswith(text)


def test_bad_config_exits_2(tmp_path, capsys):
    code = sensor_check.main(["--port", "/dev/ttyFAKE", "--config", str(tmp_path / "none.yaml")],
                             opener=lambda *a, **k: pytest.fail("port opened"),
                             clock=FakeClock())
    out = capsys.readouterr().out
    assert code == 2
    assert out.startswith("Cannot read")


def test_seconds_must_be_positive(capsys):
    with pytest.raises(SystemExit) as stop:
        sensor_check.main(["--port", "/dev/ttyFAKE", "--seconds", "0"])
    assert stop.value.code == 2
