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
