"""Combine reading and fault facts without selecting hardware, clocks or safety rules."""

from dataclasses import dataclass, field, replace
from typing import Literal

from communication_fault import (
    CommunicationFaultState,
    acknowledge_communication_fault,
    create_communication_state,
    evaluate_communication_fault,
)
from reading_state import InputStatus, ReadingState
from sensor_fault import (
    SensorFaultState,
    create_sensor_state,
    evaluate_sensor_fault,
)


@dataclass(frozen=True)
class MonitoringState:
    """Retain returned snapshots. Construct through create_monitoring_state()."""

    communication: CommunicationFaultState
    sensor: SensorFaultState
    reading: ReadingState = field(default_factory=ReadingState)


def create_monitoring_state(
    started_at: float,
    communication_timeout_s: float,
    sensor_error_timeout_s: float,
) -> MonitoringState:
    """Start normal communication timing while measurements remain empty."""
    return MonitoringState(
        communication=create_communication_state(started_at, communication_timeout_s),
        sensor=create_sensor_state(started_at, sensor_error_timeout_s),
    )


def evaluate_monitoring_faults(state: MonitoringState, now: float) -> MonitoringState:
    """Evaluate periodically during silence using actual communication timeout.

    A sensor pause starts when this function reports the timeout. An
    acknowledgment latch alone cannot pause or resume sensor timing.
    """
    communication = evaluate_communication_fault(state.communication, now)
    sensor = evaluate_sensor_fault(
        state.sensor, now, communication_timed_out=communication.timed_out
    )
    return replace(state, communication=communication, sensor=sensor)


def acknowledge_monitoring_communication(
    state: MonitoringState, now: float
) -> MonitoringState:
    """Acknowledge communication while preserving actual outage and sensor pause."""
    state = evaluate_monitoring_faults(state, now)
    return replace(
        state,
        communication=acknowledge_communication_fault(state.communication, now),
    )


def monitoring_status(
    state: MonitoringState,
) -> InputStatus | Literal["communication_lost"]:
    """Summarize current input, not alert attention, gas readiness or room safety.

    Fresh means the latest recognized input was structurally complete and
    communication has not timed out. It is not an independent age limit.
    Keep exposing both alert flags even when this summary says fresh.
    """
    if state.communication.timed_out:
        return "communication_lost"
    return state.reading.input_status
