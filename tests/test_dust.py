import json
from types import SimpleNamespace
import pytest
from dust import parse_dust
from monitoring_state import create_monitoring_state, process_serial_line, evaluate_monitoring_faults
from status_output import status_record

def output(state, now):
    return status_record(state, now, SimpleNamespace(connected=True, last_error=None), monotonic_origin=0, utc_origin=0)

@pytest.mark.parametrize("value", [None, True, "900", -1, 0, 5501, float("nan"), float("inf")])
def test_invalid(value):
    assert parse_dust(json.dumps({"type":"dust", "sensor_mv":value}))[0] is None

def test_retention_and_independent_missing_bme():
    state = create_monitoring_state(0, 120, 120)
    state = process_serial_line(state, '{"type":"dust","sensor_mv":900}', 1)
    state = process_serial_line(state, '{"type":"dust_error"}', 2)
    assert output(state, 2)["dust"]["sensor_mv"] == 900
    state = process_serial_line(state, '{"type":"dust","sensor_mv":950}', 121)
    status = output(state, 121)
    assert status["sensor_alert_active"]
    assert status["dust"]["status"] == "fresh"
    assert state.reading.last_reading is None

def test_missing_dust_and_recovery():
    state = create_monitoring_state(0, 120, 120)
    bme = '{"type":"reading","temp_c":25,"humidity_pct":40,"pressure_hpa":1000,"gas_ohms":10000}'
    state = process_serial_line(state, bme, 119)
    assert output(state, 120)["dust"]["alert_active"]
    state = process_serial_line(state, '{"type":"dust","sensor_mv":900}', 121)
    assert not output(state, 121)["dust"]["alert_active"]
    assert state.reading.last_reading.received_at == 119
    state = evaluate_monitoring_faults(state, 241)
    assert output(state, 241)["dust"]["status"] == "communication_lost"


def test_calibration_units_and_floor():
    from dust import estimate_dust
    assert estimate_dust(1400, 900, 5000) == 100
    assert estimate_dust(800, 900, 5000) == 0
    with pytest.raises(ValueError):
        estimate_dust(900, 900, 0)


def test_firmware_dust_limit_matches_host_limit():
    from pathlib import Path
    import re
    header = (Path(__file__).resolve().parents[1] / "firmware" / "sharp_dust_limits.h").read_text()

    def constant(name):
        return int(re.search(rf"constexpr uint32_t {name} = (\d+);", header).group(1))

    largest = constant("ROOM_DUST_MAX_ADC_MV") * constant("ROOM_DUST_DIVIDER_RATIO")
    assert largest == 5500
    assert parse_dust(json.dumps({"type": "dust", "sensor_mv": float(largest)})) == (largest, None)
    assert parse_dust(json.dumps({"type": "dust", "sensor_mv": largest + 0.1}))[0] is None


def test_baseline_needs_an_unbroken_run_then_is_the_lowest_voltage():
    from dust import DustBaseline
    baseline = DustBaseline(window_s=3600, min_s=30, gap_s=6)
    for at, mv in [(0, 950), (3, 900), (6, 980)]:
        baseline.add(mv, at)
    assert baseline.value(6) is None  # 6 s of data: still establishing
    for at in range(9, 31, 3):
        baseline.add(1000, at)
    assert baseline.value(30) == 900


def test_baseline_forgets_voltages_older_than_the_window():
    from dust import DustBaseline
    baseline = DustBaseline(window_s=600, min_s=30, gap_s=6)
    baseline.add(800, 0)
    for at in range(3, 901, 3):
        baseline.add(950, at)
    assert baseline.value(900) == 950


def test_baseline_restarts_after_a_gap_or_a_reset():
    from dust import DustBaseline
    baseline = DustBaseline(window_s=3600, min_s=30, gap_s=6)
    for at in range(0, 61, 3):
        baseline.add(900, at)
    assert baseline.value(60) == 900
    baseline.add(1000, 70)  # 10 s since the last record: the board may have restarted
    assert baseline.value(70) is None
    for at in range(73, 101, 3):
        baseline.add(1000, at)
    assert baseline.value(100) == 1000
    baseline.reset()  # a dust fault clears everything
    assert baseline.value(100) is None


def test_baseline_memory_is_bounded_by_the_window():
    from dust import DustBaseline
    baseline = DustBaseline(window_s=600, min_s=30, gap_s=6)
    for at in range(0, 7200, 3):
        baseline.add(900 + at % 7, at)
    assert len(baseline.buckets) <= 11


def test_estimate_from_the_tracked_baseline_is_never_negative():
    from dust import DustBaseline, estimate_dust
    baseline = DustBaseline(window_s=3600, min_s=0.001, gap_s=6)
    baseline.add(920, 0)
    baseline.add(1420, 3)
    assert estimate_dust(1420, baseline.value(3), 5000) == 100
    assert estimate_dust(920, baseline.value(3), 5000) == 0
