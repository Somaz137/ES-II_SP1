"""Measurement-shape checks; test execution is deferred to Linux."""

import pytest

from measurement_validation import validate_measurements


def complete_reading():
    return {
        "temp_c": 25.5, "humidity_pct": 45, "pressure_hpa": 1013.25,
        "gas_ohms": 12000,
    }


def test_accepts_finite_numeric_measurements():
    validate_measurements(complete_reading())


def test_does_not_apply_patient_safety_thresholds():
    data = complete_reading()
    data["temp_c"] = 45
    validate_measurements(data)


@pytest.mark.parametrize("data", [None, [], "reading", 120, True])
def test_rejects_non_mapping_measurements(data):
    with pytest.raises(ValueError, match="mapping"):
        validate_measurements(data)


@pytest.mark.parametrize(
    "field", ["temp_c", "humidity_pct", "pressure_hpa", "gas_ohms"]
)
def test_requires_every_measurement(field):
    data = complete_reading()
    del data[field]
    with pytest.raises(ValueError, match=field):
        validate_measurements(data)


@pytest.mark.parametrize(
    "field", ["temp_c", "humidity_pct", "pressure_hpa", "gas_ohms"]
)
@pytest.mark.parametrize(
    "value", [True, False, "25", None, [], {}, float("nan"),
              float("inf"), float("-inf")]
)
def test_rejects_unusable_measurements(field, value):
    data = complete_reading()
    data[field] = value
    with pytest.raises(ValueError, match=field):
        validate_measurements(data)


def test_accepts_zero_and_negative_finite_values_without_inventing_ranges():
    data = complete_reading()
    data["temp_c"] = -5
    data["gas_ohms"] = 0
    validate_measurements(data)

