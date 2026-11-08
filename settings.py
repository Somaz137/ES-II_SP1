"""Load and validate alert timeouts and host timing settings at startup."""

import math
from pathlib import Path
from typing import Any

import yaml


TIMEOUT_KEYS = ("communication_timeout_s", "sensor_error_timeout_s")


def validate_alert_settings(data: object) -> None:
    """Require a mapping containing both finite, positive numeric timeouts.

    Booleans and numeric strings are rejected. Additional keys are left
    untouched so this function only validates the settings it owns.
    """
    if not isinstance(data, dict):
        raise ValueError("Alert settings must be a YAML mapping.")

    for key in TIMEOUT_KEYS:
        if key not in data:
            raise ValueError(f"Missing required alert setting: {key}.")

        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be a finite positive number of seconds.")

        # Python integers are finite; only floats can contain NaN or infinity.
        if value <= 0 or (isinstance(value, float) and not math.isfinite(value)):
            raise ValueError(f"{key} must be a finite positive number of seconds.")


def load_alert_settings(path: str | Path) -> dict[str, Any]:
    """Read UTF-8 YAML, validate its timeouts, and return the settings.

    The application should call this once during startup and retain the
    result. This function does not watch the file or reload settings.
    Missing or unreadable files retain their native filesystem exceptions.
    """
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as config_file:
        try:
            settings = yaml.safe_load(config_file)
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid YAML in {config_path}.") from error

    validate_alert_settings(settings)
    return settings


def load_runtime_settings(path: str | Path) -> dict:
    """These host settings do not configure the ESP32 sampling interval."""
    with Path(path).open(encoding="utf-8") as source:
        try:
            data = yaml.safe_load(source)
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid runtime YAML: {path}") from error
    validate_runtime_settings(data)
    return data


def validate_runtime_settings(data: object) -> None:
    """Require finite positive durations, with a responsive poll interval."""
    keys = ("fault_check_interval_s", "serial_retry_interval_s", "serial_poll_interval_s")
    if not isinstance(data, dict):
        raise ValueError("Runtime settings must be a mapping.")
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} must be finite and positive.")
        try:
            valid = math.isfinite(value) and value > 0
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError(f"{key} must be finite and positive.")
    if data["serial_poll_interval_s"] > min(
        data["fault_check_interval_s"], data["serial_retry_interval_s"]
    ):
        raise ValueError("Serial polling must not exceed fault/retry intervals.")
