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
