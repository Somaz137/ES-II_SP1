"""Read a startup snapshot of the technical alert settings."""

from pathlib import Path
from typing import Any

import yaml

from config_validation import validate_alert_settings


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

