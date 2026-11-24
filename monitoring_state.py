"""Combine monitoring facts and route decoded messages through the parser and trackers."""

from dataclasses import dataclass, field, replace
from typing import Literal, NamedTuple

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
from dust import DustState, parse_dust, record_dust


class AlarmReply(NamedTuple):
    """The level the board last reported applying, and its host receipt time."""

    level: int
    received_at: float


class BsecRequest(NamedTuple):
    """The latest state request; count is the number of requests so far."""

    count: int
    bsec_version: str
    received_at: float


class BsecStateReport(NamedTuple):
    """The latest state line from the board; count is the number so far."""

    count: int
    accuracy: int
    bsec_version: str
    state_hex: str
    received_at: float


class BsecRestored(NamedTuple):
    count: int
    ok: bool
    received_at: float


class BsecSaveFailed(NamedTuple):
    count: int
    received_at: float


@dataclass(frozen=True)
class MonitoringState:
    """Retain returned snapshots. Construct through create_monitoring_state()."""

    communication: CommunicationFaultState
    sensor: SensorFaultState
    reading: ReadingState = field(default_factory=ReadingState)
    gas: GasReadiness = field(default_factory=GasReadiness)
    dust: DustState = field(default_factory=DustState)
    alarm_reply: AlarmReply | None = None
    # BSEC calibration state lines; the monitor answers and stores them.
    bsec_request: BsecRequest | None = None
    bsec_state: BsecStateReport | None = None
    bsec_restored: BsecRestored | None = None
    bsec_save_failed: BsecSaveFailed | None = None


def create_monitoring_state(
    started_at: float,
    communication_timeout_s: float,
    sensor_error_timeout_s: float,
    dust_floor_mv: float = 100.0,
) -> MonitoringState:
    """Start normal communication timing while measurements remain empty."""
    return MonitoringState(
        dust=DustState(started_at=started_at, floor_mv=float(dust_floor_mv)),
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
    dust_message = parse_dust(line)
    if dust_message is not None:
        state = evaluate_monitoring_faults(state, now)
        communication = record_communication_message(state.communication, now)
        return replace(state, communication=communication,
                       dust=record_dust(state.dust, dust_message, now))
    parsed = parse_serial_line(line)
    if parsed.kind == "ignored":
        return evaluate_monitoring_faults(state, now)
    if parsed.kind == "alarm_state":
        # Not communication contact: the host solicits these replies, so they
        # must not hide a stopped measurement stream. No reading or sensor effect.
        state = evaluate_monitoring_faults(state, now)
        return replace(state, alarm_reply=AlarmReply(parsed.alarm_level, now))
    if parsed.kind.startswith("bsec_state"):
        # Not communication contact, like alarm replies: no reading or sensor effect.
        return record_bsec_line(evaluate_monitoring_faults(state, now), parsed, now)

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


def record_bsec_line(state, parsed, now):
    """Keep the latest BSEC line of each kind with a running count."""
    def count(previous):
        return 1 if previous is None else previous.count + 1

    if parsed.kind == "bsec_state_request":
        return replace(state, bsec_request=BsecRequest(
            count(state.bsec_request), parsed.bsec_version, now))
    if parsed.kind == "bsec_state":
        return replace(state, bsec_state=BsecStateReport(
            count(state.bsec_state), parsed.bsec_accuracy, parsed.bsec_version,
            parsed.bsec_state_hex, now))
    if parsed.kind == "bsec_state_restored":
        return replace(state, bsec_restored=BsecRestored(
            count(state.bsec_restored), parsed.restore_ok, now))
    return replace(state, bsec_save_failed=BsecSaveFailed(count(state.bsec_save_failed), now))
