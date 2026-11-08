"""Interpret reported BSEC status without timing or gas safety decisions."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class GasReadiness:
    """One coherent status report. Missing or invalid metadata stays unknown."""

    stabilization_status: int | None = None
    run_in_status: int | None = None
    iaq_accuracy: int | None = None


def parse_gas_readiness(data: object) -> GasReadiness:
    """Require all three integer fields, excluding bools and numeric strings."""
    if not isinstance(data, dict):
        return GasReadiness()
    limits = {"stabilization_status": 1, "run_in_status": 1, "iaq_accuracy": 3}
    for name, maximum in limits.items():
        value = data.get(name)
        if type(value) is not int or not 0 <= value <= maximum:
            return GasReadiness()
    return GasReadiness(
        stabilization_status=data["stabilization_status"],
        run_in_status=data["run_in_status"],
        iaq_accuracy=data["iaq_accuracy"],
    )


def gas_warmup_status(
    state: GasReadiness,
) -> Literal["unknown", "warming_up", "warmup_complete"]:
    """Report Bosch flags, not elapsed time or verified calibration."""
    if state.stabilization_status is None or state.run_in_status is None:
        return "unknown"
    if state.stabilization_status == 0 or state.run_in_status == 0:
        return "warming_up"
    return "warmup_complete"


def gas_calibration_status(
    state: GasReadiness,
) -> Literal["unknown", "stabilizing", "calibration_required", "calibrating", "calibrated"]:
    """Describe reported IAQ algorithm accuracy separately from warm-up.

    These are algorithm status labels. They do not establish room safety
    or a certified gas concentration. Consult current input/fault status
    before displaying a retained report as current.
    """
    labels = {0: "stabilizing", 1: "calibration_required",
              2: "calibrating", 3: "calibrated"}
    return labels.get(state.iaq_accuracy, "unknown")
