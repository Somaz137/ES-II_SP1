"""Retain the last complete measurements independently from current input quality."""

from dataclasses import dataclass, replace
import math
from typing import Literal

from measurement_validation import validate_measurements

InputStatus = Literal[
    "waiting_for_first_measurement", "fresh", "incomplete", "sensor_error"
]


@dataclass(frozen=True)
class CommittedReading:
    """Complete scalar values and host receipt time in the caller's clock domain."""

    temp_c: int | float
    humidity_pct: int | float
    pressure_hpa: int | float
    gas_ohms: int | float
    received_at: float


@dataclass(frozen=True)
class ReadingState:
    """No measurement exists until the first complete record arrives."""

    last_reading: CommittedReading | None = None
    input_status: InputStatus = "waiting_for_first_measurement"
    diagnostic: str | None = None


def commit_reading(
    state: ReadingState, measurements: dict[str, int | float], now: float
) -> ReadingState:
    """Validate and copy values without retaining a caller-owned dictionary.

    A complete reading does not establish gas readiness or room safety.
    The router validates event order against both fault trackers as well.
    """
    validate_measurements(measurements)
    if isinstance(now, bool) or not isinstance(now, (int, float)):
        raise ValueError("now must be a finite number.")
    try:
        now = float(now)
    except OverflowError as error:
        raise ValueError("now must be a finite number.") from error
    if not math.isfinite(now):
        raise ValueError("now must be a finite number.")
    if state.last_reading is not None and now < state.last_reading.received_at:
        raise ValueError("now must not move backwards.")
    reading = CommittedReading(
        temp_c=measurements["temp_c"],
        humidity_pct=measurements["humidity_pct"],
        pressure_hpa=measurements["pressure_hpa"],
        gas_ohms=measurements["gas_ohms"],
        received_at=now,
    )
    return ReadingState(last_reading=reading, input_status="fresh")


def record_reading_problem(
    state: ReadingState,
    kind: Literal["incomplete", "sensor_error"],
    message: str | None,
) -> ReadingState:
    """Expose the latest recognized problem without replacing values or time."""
    if kind not in ("incomplete", "sensor_error"):
        raise ValueError("kind must be incomplete or sensor_error.")
    return replace(state, input_status=kind, diagnostic=message)
