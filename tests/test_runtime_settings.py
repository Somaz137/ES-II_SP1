"""Deferred Linux validation using real YAML files."""

import pytest

from settings import load_runtime_settings, validate_runtime_settings


def test_runtime_file_loads_startup_snapshot(tmp_path):
    path = tmp_path / "runtime.yaml"
    path.write_text("fault_check_interval_s: 5\nserial_retry_interval_s: 5\nserial_poll_interval_s: 0.05\n")
    first = load_runtime_settings(path)
    path.write_text("fault_check_interval_s: 10\nserial_retry_interval_s: 5\nserial_poll_interval_s: 0.1\n")
    assert first["fault_check_interval_s"] == 5
    assert load_runtime_settings(path)["fault_check_interval_s"] == 10


@pytest.mark.parametrize("key", ["fault_check_interval_s", "serial_retry_interval_s", "serial_poll_interval_s"])
@pytest.mark.parametrize("bad", [None, True, "5", 0, -1, float("inf"), float("nan"), 10 ** 1000])
def test_bad_durations_rejected(key, bad):
    data = dict(fault_check_interval_s=5, serial_retry_interval_s=5, serial_poll_interval_s=0.05)
    data[key] = bad
    with pytest.raises(ValueError):
        validate_runtime_settings(data)


def test_poll_cannot_exceed_fault_interval():
    with pytest.raises(ValueError):
        validate_runtime_settings(dict(fault_check_interval_s=5, serial_retry_interval_s=5, serial_poll_interval_s=6))


BASE = dict(fault_check_interval_s=5, serial_retry_interval_s=5, serial_poll_interval_s=0.05)
NEW_KEYS = ("reading_gap_limit_s", "status_stale_after_s", "dashboard_refresh_s",
            "camera_interval_s", "readings_retention_days")


def test_three_key_file_loads_with_defaults(tmp_path):
    from settings import RUNTIME_DEFAULTS

    path = tmp_path / "runtime.yaml"
    path.write_text("fault_check_interval_s: 5\nserial_retry_interval_s: 5\nserial_poll_interval_s: 0.05\n")
    loaded = load_runtime_settings(path)
    assert RUNTIME_DEFAULTS == dict(reading_gap_limit_s=6, status_stale_after_s=15,
                                    dashboard_refresh_s=10, camera_interval_s=10,
                                    readings_retention_days=7, alarm_confirm_timeout_s=2,
                                    occupancy_confirm_s=120, occupancy_confirm_fraction=0.75,
                                    occupancy_hold_s=900, occupancy_override_s=900,
                                    person_confidence=0.5)
    assert loaded == {**BASE, **RUNTIME_DEFAULTS}


def test_project_runtime_file_matches_defaults():
    from pathlib import Path
    from settings import RUNTIME_DEFAULTS

    loaded = load_runtime_settings(Path(__file__).resolve().parents[1] / "src" / "config/runtime.yaml")
    assert {key: loaded[key] for key in RUNTIME_DEFAULTS} == RUNTIME_DEFAULTS


def test_new_keys_override_defaults(tmp_path):
    path = tmp_path / "runtime.yaml"
    path.write_text("fault_check_interval_s: 5\nserial_retry_interval_s: 5\nserial_poll_interval_s: 0.05\n"
                    "reading_gap_limit_s: 9\nstatus_stale_after_s: 20\ndashboard_refresh_s: 4\n"
                    "camera_interval_s: 30\nreadings_retention_days: 2.5\n")
    loaded = load_runtime_settings(path)
    assert [loaded[key] for key in NEW_KEYS] == [9, 20, 4, 30, 2.5]


@pytest.mark.parametrize("key", NEW_KEYS)
@pytest.mark.parametrize("bad", [None, True, "5", 0, -1, float("inf"), float("nan"), 10 ** 1000])
def test_bad_optional_values_rejected(key, bad):
    with pytest.raises(ValueError, match=key):
        validate_runtime_settings({**BASE, key: bad})


@pytest.mark.parametrize("extra, message", [
    (dict(status_stale_after_s=5.05), "status_stale_after_s"),
    (dict(dashboard_refresh_s=16), "dashboard_refresh_s"),
    (dict(readings_retention_days=0.5), "readings_retention_days"),
])
def test_unworkable_combinations_rejected(extra, message):
    with pytest.raises(ValueError, match=message):
        validate_runtime_settings({**BASE, **extra})


def test_stale_limit_just_above_fault_check_accepted():
    validate_runtime_settings({**BASE, "status_stale_after_s": 5.1, "dashboard_refresh_s": 5.1})


def test_defaults_import_without_pyyaml():
    import subprocess
    import sys
    from pathlib import Path

    code = ("import sys; sys.modules['yaml'] = None\n"
            "import settings, monitor, room_session\n"
            "print(settings.RUNTIME_DEFAULTS['reading_gap_limit_s'])")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1] / "src")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "6"


@pytest.mark.parametrize("bad", [None, True, "2", 0, -1, float("inf"), float("nan"), 10 ** 1000])
def test_bad_alarm_confirm_timeout_rejected(bad):
    with pytest.raises(ValueError, match="alarm_confirm_timeout_s"):
        validate_runtime_settings({**BASE, "alarm_confirm_timeout_s": bad})


def test_alarm_confirm_timeout_must_exceed_the_poll_interval(tmp_path):
    with pytest.raises(ValueError, match="alarm_confirm_timeout_s"):
        validate_runtime_settings({**BASE, "alarm_confirm_timeout_s": 0.05})
    validate_runtime_settings({**BASE, "alarm_confirm_timeout_s": 0.06})
    path = tmp_path / "runtime.yaml"
    path.write_text("fault_check_interval_s: 5\nserial_retry_interval_s: 5\nserial_poll_interval_s: 0.05\n"
                    "alarm_confirm_timeout_s: 4\n")
    assert load_runtime_settings(path)["alarm_confirm_timeout_s"] == 4


@pytest.mark.parametrize("bad", [{"occupancy_confirm_s": 5}, {"occupancy_confirm_fraction": 1.5},
                                 {"occupancy_confirm_fraction": 0}, {"person_confidence": 1},
                                 {"person_confidence": 0}])
def test_impossible_occupancy_settings_refused(bad):
    with pytest.raises(ValueError, match=next(iter(bad))):
        validate_runtime_settings({**BASE, "camera_interval_s": 10, **bad})
    validate_runtime_settings({**BASE, "camera_interval_s": 10, "occupancy_confirm_fraction": 1,
                               "occupancy_confirm_s": 10, "person_confidence": 0.99})


def test_camera_mode_without_model_exits_with_hint(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    code = ("import sys, person_detector, monitor\n"
            "from pathlib import Path\n"
            f"person_detector.MODEL_PATH = Path({str(tmp_path / 'missing.onnx')!r})\n"
            "sys.argv = ['monitor.py', '--port', '/dev/null', '--camera', '0']\n"
            "monitor.main()")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=Path(__file__).resolve().parents[1] / "src", timeout=30)
    assert result.returncode != 0
    assert "src/tools/get_person_model.py" in result.stderr
