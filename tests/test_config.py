"""Hardware-free checks for the technical alert configuration."""

from pathlib import Path

import pytest

from config_loader import load_alert_settings
from config_validation import validate_alert_settings


@pytest.mark.parametrize(
    "settings",
    [
        {"communication_timeout_s": 120, "sensor_error_timeout_s": 120},
        {"communication_timeout_s": 30, "sensor_error_timeout_s": 180.5},
        {"communication_timeout_s": 0.25, "sensor_error_timeout_s": 1},
    ],
)
def test_accepts_positive_timeout_values(settings):
    validate_alert_settings(settings)


@pytest.mark.parametrize("settings", [None, [], "settings", 120, True])
def test_rejects_non_mapping_settings(settings):
    with pytest.raises(ValueError, match="mapping"):
        validate_alert_settings(settings)


@pytest.mark.parametrize(
    "missing_key", ["communication_timeout_s", "sensor_error_timeout_s"]
)
def test_requires_each_timeout(missing_key):
    settings = {"communication_timeout_s": 120, "sensor_error_timeout_s": 120}
    del settings[missing_key]

    with pytest.raises(ValueError, match=missing_key):
        validate_alert_settings(settings)


@pytest.mark.parametrize(
    "key", ["communication_timeout_s", "sensor_error_timeout_s"]
)
@pytest.mark.parametrize(
    "value",
    [0, -1, True, False, "120", None, float("inf"), float("-inf"),
     float("nan"), [], {}],
)
def test_rejects_invalid_timeout_values(key, value):
    settings = {"communication_timeout_s": 120, "sensor_error_timeout_s": 120}
    settings[key] = value

    with pytest.raises(ValueError, match=key):
        validate_alert_settings(settings)


def test_loads_independent_values_from_yaml(tmp_path):
    path = tmp_path / "alerts.yaml"
    path.write_text(
        "communication_timeout_s: 45\nsensor_error_timeout_s: 180.5\n",
        encoding="utf-8",
    )

    assert load_alert_settings(path) == {
        "communication_timeout_s": 45,
        "sensor_error_timeout_s": 180.5,
    }


def test_existing_settings_remain_unchanged_until_loaded_again(tmp_path):
    path = tmp_path / "alerts.yaml"
    path.write_text(
        "communication_timeout_s: 120\nsensor_error_timeout_s: 120\n",
        encoding="utf-8",
    )
    initial = load_alert_settings(path)

    path.write_text(
        "communication_timeout_s: 60\nsensor_error_timeout_s: 90\n",
        encoding="utf-8",
    )

    assert initial == {"communication_timeout_s": 120, "sensor_error_timeout_s": 120}
    assert load_alert_settings(path) == {
        "communication_timeout_s": 60,
        "sensor_error_timeout_s": 90,
    }


@pytest.mark.parametrize(
    "content, message",
    [
        ("", "mapping"),
        ("- 120\n- 120\n", "mapping"),
        ("communication_timeout_s: [\n", "Invalid YAML"),
        ("communication_timeout_s: 120\n", "sensor_error_timeout_s"),
        ("communication_timeout_s: false\nsensor_error_timeout_s: 120\n",
         "communication_timeout_s"),
        ("communication_timeout_s: 120\nsensor_error_timeout_s: .inf\n",
         "sensor_error_timeout_s"),
    ],
)
def test_rejects_invalid_yaml_settings(tmp_path, content, message):
    path = tmp_path / "alerts.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_alert_settings(path)


def test_missing_file_reports_its_path(tmp_path):
    path = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError) as error:
        load_alert_settings(path)

    assert Path(error.value.filename) == path

