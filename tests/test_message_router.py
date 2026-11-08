"""Exercise the real parser and trackers together, with supplied event times."""

import json

import pytest

from message_router import process_serial_line
from monitoring_state import (
    acknowledge_monitoring_communication,
    create_monitoring_state,
    evaluate_monitoring_faults,
    monitoring_status,
)

VALID = json.dumps({"type": "reading", "temp_c": 24, "humidity_pct": 45,
                    "pressure_hpa": 1005, "gas_ohms": 12000})
ERROR = '{"type":"error","message":"Sensor unavailable"}'
INCOMPLETE = '{"type":"reading","temp_c":25}'


def start(communication_timeout_s=120, sensor_error_timeout_s=120):
    return create_monitoring_state(0, communication_timeout_s, sensor_error_timeout_s)


def test_startup_waits_with_empty_values_then_communication_times_out():
    state = evaluate_monitoring_faults(start(), 119)
    assert state.reading.last_reading is None
    assert monitoring_status(state) == "waiting_for_first_measurement"
    assert not state.sensor.alert_active
    state = evaluate_monitoring_faults(state, 120)
    assert monitoring_status(state) == "communication_lost"
    assert state.communication.alert_active
    assert state.sensor.paused


def test_valid_reading_updates_both_trackers_and_committed_time():
    original = start()
    state = process_serial_line(original, VALID, 10)
    assert state.reading.last_reading.temp_c == 24
    assert state.reading.last_reading.received_at == 10
    assert state.communication.last_message_at == 10
    assert state.sensor.last_valid_measurement_at == 10
    assert monitoring_status(state) == "fresh"
    assert original.reading.last_reading is None


@pytest.mark.parametrize("line,status", [(ERROR, "sensor_error"), (INCOMPLETE, "incomplete")])
def test_bad_measurement_updates_contact_but_preserves_values_and_time(line, status):
    state = process_serial_line(start(), VALID, 10)
    saved = state.reading.last_reading
    state = process_serial_line(state, line, 20)
    assert state.reading.last_reading is saved
    assert state.reading.last_reading.received_at == 10
    assert state.sensor.last_valid_measurement_at == 10
    assert state.communication.last_message_at == 20
    assert monitoring_status(state) == status
    assert state.reading.diagnostic
    assert state.sensor.error_started_at == 20
    assert not state.sensor.alert_active


def test_error_before_first_measurement_has_empty_values_and_explicit_status():
    state = process_serial_line(start(), ERROR, 10)
    assert state.reading.last_reading is None
    assert monitoring_status(state) == "sensor_error"


def test_repeated_errors_do_not_restart_wait_and_valid_measurement_clears():
    state = process_serial_line(start(), ERROR, 10)
    state = process_serial_line(state, INCOMPLETE, 70)
    state = process_serial_line(state, ERROR, 130)
    assert state.sensor.error_started_at == 10
    assert state.sensor.error_elapsed_s == 120
    assert state.sensor.alert_active
    assert not state.communication.timed_out
    state = process_serial_line(state, VALID, 131)
    assert not state.sensor.alert_active
    assert state.sensor.error_started_at is None
    assert state.sensor.error_elapsed_s == 0
    assert monitoring_status(state) == "fresh"


@pytest.mark.parametrize("line", ["garbage", "[]", '{"type":"other"}'])
def test_ignored_line_still_checks_timeouts_without_changing_input(line):
    state = process_serial_line(start(), VALID, 10)
    saved = state.reading
    state = process_serial_line(state, line, 130)
    assert state.reading is saved
    assert state.communication.last_message_at == 10
    assert state.communication.timed_out
    assert state.communication.alert_active
    assert monitoring_status(state) == "communication_lost"


def test_late_valid_recovery_keeps_communication_alert_until_acknowledged():
    state = process_serial_line(start(), VALID, 120)
    assert not state.communication.timed_out
    assert state.communication.alert_active
    assert not state.sensor.alert_active
    state = acknowledge_monitoring_communication(state, 121)
    assert not state.communication.alert_active
    assert state.communication.last_message_at == 120
    assert state.reading.last_reading.received_at == 120


def test_acknowledgment_during_silence_preserves_pause_and_realerts():
    state = process_serial_line(start(), ERROR, 10)
    state = evaluate_monitoring_faults(state, 130)
    assert state.sensor.paused
    assert not state.sensor.alert_active
    state = acknowledge_monitoring_communication(state, 140)
    assert state.sensor.paused
    assert state.communication.timed_out
    assert not state.communication.alert_active
    assert state.communication.last_message_at == 10
    state = evaluate_monitoring_faults(state, 259)
    assert not state.communication.alert_active
    state = evaluate_monitoring_faults(state, 260)
    assert state.communication.alert_active


def test_pause_excludes_outage_and_returning_error_resumes_remaining_wait():
    state = process_serial_line(start(communication_timeout_s=20), ERROR, 10)
    state = evaluate_monitoring_faults(state, 30)
    assert state.sensor.error_elapsed_s == 20
    state = process_serial_line(state, ERROR, 100)
    assert state.sensor.error_elapsed_s == 20
    assert not state.sensor.paused
    assert state.communication.alert_active
    for now in (110, 120, 130, 140, 150, 160, 170, 180, 190, 200):
        state = process_serial_line(state, ERROR, now)
    assert state.sensor.error_elapsed_s == 120
    assert state.sensor.alert_active


def test_valid_recovery_at_sensor_deadline_clears_without_new_sensor_alert():
    state = process_serial_line(start(), ERROR, 10)
    state = process_serial_line(state, ERROR, 70)
    state = process_serial_line(state, VALID, 130)
    assert not state.sensor.alert_active
    assert state.sensor.error_elapsed_s == 0


def test_late_error_without_prior_poll_detects_silence_before_resuming():
    state = process_serial_line(start(communication_timeout_s=20), ERROR, 10)
    state = process_serial_line(state, ERROR, 100)
    assert state.communication.alert_active
    assert not state.communication.timed_out
    assert not state.sensor.paused
    # A pause starts only when supplied, not retroactively at physical loss.
    assert state.sensor.error_elapsed_s == 90
    assert not state.sensor.alert_active


def test_custom_sensor_timeout_is_used_independently():
    state = process_serial_line(start(sensor_error_timeout_s=5), ERROR, 10)
    state = evaluate_monitoring_faults(state, 15)
    assert state.sensor.alert_active
    assert not state.communication.timed_out


@pytest.mark.parametrize("operation", [
    lambda s, t: process_serial_line(s, VALID, t),
    lambda s, t: process_serial_line(s, "garbage", t),
    evaluate_monitoring_faults,
    acknowledge_monitoring_communication,
])
@pytest.mark.parametrize("now", [9, True, float("nan"), float("inf")])
def test_operations_reject_invalid_or_backwards_time(operation, now):
    state = process_serial_line(start(), VALID, 10)
    with pytest.raises(ValueError):
        operation(state, now)


def test_non_text_input_remains_a_caller_error_without_mutating_state():
    state = start()
    with pytest.raises(TypeError):
        process_serial_line(state, None, 10)
    assert state.communication.last_updated_at == 0
