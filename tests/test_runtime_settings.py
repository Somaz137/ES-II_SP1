"""Deferred Linux validation using real YAML files."""

import pytest

from runtime_settings import load_runtime_settings, validate_runtime_settings


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
