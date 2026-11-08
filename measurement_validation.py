"""Check measurement structure without deciding whether a room is safe."""

import math

MEASUREMENT_FIELDS = ("temp_c", "humidity_pct", "pressure_hpa", "gas_ohms")


def validate_measurements(data: object) -> None:
    """Require all four measurements as finite numbers; do not coerce values.

    This validates usability, not patient safety or physical-range limits.
    Metadata such as the serial record type is not a measurement.
    """
    if not isinstance(data, dict):
        raise ValueError("Measurements must be a mapping.")

    for field in MEASUREMENT_FIELDS:
        if field not in data:
            raise ValueError(f"Missing measurement: {field}.")
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{field} must be a finite number.")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"{field} must be a finite number.")

