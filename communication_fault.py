"""Pure communication-fault timing; the caller supplies time and messages."""

from dataclasses import dataclass, replace
import math


@dataclass(frozen=True)
class CommunicationFaultState:
    """Independent contact facts and alert-attention state.

    Use create_communication_state() to initialize this snapshot. An alert
    can remain active after communication recovers, until acknowledged.
    """

    timeout_s: float
    started_at: float
    alert_wait_started_at: float
    last_updated_at: float
    last_message_at: float | None = None
    timed_out: bool = False
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


def _checked_now(state: CommunicationFaultState, now: float) -> float:
    now = _finite_number(now, "now")
    if now < state.last_updated_at:
        raise ValueError("now must not move backwards.")
    return now


def create_communication_state(
    started_at: float, timeout_s: float
) -> CommunicationFaultState:
    """Begin the startup grace period using the configured timeout."""
    started_at = _finite_number(started_at, "started_at")
    timeout_s = _finite_number(timeout_s, "timeout_s")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive.")
    return CommunicationFaultState(
        timeout_s=timeout_s,
        started_at=started_at,
        alert_wait_started_at=started_at,
        last_updated_at=started_at,
    )


def evaluate_communication_fault(
    state: CommunicationFaultState, now: float
) -> CommunicationFaultState:
    """Update timeout/alert flags, including when no message is received.

    Call periodically even during serial silence. All supplied times must
    be finite, nondecreasing, and from the same clock/time domain.
    """
    now = _checked_now(state, now)
    contact_at = (
        state.started_at if state.last_message_at is None else state.last_message_at
    )
    timed_out = now - contact_at >= state.timeout_s
    wait_expired = now - state.alert_wait_started_at >= state.timeout_s
    return replace(
        state,
        last_updated_at=now,
        timed_out=timed_out,
        alert_active=state.alert_active or (timed_out and wait_expired),
    )


def record_communication_message(
    state: CommunicationFaultState, now: float
) -> CommunicationFaultState:
    """Record a recognized reading OR sensor-error message.

    Evaluate the preceding silence first, so a late message cannot erase
    an elapsed fault merely because a periodic check was delayed. A
    message arriving exactly at the timeout boundary counts as late.
    This function does not validate measurements or clear sensor errors.
    """
    state = evaluate_communication_fault(state, now)
    return replace(
        state,
        last_message_at=state.last_updated_at,
        alert_wait_started_at=state.last_updated_at,
        timed_out=False,
    )


def acknowledge_communication_fault(
    state: CommunicationFaultState, now: float
) -> CommunicationFaultState:
    """Dismiss an alert; during an outage, start another full waiting period.

    Actual contact timestamps remain unchanged. An acknowledgment with no
    outstanding alert cannot repeatedly extend a waiting period.
    """
    state = evaluate_communication_fault(state, now)
    if not state.alert_active:
        return state
    return replace(
        state,
        alert_active=False,
        alert_wait_started_at=(
            state.last_updated_at if state.timed_out else state.alert_wait_started_at
        ),
    )

