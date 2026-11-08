"""Reported algorithm status, independent of elapsed warm-up time."""

import pytest

from gas_readiness import (
    parse_gas_readiness,
    gas_warmup_status,
    gas_calibration_status,
)


@pytest.mark.parametrize("stabilization,run_in,want", [
    (0, 0, "warming_up"), (0, 1, "warming_up"),
    (1, 0, "warming_up"), (1, 1, "warmup_complete"),
])
def test_warmup_uses_both_bosch_flags(stabilization, run_in, want):
    state = parse_gas_readiness({"stabilization_status": stabilization,
                                "run_in_status": run_in, "iaq_accuracy": 1})
    assert gas_warmup_status(state) == want


@pytest.mark.parametrize("accuracy,want", [
    (0, "stabilizing"), (1, "calibration_required"),
    (2, "calibrating"), (3, "calibrated"),
])
def test_calibration_is_separate_from_completed_warmup(accuracy, want):
    state = parse_gas_readiness({"stabilization_status": 1,
                                "run_in_status": 1, "iaq_accuracy": accuracy})
    assert gas_warmup_status(state) == "warmup_complete"
    assert gas_calibration_status(state) == want


@pytest.mark.parametrize("data", [None, [], "ready", {},
    {"stabilization_status": 1, "run_in_status": 1}])
def test_missing_or_incomplete_metadata_is_unknown(data):
    state = parse_gas_readiness(data)
    assert gas_warmup_status(state) == "unknown"
    assert gas_calibration_status(state) == "unknown"


@pytest.mark.parametrize("field,bad", [
    ("stabilization_status", True), ("stabilization_status", 2),
    ("run_in_status", False), ("run_in_status", -1),
    ("iaq_accuracy", 4), ("iaq_accuracy", 3.0),
    ("iaq_accuracy", "3"), ("iaq_accuracy", float("nan")),
])
def test_invalid_metadata_does_not_establish_readiness(field, bad):
    data = {"stabilization_status": 1, "run_in_status": 1, "iaq_accuracy": 3}
    data[field] = bad
    state = parse_gas_readiness(data)
    assert gas_warmup_status(state) == "unknown"
    assert gas_calibration_status(state) == "unknown"


def test_snapshot_does_not_retain_mutable_dictionary():
    data = {"stabilization_status": 1, "run_in_status": 1, "iaq_accuracy": 3}
    state = parse_gas_readiness(data)
    data["run_in_status"] = 0
    assert gas_warmup_status(state) == "warmup_complete"
