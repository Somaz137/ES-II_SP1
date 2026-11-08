"""Sensor-fault and pause/resume scenarios; execution is deferred to Linux."""

import pytest

from communication_fault import (
    acknowledge_communication_fault,
    create_communication_state,
    evaluate_communication_fault,
    record_communication_message,
)
from sensor_fault import (
    create_sensor_state,
    evaluate_sensor_fault,
    record_sensor_error,
    record_valid_measurement,
)


def test_startup_does_not_invent_a_sensor_error():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = evaluate_sensor_fault(state, now=500, communication_timed_out=False)

    assert state.error_started_at is None
    assert state.error_elapsed_s == 0
    assert state.last_valid_measurement_at is None
    assert not state.alert_active


def test_first_error_starts_the_wait_at_its_arrival_time():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_sensor_error(state, now=50)

    assert state.error_started_at == 50
    assert not evaluate_sensor_fault(
        state, now=169.999, communication_timed_out=False
    ).alert_active
    assert evaluate_sensor_fault(
        state, now=170, communication_timed_out=False
    ).alert_active


def test_repeated_errors_do_not_restart_the_episode():
    state = create_sensor_state(started_at=0, timeout_s=120)
    for now in (0, 30, 90):
        state = record_sensor_error(state, now=now)

    assert state.error_started_at == 0
    assert state.error_elapsed_s == 90
    assert record_sensor_error(state, now=120).alert_active


def test_uses_the_configured_sensor_timeout():
    state = create_sensor_state(started_at=0, timeout_s=30)
    state = record_sensor_error(state, now=100)

    assert not evaluate_sensor_fault(
        state, now=129.999, communication_timed_out=False
    ).alert_active
    assert evaluate_sensor_fault(
        state, now=130, communication_timed_out=False
    ).alert_active


def test_valid_measurement_resets_a_pending_error():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_sensor_error(state, now=30)
    state = record_valid_measurement(state, now=80)

    assert state.error_started_at is None
    assert state.error_elapsed_s == 0
    assert state.last_valid_measurement_at == 80
    assert not state.alert_active
    assert not evaluate_sensor_fault(
        state, now=500, communication_timed_out=False
    ).alert_active


def test_valid_measurement_automatically_clears_an_active_alert():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_sensor_error(state, now=0)
    state = evaluate_sensor_fault(state, now=120, communication_timed_out=False)
    assert state.alert_active

    state = record_valid_measurement(state, now=125)
    assert not state.alert_active
    assert state.error_elapsed_s == 0
    assert state.error_started_at is None
    assert state.last_valid_measurement_at == 125


def test_paused_time_is_excluded_and_error_recovery_resumes_remaining_time():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_sensor_error(state, now=0)
    state = evaluate_sensor_fault(state, now=60, communication_timed_out=True)
    state = evaluate_sensor_fault(state, now=600, communication_timed_out=True)

    assert state.paused
    assert state.error_elapsed_s == 60
    assert state.error_started_at == 0
    assert not state.alert_active

    state = record_sensor_error(state, now=610)
    assert not state.paused
    assert state.error_elapsed_s == 60
    assert not evaluate_sensor_fault(
        state, now=669.999, communication_timed_out=False
    ).alert_active
    assert evaluate_sensor_fault(
        state, now=670, communication_timed_out=False
    ).alert_active


def test_repeated_outages_preserve_accumulated_active_error_time():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_sensor_error(state, now=0)
    state = evaluate_sensor_fault(state, now=30, communication_timed_out=True)
    state = evaluate_sensor_fault(state, now=100, communication_timed_out=False)
    state = evaluate_sensor_fault(state, now=120, communication_timed_out=True)
    state = record_sensor_error(state, now=200)

    assert state.error_elapsed_s == 50
    assert not evaluate_sensor_fault(
        state, now=269.999, communication_timed_out=False
    ).alert_active
    assert evaluate_sensor_fault(
        state, now=270, communication_timed_out=False
    ).alert_active


def test_communication_timeout_takes_priority_at_the_sensor_boundary():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_sensor_error(state, now=0)
    state = evaluate_sensor_fault(state, now=120, communication_timed_out=True)

    assert state.paused
    assert state.error_elapsed_s == 120
    assert not state.alert_active

    # No waiting time remains if communication returns with the same error.
    resumed = record_sensor_error(state, now=300)
    assert not resumed.paused
    assert resumed.alert_active


def test_valid_measurement_after_a_paused_boundary_does_not_raise_an_alert():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_sensor_error(state, now=0)
    state = evaluate_sensor_fault(state, now=120, communication_timed_out=True)
    state = record_valid_measurement(state, now=300)

    assert not state.paused
    assert not state.alert_active
    assert state.error_elapsed_s == 0


def test_pausing_does_not_clear_an_already_raised_sensor_alert():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_sensor_error(state, now=0)
    state = evaluate_sensor_fault(state, now=120, communication_timed_out=False)
    state = evaluate_sensor_fault(state, now=130, communication_timed_out=True)
    state = evaluate_sensor_fault(state, now=1000, communication_timed_out=True)

    assert state.paused
    assert state.error_elapsed_s == 130
    assert state.alert_active

    assert not record_valid_measurement(state, now=1001).alert_active


def test_error_after_an_outage_starts_a_new_episode_if_none_existed():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = evaluate_sensor_fault(state, now=60, communication_timed_out=True)
    state = record_sensor_error(state, now=100)

    assert state.error_started_at == 100
    assert state.error_elapsed_s == 0
    assert not state.paused
    assert not state.alert_active


def test_errors_and_outages_do_not_fake_a_valid_measurement():
    state = create_sensor_state(started_at=0, timeout_s=120)
    state = record_valid_measurement(state, now=10)
    state = record_sensor_error(state, now=20)
    state = evaluate_sensor_fault(state, now=60, communication_timed_out=True)
    state = record_sensor_error(state, now=90)

    assert state.last_valid_measurement_at == 10


def test_acknowledging_communication_does_not_resume_the_sensor_timer():
    communication = create_communication_state(started_at=0, timeout_s=30)
    sensor = record_sensor_error(
        create_sensor_state(started_at=0, timeout_s=120), now=0
    )
    communication = record_communication_message(communication, now=0)
    communication = evaluate_communication_fault(communication, now=30)
    sensor = evaluate_sensor_fault(
        sensor, now=30, communication_timed_out=communication.timed_out
    )

    communication = acknowledge_communication_fault(communication, now=60)
    sensor = evaluate_sensor_fault(
        sensor, now=60, communication_timed_out=communication.timed_out
    )

    assert not communication.alert_active
    assert communication.timed_out
    assert sensor.paused
    assert sensor.error_elapsed_s == 30


def test_restored_communication_resumes_despite_an_unacknowledged_alert():
    communication = create_communication_state(started_at=0, timeout_s=30)
    sensor = record_sensor_error(
        create_sensor_state(started_at=0, timeout_s=120), now=0
    )
    communication = record_communication_message(communication, now=0)
    communication = evaluate_communication_fault(communication, now=30)
    sensor = evaluate_sensor_fault(
        sensor, now=30, communication_timed_out=communication.timed_out
    )

    communication = record_communication_message(communication, now=100)
    sensor = record_sensor_error(sensor, now=100)
    sensor = evaluate_sensor_fault(
        sensor, now=100, communication_timed_out=communication.timed_out
    )

    assert communication.alert_active
    assert not communication.timed_out
    assert not sensor.paused
    assert sensor.error_elapsed_s == 30


def test_updates_preserve_previous_state_snapshots():
    original = create_sensor_state(started_at=0, timeout_s=120)
    updated = record_sensor_error(original, now=0)

    assert original.error_started_at is None
    assert updated.error_started_at == 0


@pytest.mark.parametrize("timeout", [0, -1, True, "120", float("inf"), float("nan")])
def test_rejects_invalid_timeouts(timeout):
    with pytest.raises(ValueError, match="timeout_s"):
        create_sensor_state(started_at=0, timeout_s=timeout)


@pytest.mark.parametrize("now", [True, "0", float("inf"), float("nan")])
def test_rejects_invalid_start_times(now):
    with pytest.raises(ValueError, match="started_at"):
        create_sensor_state(started_at=now, timeout_s=120)


@pytest.mark.parametrize("value", [0, 1, None, "false"])
def test_requires_a_boolean_communication_timeout_flag(value):
    state = create_sensor_state(started_at=0, timeout_s=120)
    with pytest.raises(ValueError, match="communication_timed_out"):
        evaluate_sensor_fault(state, now=1, communication_timed_out=value)


@pytest.mark.parametrize("operation", [record_sensor_error, record_valid_measurement])
def test_rejects_message_times_moving_backwards(operation):
    state = create_sensor_state(started_at=10, timeout_s=120)
    state = record_sensor_error(state, now=20)
    with pytest.raises(ValueError, match="backwards"):
        operation(state, now=19)


def test_rejects_evaluation_time_moving_backwards():
    state = create_sensor_state(started_at=10, timeout_s=120)
    state = record_sensor_error(state, now=20)
    with pytest.raises(ValueError, match="backwards"):
        evaluate_sensor_fault(state, now=19, communication_timed_out=False)

