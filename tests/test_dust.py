import json
from types import SimpleNamespace
import pytest
from dust import parse_dust
from monitoring_state import create_monitoring_state, process_serial_line, evaluate_monitoring_faults
from status_output import status_record

def output(state, now):
    return status_record(state, now, SimpleNamespace(connected=True, last_error=None), monotonic_origin=0, utc_origin=0)

@pytest.mark.parametrize("value", [None, True, "900", -1, -0.1, 5501, float("nan"), float("inf")])
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


# Dust floor: a reading below the floor means the sensor is not connected.

def test_record_below_floor_is_not_a_reading():
    from dust import DUST_BELOW_FLOOR, DustState, record_dust
    state = record_dust(DustState(floor_mv=100.0), (920.0, None), 1)
    state = record_dust(state, (99.0, None), 4)
    assert state.received_at == 1 and state.last_voltage_mv == 920.0
    assert state.diagnostic == DUST_BELOW_FLOOR
    assert DUST_BELOW_FLOOR == "Dust reading below the not-connected floor."


def test_record_at_floor_is_a_reading():
    from dust import DustState, record_dust
    state = record_dust(DustState(floor_mv=100.0), (100.0, None), 5)
    assert state.received_at == 5 and state.last_voltage_mv == 100.0 and state.diagnostic is None


def below_floor_only(until):
    state = create_monitoring_state(0, 120, 120, dust_floor_mv=100.0)
    t = 0
    while t <= until:
        state = process_serial_line(state, '{"type":"dust","sensor_mv":50}', t)
        t += 3
    return state


def test_not_connected_after_timeout():
    state = below_floor_only(119)
    dust = output(state, 119)["dust"]
    assert dust["status"] == "sensor_error" and not dust["alert_active"]
    assert dust["floor_mv"] == 100.0
    dust = output(state, 120)["dust"]
    assert dust["status"] == "not_connected" and dust["alert_active"]
    assert dust["sensor_mv"] is None and dust["age_s"] is None


def test_recovery_clears_not_connected():
    state = below_floor_only(120)
    assert output(state, 121)["dust"]["status"] == "not_connected"
    state = process_serial_line(state, '{"type":"dust","sensor_mv":920}', 122)
    dust = output(state, 122)["dust"]
    assert dust["status"] == "fresh" and not dust["alert_active"]


def test_alternating_around_floor_never_faults():
    state = create_monitoring_state(0, 120, 120, dust_floor_mv=100.0)
    for step, t in enumerate(range(0, 301, 3)):
        value = 99 if step % 2 == 0 else 101
        state = process_serial_line(state, json.dumps({"type": "dust", "sensor_mv": value}), t)
        status = output(state, t)["dust"]
        assert status["status"] != "not_connected" and not status["alert_active"]


# A sensor at about 0 V: a 0 mV record and the board's dust_input_at_zero report
# count as below the floor; a generic dust_error does not.

ZERO_ERROR = '{"type":"dust_error","message":"dust_input_at_zero"}'
GENERIC_ERROR = '{"type":"dust_error","message":"dust_acquisition_unavailable"}'


def test_zero_mv_parses_as_a_below_floor_reading():
    from dust import DUST_BELOW_FLOOR, DustState, record_dust
    assert parse_dust(json.dumps({"type": "dust", "sensor_mv": 0})) == (0.0, None)
    state = record_dust(DustState(floor_mv=100.0), (920.0, None), 1)
    state = record_dust(state, parse_dust(json.dumps({"type": "dust", "sensor_mv": 0})), 4)
    assert state.received_at == 1 and state.last_voltage_mv == 920.0
    assert state.diagnostic == DUST_BELOW_FLOOR


def test_input_at_zero_error_is_a_below_floor_record():
    from dust import DUST_BELOW_FLOOR, DustState, record_dust
    state = record_dust(DustState(floor_mv=100.0), (920.0, None), 1)
    state = record_dust(state, parse_dust(ZERO_ERROR), 4)
    assert state.received_at == 1 and state.last_voltage_mv == 920.0
    assert state.diagnostic == DUST_BELOW_FLOOR
    state = record_dust(state, parse_dust(GENERIC_ERROR), 7)
    assert state.diagnostic == "Dust acquisition failed."


def lines_only(lines, until):
    state = create_monitoring_state(0, 120, 120, dust_floor_mv=100.0)
    for step, t in enumerate(range(0, until + 1, 3)):
        state = process_serial_line(state, lines[step % len(lines)], t)
    return state


@pytest.mark.parametrize("lines", [
    ['{"type":"dust","sensor_mv":0}'],
    [ZERO_ERROR],
    ['{"type":"dust","sensor_mv":40}', ZERO_ERROR],
])
def test_sensor_at_zero_volts_is_not_connected_without_flipping(lines):
    state = lines_only(lines, 117)
    assert output(state, 119)["dust"]["status"] == "sensor_error"
    state = lines_only(lines, 120)
    assert output(state, 120)["dust"]["status"] == "not_connected"
    for step, t in enumerate(range(123, 301, 3)):
        state = process_serial_line(state, lines[step % len(lines)], t)
        dust = output(state, t)["dust"]
        assert dust["status"] == "not_connected" and dust["alert_active"]
    state = process_serial_line(state, '{"type":"dust","sensor_mv":920}', 302)
    dust = output(state, 302)["dust"]
    assert dust["status"] == "fresh" and not dust["alert_active"]


def test_generic_dust_error_only_is_still_stale():
    state = lines_only([GENERIC_ERROR], 150)
    dust = output(state, 150)["dust"]
    assert dust["status"] == "stale" and dust["alert_active"]
    assert dust["diagnostic"] == "Dust acquisition failed."
