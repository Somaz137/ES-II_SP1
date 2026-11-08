"""Load and validate host scheduling settings once at monitor startup."""

import math
from pathlib import Path

import yaml


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
