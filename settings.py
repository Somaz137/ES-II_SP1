"""Load and validate alert timeouts and host timing settings at startup."""

import math
from pathlib import Path
from typing import Any


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
    import yaml

    config_path = Path(path)
    with config_path.open(encoding="utf-8") as config_file:
        try:
            settings = yaml.safe_load(config_file)
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid YAML in {config_path}.") from error

    validate_alert_settings(settings)
    return settings


# Optional host timing keys. Defined once; the demo and the dashboard use these values too.
RUNTIME_DEFAULTS = {
    "reading_gap_limit_s": 6,
    "status_stale_after_s": 15,
    "dashboard_refresh_s": 10,
    "camera_interval_s": 60,
    "readings_retention_days": 7,
}


def load_runtime_settings(path: str | Path) -> dict:
    """These host settings do not configure the ESP32 sampling interval.

    Optional keys absent from the file take their RUNTIME_DEFAULTS value.
    """
    import yaml

    with Path(path).open(encoding="utf-8") as source:
        try:
            data = yaml.safe_load(source)
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid runtime YAML: {path}") from error
    validate_runtime_settings(data)
    return {**RUNTIME_DEFAULTS, **data}


def _positive(key, value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be finite and positive.")
    try:
        valid = math.isfinite(value) and value > 0
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f"{key} must be finite and positive.")


def validate_runtime_settings(data: object) -> None:
    """Require finite positive durations, with a responsive poll interval."""
    keys = ("fault_check_interval_s", "serial_retry_interval_s", "serial_poll_interval_s")
    if not isinstance(data, dict):
        raise ValueError("Runtime settings must be a mapping.")
    for key in keys:
        _positive(key, data.get(key))
    for key in RUNTIME_DEFAULTS:
        if key in data:
            _positive(key, data[key])
    if data["serial_poll_interval_s"] > min(
        data["fault_check_interval_s"], data["serial_retry_interval_s"]
    ):
        raise ValueError("Serial polling must not exceed fault/retry intervals.")
    merged = {**RUNTIME_DEFAULTS, **data}
    # An idle monitor publishes once per fault check, up to one poll interval late.
    if merged["status_stale_after_s"] <= (merged["fault_check_interval_s"]
                                          + merged["serial_poll_interval_s"]):
        raise ValueError("status_stale_after_s must exceed fault_check_interval_s plus "
                         "serial_poll_interval_s; an idle monitor publishes once per fault check.")
    if merged["dashboard_refresh_s"] > merged["status_stale_after_s"]:
        raise ValueError("dashboard_refresh_s must not exceed status_stale_after_s.")
    if merged["readings_retention_days"] < 1:
        raise ValueError("readings_retention_days must be at least 1 for the 24-hour trend.")
