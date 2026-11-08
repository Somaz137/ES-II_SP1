"""Communication-fault scenarios; run with the pinned pytest on Linux."""

import pytest

from communication_fault import (
    acknowledge_communication_fault,
    create_communication_state,
    evaluate_communication_fault,
    record_communication_message,
)


def test_startup_waits_until_the_full_timeout():
    state = create_communication_state(started_at=0, timeout_s=120)

    before = evaluate_communication_fault(state, now=119.999)
    assert before.last_message_at is None
    assert not before.timed_out
    assert not before.alert_active

    at_limit = evaluate_communication_fault(before, now=120)
    assert at_limit.timed_out
    assert at_limit.alert_active


def test_uses_the_configured_timeout_instead_of_a_fixed_two_minutes():
    state = create_communication_state(started_at=100, timeout_s=30)

    assert not evaluate_communication_fault(state, now=129.999).alert_active
    assert evaluate_communication_fault(state, now=130).alert_active


def test_recognized_message_restarts_the_communication_wait():
    state = create_communication_state(started_at=0, timeout_s=120)
    state = record_communication_message(state, now=100)

    assert state.last_message_at == 100
    assert not evaluate_communication_fault(state, now=219.999).alert_active
    assert evaluate_communication_fault(state, now=220).alert_active


def test_regular_messages_do_not_raise_an_alert():
    state = create_communication_state(started_at=0, timeout_s=120)
    for now in (30, 60, 90, 120, 150, 180, 210, 240):
        state = record_communication_message(state, now=now)

    assert state.last_message_at == 240
    assert not state.timed_out
    assert not state.alert_active


def test_recovery_keeps_the_alert_until_acknowledgment():
    state = create_communication_state(started_at=0, timeout_s=120)
    state = evaluate_communication_fault(state, now=120)
    restored = record_communication_message(state, now=125)

    assert restored.last_message_at == 125
    assert not restored.timed_out
    assert restored.alert_active

    acknowledged = acknowledge_communication_fault(restored, now=130)
    assert not acknowledged.alert_active
    assert acknowledged.last_message_at == 125


def test_late_message_preserves_a_fault_even_without_an_intervening_tick():
    state = create_communication_state(started_at=0, timeout_s=120)
    restored = record_communication_message(state, now=150)

    assert restored.last_message_at == 150
    assert not restored.timed_out
    assert restored.alert_active


def test_message_arriving_at_the_timeout_boundary_preserves_the_alert():
    state = create_communication_state(started_at=0, timeout_s=120)
    restored = record_communication_message(state, now=120)

    assert not restored.timed_out
    assert restored.alert_active


def test_acknowledgment_during_silence_starts_another_full_wait():
    state = create_communication_state(started_at=0, timeout_s=120)
    state = evaluate_communication_fault(state, now=120)
    state = acknowledge_communication_fault(state, now=130)

    assert state.started_at == 0
    assert state.last_message_at is None
    assert state.timed_out
    assert not state.alert_active
    assert not evaluate_communication_fault(state, now=249.999).alert_active
    assert evaluate_communication_fault(state, now=250).alert_active


def test_acknowledgment_does_not_modify_the_last_real_contact():
    state = create_communication_state(started_at=0, timeout_s=120)
    state = record_communication_message(state, now=20)
    state = evaluate_communication_fault(state, now=140)
    acknowledged = acknowledge_communication_fault(state, now=150)

    assert acknowledged.last_message_at == 20
    assert acknowledged.timed_out
    assert not acknowledged.alert_active


def test_repeated_acknowledgments_require_a_new_alert_before_postponing():
    state = create_communication_state(started_at=0, timeout_s=120)
    state = acknowledge_communication_fault(
        evaluate_communication_fault(state, now=120), now=130
    )
    state = acknowledge_communication_fault(state, now=200)

    assert evaluate_communication_fault(state, now=250).alert_active


def test_acknowledgment_before_any_alert_does_not_delay_detection():
    state = create_communication_state(started_at=0, timeout_s=120)
    state = acknowledge_communication_fault(state, now=60)

    assert evaluate_communication_fault(state, now=120).alert_active


def test_recovery_during_acknowledged_wait_starts_from_the_real_message():
    state = create_communication_state(started_at=0, timeout_s=120)
    state = acknowledge_communication_fault(
        evaluate_communication_fault(state, now=120), now=130
    )
    state = record_communication_message(state, now=150)

    assert not state.alert_active
    assert not state.timed_out
    assert not evaluate_communication_fault(state, now=269.999).alert_active
    assert evaluate_communication_fault(state, now=270).alert_active


def test_acknowledgment_after_recovery_does_not_extend_contact_freshness():
    state = create_communication_state(started_at=0, timeout_s=120)
    state = record_communication_message(state, now=130)
    state = acknowledge_communication_fault(state, now=200)

    assert state.last_message_at == 130
    assert evaluate_communication_fault(state, now=250).alert_active


def test_state_updates_do_not_mutate_previous_snapshots():
    original = create_communication_state(started_at=0, timeout_s=120)
    updated = record_communication_message(original, now=30)

    assert original.last_message_at is None
    assert updated.last_message_at == 30


@pytest.mark.parametrize("timeout", [0, -1, True, "120", float("inf"), float("nan")])
def test_rejects_invalid_timeout_inputs(timeout):
    with pytest.raises(ValueError, match="timeout_s"):
        create_communication_state(started_at=0, timeout_s=timeout)


@pytest.mark.parametrize("now", [True, "0", float("inf"), float("nan")])
def test_rejects_invalid_start_times(now):
    with pytest.raises(ValueError, match="started_at"):
        create_communication_state(started_at=now, timeout_s=120)


@pytest.mark.parametrize(
    "operation",
    [evaluate_communication_fault, record_communication_message,
     acknowledge_communication_fault],
)
def test_rejects_time_moving_backwards(operation):
    state = create_communication_state(started_at=10, timeout_s=120)
    state = record_communication_message(state, now=20)

    with pytest.raises(ValueError, match="backwards"):
        operation(state, now=19)

