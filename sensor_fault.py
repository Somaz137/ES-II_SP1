"""Pure sensor-error timing, with pauses controlled by communication status."""

from dataclasses import dataclass, replace
import math


@dataclass(frozen=True)
class SensorFaultState:
    """A snapshot of a sensor-error episode, separate from communication alerts."""

    timeout_s: float
    last_updated_at: float
    error_started_at: float | None = None
    error_elapsed_s: float = 0.0
    last_valid_measurement_at: float | None = None
    paused: bool = False
    alert_active: bool = False


def _finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number.")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be a finite number.") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite number.")
    return result


def _checked_now(state: SensorFaultState, now: float) -> float:
    now = _finite_number(now, "now")
    if now < state.last_updated_at:
        raise ValueError("now must not move backwards.")
    return now


def _advance(state: SensorFaultState, now: float) -> SensorFaultState:
    now = _checked_now(state, now)
    elapsed = state.error_elapsed_s
    if state.error_started_at is not None and not state.paused:
        elapsed += now - state.last_updated_at
    return replace(state, last_updated_at=now, error_elapsed_s=elapsed)


def _update_alert(state: SensorFaultState) -> SensorFaultState:
    due = (
        state.error_started_at is not None
        and not state.paused
        and state.error_elapsed_s >= state.timeout_s
    )
    return replace(state, alert_active=state.alert_active or due)


def create_sensor_state(started_at: float, timeout_s: float) -> SensorFaultState:
    """Initialize timing without inventing a sensor-error episode."""
    started_at = _finite_number(started_at, "started_at")
    timeout_s = _finite_number(timeout_s, "timeout_s")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive.")
    return SensorFaultState(timeout_s=timeout_s, last_updated_at=started_at)


def record_sensor_error(state: SensorFaultState, now: float) -> SensorFaultState:
    """Begin or continue an error episode; an arriving message resumes timing.

    Repeated errors do not reset accumulated time. Time while paused is
    excluded. The caller must also record the recognized message with the
    communication tracker; this module does not mutate that tracker.
    """
    state = _advance(state, now)
    state = replace(
        state,
        error_started_at=(
            state.last_updated_at
            if state.error_started_at is None
            else state.error_started_at
        ),
        paused=False,
    )
    return _update_alert(state)


def record_valid_measurement(
    state: SensorFaultState, now: float
) -> SensorFaultState:
    """Reset error timing and clear its alert without acknowledgment."""
    now = _checked_now(state, now)
    return replace(
        state,
        last_updated_at=now,
        last_valid_measurement_at=now,
        error_started_at=None,
        error_elapsed_s=0.0,
        paused=False,
        alert_active=False,
    )


def evaluate_sensor_fault(
    state: SensorFaultState, now: float, *, communication_timed_out: bool
) -> SensorFaultState:
    """Advance active error time and apply actual communication timeout status.

    Pass communication.timed_out, never communication.alert_active. The
    pause begins at this call's supplied time; earlier unpaused time counts.
    While paused, no new sensor alert is raised and existing alerts remain
    until a valid measurement. Resume preserves elapsed time, so an error
    with no waiting time left alerts as soon as it resumes.

    Evaluate periodically, including during silence, with nondecreasing
    times from the same clock domain used for message arrival.
    """
    if not isinstance(communication_timed_out, bool):
        raise ValueError("communication_timed_out must be a boolean.")
    state = _advance(state, now)
    state = replace(state, paused=communication_timed_out)
    return _update_alert(state)

