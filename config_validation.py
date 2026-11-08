"""Validate technical alert settings without file or hardware access."""

import math

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

