"""Bosch index parsing, its state and word band, and the system settings file."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gas_readiness import GasReadiness, parse_gas_readiness
from monitoring_state import create_monitoring_state, process_serial_line
from serial_parser import parse_serial_line
from status_output import status_record

ROOT = Path(__file__).resolve().parents[1]
BSEC = {"stabilization_status": 1, "run_in_status": 1, "iaq_accuracy": 3}


def reading(**bsec):
    return json.dumps({"type": "reading", "temp_c": 24, "humidity_pct": 45, "pressure_hpa": 1005,
                       "gas_ohms": 12000, "bsec": bsec})


def test_index_is_kept_with_the_status_fields():
    assert parse_gas_readiness({**BSEC, "iaq": 57.25}) == GasReadiness(1, 1, 3, 57.25)
    assert parse_serial_line(reading(**BSEC, iaq=182)).gas.iaq == 182


def test_record_without_index_still_parses():
    line = (ROOT / "tests" / "fixtures" / "bsec_reading.json").read_text()
    parsed = parse_serial_line(line)
    assert parsed.kind == "valid_reading"
    assert parsed.gas == GasReadiness(1, 0, 2, None)


@pytest.mark.parametrize("bad", [None, True, "57", -0.1, 500.1, float("nan"), float("inf"), [1]])
def test_unusable_index_is_null_and_does_not_reject_the_reading(bad):
    parsed = parse_serial_line(reading(**BSEC, iaq=bad))
    assert parsed.kind == "valid_reading"
    assert parsed.gas == GasReadiness(1, 1, 3, None)


def test_index_needs_valid_status_fields():
    assert parse_gas_readiness({"iaq": 50}) == GasReadiness()


def test_status_record_reports_the_retained_index_and_accuracy():
    state = create_monitoring_state(0, 120, 120)
    state = process_serial_line(state, reading(**{**BSEC, "iaq_accuracy": 1}, iaq=75.5), 1)
    record = status_record(state, 2, SimpleNamespace(connected=True, last_error=None),
                           monotonic_origin=0, utc_origin=0)
    assert record["bsec_iaq"] == 75.5 and record["bsec_iaq_accuracy"] == 1


def test_state_follows_bosch_accuracy_and_reading_freshness():
    from air_quality import IAQ_MIN_ACCURACY, air_quality_state

    assert IAQ_MIN_ACCURACY == 2
    assert air_quality_state(80, 3, True) == "current"
    assert air_quality_state(80, 2, True) == "current"
    assert air_quality_state(80, 1, True) == "calibrating"
    assert air_quality_state(80, 0, True) == "calibrating"
    assert air_quality_state(None, 0, True) == "calibrating"
    assert air_quality_state(None, 3, True) == "unavailable"
    assert air_quality_state(80, None, True) == "unavailable"
    assert air_quality_state(80, 3, False) == "unavailable"


def test_band_takes_the_first_entry_the_value_does_not_exceed():
    from air_quality import band_word

    bands = [{"up_to": 50, "word": "a"}, {"up_to": 100, "word": "b"}, {"word": "c"}]
    assert [band_word(v, bands) for v in (0, 50, 50.01, 100, 101, 500)] == ["a", "a", "b", "b", "c", "c"]
    assert band_word(None, bands) is None


# System settings file.

def test_project_system_file_matches_defaults_and_leaves_limits_off():
    from settings import SYSTEM_DEFAULTS, load_system_settings

    loaded = load_system_settings(ROOT / "config" / "system.yaml")
    assert loaded == SYSTEM_DEFAULTS
    for key in ("air_quality", "dust"):
        assert loaded[key]["upper_limit"] is None and loaded[key]["hold_s"] is None
    assert loaded["dust"]["sensitivity_mv_per_mg_m3"] == 5000


def test_demo_settings_are_valid_and_set_demonstration_limits():
    from settings import DEMO_SYSTEM_SETTINGS, validate_system_settings

    validate_system_settings(DEMO_SYSTEM_SETTINGS)
    assert DEMO_SYSTEM_SETTINGS["air_quality"]["upper_limit"] == 150
    assert DEMO_SYSTEM_SETTINGS["dust"]["upper_limit"] == 100


def changed(path, value):
    from settings import SYSTEM_DEFAULTS

    data = copy.deepcopy(SYSTEM_DEFAULTS)
    target = data
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return data


@pytest.mark.parametrize("path, value", [
    (("air_quality", "upper_limit"), 150),  # a limit without a hold time
    (("dust", "hold_s"), 60),  # a hold time without a limit
    (("air_quality",), KeyError),
    (("dust", "sensitivity_mv_per_mg_m3"), 0),
    (("dust", "sensitivity_mv_per_mg_m3"), True),
    (("dust", "baseline_min_s"), 90000),  # longer than the window
    (("dust", "baseline_window_s"), 8 * 86400),  # beyond the 7-day bound
    (("air_quality", "bands"), []),
    (("air_quality", "bands"), [{"up_to": 100, "word": "a"}, {"up_to": 50, "word": "b"}, {"word": "c"}]),
    (("air_quality", "bands"), [{"up_to": 50, "word": "a"}]),  # last entry must be open
    (("dust", "levels"), [{"up_to": 50, "word": ""}, {"word": "b"}]),
    (("dust", "levels"), [{"up_to": float("nan"), "word": "a"}, {"word": "b"}]),
    (("dust", "unknown_key"), 1),
])
def test_invalid_system_settings_are_rejected(path, value):
    from settings import validate_system_settings

    with pytest.raises(ValueError):
        validate_system_settings(changed(path, value))


@pytest.mark.parametrize("limit, hold", [(0, 60), (-1, 60), (150, 0), (501, 60), (float("inf"), 60), ("150", 60)])
def test_invalid_air_quality_limit_pairs_are_rejected(limit, hold):
    from settings import validate_system_settings

    data = changed(("air_quality", "upper_limit"), limit)
    data["air_quality"]["hold_s"] = hold
    with pytest.raises(ValueError):
        validate_system_settings(data)


def test_a_complete_limit_pair_is_accepted(tmp_path):
    from settings import load_system_settings

    text = (ROOT / "config" / "system.yaml").read_text(encoding="utf-8")
    text = text.replace("upper_limit: null", "upper_limit: 150", 1).replace("hold_s: null", "hold_s: 1800", 1)
    path = tmp_path / "system.yaml"
    path.write_text(text, encoding="utf-8")
    loaded = load_system_settings(path)
    assert loaded["air_quality"]["upper_limit"] == 150 and loaded["air_quality"]["hold_s"] == 1800


def test_invalid_yaml_is_a_value_error(tmp_path):
    from settings import load_system_settings

    path = tmp_path / "system.yaml"
    path.write_text("air_quality: [\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_system_settings(path)
