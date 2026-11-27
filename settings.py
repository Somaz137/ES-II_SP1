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
    "camera_interval_s": 10,
    "readings_retention_days": 7,
    "alarm_confirm_timeout_s": 2,
    "occupancy_confirm_s": 120,
    "occupancy_confirm_fraction": 0.75,
    "occupancy_hold_s": 900,
    "occupancy_override_s": 900,
    "person_confidence": 0.5,
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


# Optional online-access keys (dashboard.py --online). The local dashboard does not need them.
ONLINE_DEFAULTS = {
    "online_port": 5001,
    "cloudflared_path": "cloudflared",
    "online_session_hours": 8,
    "cloudflared_tunnel": None,
    "online_public_url": None,
    "online_retry_waits_s": [5, 10, 20, 40, 60],
    "cloudflared_log": "logs/cloudflared.log",
}
RETRY_WAITS_MAX = 20
RETRY_WAIT_MAX_S = 3600
LOCAL_DASHBOARD_PORT = 5000


def load_online_settings(path: str | Path) -> dict:
    """The online-access keys of the runtime file, with defaults for absent keys."""
    import yaml

    with Path(path).open(encoding="utf-8") as source:
        try:
            data = yaml.safe_load(source)
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid runtime YAML: {path}") from error
    validate_runtime_settings(data)
    return {key: data.get(key, default) for key, default in ONLINE_DEFAULTS.items()}


def validate_online_settings(data: dict) -> None:
    merged = {**ONLINE_DEFAULTS, **{key: data[key] for key in ONLINE_DEFAULTS if key in data}}
    port = merged["online_port"]
    if (isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535
            or port == LOCAL_DASHBOARD_PORT):
        raise ValueError("online_port must be a whole number from 1024 to 65535, not 5000.")
    binary = merged["cloudflared_path"]
    if not isinstance(binary, str) or not binary.strip():
        raise ValueError("cloudflared_path must be the cloudflared program name or path.")
    _positive("online_session_hours", merged["online_session_hours"])
    name, url = merged["cloudflared_tunnel"], merged["online_public_url"]
    if name is not None and (not isinstance(name, str) or not name.strip()):
        raise ValueError("cloudflared_tunnel must be null or a named tunnel.")
    if url is not None and (not isinstance(url, str) or not url.startswith("https://")):
        raise ValueError("online_public_url must be null or an https:// address.")
    if name is not None and url is None:
        raise ValueError("A named cloudflared_tunnel needs online_public_url.")
    waits = merged["online_retry_waits_s"]
    message = (f"online_retry_waits_s must be a list of at most {RETRY_WAITS_MAX} waits, each more than 0 "
               f"and at most {RETRY_WAIT_MAX_S} seconds.")
    if not isinstance(waits, list) or len(waits) > RETRY_WAITS_MAX:
        raise ValueError(message)
    for wait in waits:
        try:
            _positive("online_retry_waits_s", wait)
        except ValueError:
            raise ValueError(message) from None
        if wait > RETRY_WAIT_MAX_S:
            raise ValueError(message)
    log = merged["cloudflared_log"]
    if not isinstance(log, str) or not log.strip():
        raise ValueError("cloudflared_log must be a file path (relative paths start at the project folder).")


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
    if merged["alarm_confirm_timeout_s"] <= data["serial_poll_interval_s"]:
        raise ValueError("alarm_confirm_timeout_s must exceed serial_poll_interval_s; "
                         "the board's reply is read at a later poll.")
    if merged["readings_retention_days"] < 1:
        raise ValueError("readings_retention_days must be at least 1 for the 24-hour trend.")
    if merged["occupancy_confirm_s"] < merged["camera_interval_s"]:
        raise ValueError("occupancy_confirm_s must not be shorter than camera_interval_s.")
    if not 0 < merged["occupancy_confirm_fraction"] <= 1:
        raise ValueError("occupancy_confirm_fraction must be more than 0 and at most 1.")
    if not 0 < merged["person_confidence"] < 1:
        raise ValueError("person_confidence must be more than 0 and less than 1.")
    validate_online_settings(data)


# System setup for air quality and dust. Equal to config/system.yaml; a test keeps them equal.
SYSTEM_DEFAULTS = {
    "air_quality": {
        "upper_limit": None, "hold_s": None,
        "bands": [{"up_to": 50, "word": "excellent"}, {"up_to": 100, "word": "good"},
                  {"up_to": 150, "word": "lightly polluted"},
                  {"up_to": 200, "word": "moderately polluted"},
                  {"up_to": 250, "word": "heavily polluted"},
                  {"up_to": 350, "word": "severely polluted"}, {"word": "extremely polluted"}],
    },
    "dust": {
        "upper_limit": None, "hold_s": None, "sensitivity_mv_per_mg_m3": 5000,
        "baseline_window_s": 86400, "baseline_min_s": 600, "disconnected_below_mv": 100,
        "levels": [{"up_to": 50, "word": "low"}, {"up_to": 150, "word": "raised"}, {"word": "high"}],
    },
}

# Demonstration values for `monitor.py --demo` only. They are not recommendations: short
# hold times so the simulator shows an air-quality and a dust alert within minutes.
DEMO_SYSTEM_SETTINGS = {
    "air_quality": {**SYSTEM_DEFAULTS["air_quality"], "upper_limit": 150, "hold_s": 30},
    "dust": {**SYSTEM_DEFAULTS["dust"], "upper_limit": 100, "hold_s": 30,
             "baseline_window_s": 3600, "baseline_min_s": 30},
}

BASELINE_WINDOW_MAX_S = 7 * 86400
_SYSTEM_KEYS = {"air_quality": {"upper_limit", "hold_s", "bands"},
                "dust": {"upper_limit", "hold_s", "sensitivity_mv_per_mg_m3",
                         "baseline_window_s", "baseline_min_s", "disconnected_below_mv",
                         "levels"}}


def _words(key, entries):
    if not isinstance(entries, list) or len(entries) < 2:
        raise ValueError(f"{key} needs at least two entries.")
    previous = None
    for index, entry in enumerate(entries):
        last = index == len(entries) - 1
        if not isinstance(entry, dict) or set(entry) != ({"word"} if last else {"up_to", "word"}):
            raise ValueError(f"{key}: each entry has up_to and word; the last has only word.")
        word = entry["word"]
        if not isinstance(word, str) or not word.strip() or len(word) > 40:
            raise ValueError(f"{key}: each word is non-empty text of at most 40 characters.")
        if not last:
            _positive(f"{key} up_to", entry["up_to"])
            if previous is not None and entry["up_to"] <= previous:
                raise ValueError(f"{key}: up_to values must increase.")
            previous = entry["up_to"]


def validate_system_settings(data: object) -> None:
    """Both limits off, or a limit with a hold time; display words in ascending order."""
    if not isinstance(data, dict) or set(data) != set(_SYSTEM_KEYS):
        raise ValueError("System settings need exactly air_quality and dust.")
    for name, keys in _SYSTEM_KEYS.items():
        section = data[name]
        if not isinstance(section, dict) or set(section) != keys:
            raise ValueError(f"{name} needs exactly: {', '.join(sorted(keys))}.")
        limit, hold = section["upper_limit"], section["hold_s"]
        if (limit is None) != (hold is None):
            raise ValueError(f"{name}: set upper_limit and hold_s together, or leave both null.")
        if limit is not None:
            _positive(f"{name} upper_limit", limit)
            _positive(f"{name} hold_s", hold)
    if data["air_quality"]["upper_limit"] is not None and data["air_quality"]["upper_limit"] > 500:
        raise ValueError("air_quality upper_limit must be within Bosch's 0 to 500 scale.")
    _words("air_quality bands", data["air_quality"]["bands"])
    dust = data["dust"]
    _words("dust levels", dust["levels"])
    for key in ("sensitivity_mv_per_mg_m3", "baseline_window_s", "baseline_min_s",
                "disconnected_below_mv"):
        _positive(f"dust {key}", dust[key])
    if dust["disconnected_below_mv"] > 5500:
        raise ValueError("dust disconnected_below_mv must not exceed 5500 mV.")
    if dust["baseline_window_s"] > BASELINE_WINDOW_MAX_S:
        raise ValueError("dust baseline_window_s must not exceed 7 days.")
    if dust["baseline_min_s"] > dust["baseline_window_s"]:
        raise ValueError("dust baseline_min_s must not exceed baseline_window_s.")


def load_system_settings(path: str | Path) -> dict:
    import yaml

    with Path(path).open(encoding="utf-8") as source:
        try:
            data = yaml.safe_load(source)
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid system settings YAML: {path}") from error
    validate_system_settings(data)
    return data
