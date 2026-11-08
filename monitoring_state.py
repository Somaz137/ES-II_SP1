"""Combine monitoring facts and route decoded messages through the parser and trackers."""

from dataclasses import dataclass, field, replace
from typing import Literal

from communication_fault import (
    CommunicationFaultState,
    acknowledge_communication_fault,
    create_communication_state,
    evaluate_communication_fault,
    record_communication_message,
)
from measurements import (
    InputStatus,
    ReadingState,
    commit_reading,
    record_reading_problem,
)
from gas_readiness import GasReadiness, gas_warmup_status
from sensor_fault import (
    SensorFaultState,
    create_sensor_state,
    evaluate_sensor_fault,
    record_sensor_error,
    record_valid_measurement,
)
from serial_parser import parse_serial_line


@dataclass(frozen=True)
class MonitoringState:
    """Retain returned snapshots. Construct through create_monitoring_state()."""

    communication: CommunicationFaultState
    sensor: SensorFaultState
    reading: ReadingState = field(default_factory=ReadingState)
    gas: GasReadiness = field(default_factory=GasReadiness)


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


def current_gas_warmup_status(
    state: MonitoringState,
) -> Literal["unavailable", "unknown", "warming_up", "warmup_complete"]:
    """Hide live readiness when communication or the latest measurement fails.

    Call periodic fault evaluation even during silence. The communication
    acknowledgment latch does not imply current communication loss.
    Warmup complete is not a gas-evaluation policy or room safety verdict.
    """
    if state.communication.timed_out or state.reading.input_status != "fresh":
        return "unavailable"
    return gas_warmup_status(state.gas)


def process_serial_line(
    state: MonitoringState, line: str, now: float
) -> MonitoringState:
    """Return a new state for one line and its host receipt time.

    Supply finite, nondecreasing times in the same domain as startup and
    periodic checks. Ignored lines still allow fault checks. This function
    performs no port access, scheduling or notification. Reported BSEC status
    is retained separately, without a host warm-up timer.
    """
    parsed = parse_serial_line(line)
    if parsed.kind == "ignored":
        return evaluate_monitoring_faults(state, now)

    # Detect preceding silence before the message restores communication.
    communication = evaluate_communication_fault(state.communication, now)
    sensor = state.sensor
    if communication.timed_out:
        sensor = evaluate_sensor_fault(sensor, now, communication_timed_out=True)
    communication = record_communication_message(communication, now)

    if parsed.kind == "valid_reading":
        reading = commit_reading(state.reading, parsed.measurements, now)
        sensor = record_valid_measurement(sensor, now)
    else:
        kind = "incomplete" if parsed.kind == "incomplete_reading" else "sensor_error"
        reading = record_reading_problem(state.reading, kind, parsed.message)
        sensor = record_sensor_error(sensor, now)

    return replace(
        state, communication=communication, sensor=sensor, reading=reading,
        gas=parsed.gas,
    )
