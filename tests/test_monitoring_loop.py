"""Deferred Linux integration scenarios using real parser/trackers, fake time/I/O."""

import json

import pytest

from monitoring_loop import run_monitor
from status_output import status_record
from serial_transport import SerialTransport

ALERTS = {"communication_timeout_s": 120, "sensor_error_timeout_s": 120}
RUNTIME = {"fault_check_interval_s": 5, "serial_poll_interval_s": 1}
READING = json.dumps({"type": "reading", "temp_c": 24, "humidity_pct": 45,
                      "pressure_hpa": 1005, "gas_ohms": 12000,
                      "bsec": {"stabilization_status": 1, "run_in_status": 1,
                               "iaq_accuracy": 3}})


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class Transport:
    connected = False
    last_error = None
    closed = False

    def __init__(self, events=None):
        self.events = events or {}

    def poll(self, now):
        return self.events.get(now, [])

    def close(self):
        self.closed = True


def run(events, until=126):
    clock, transport, reports = Clock(), Transport(events), []
    state = run_monitor(
        transport, ALERTS, RUNTIME, lambda s, t, io: reports.append((t, s)),
        clock=clock, sleep=clock.sleep, should_stop=lambda: clock.now >= until,
    )
    assert transport.closed
    return state, reports


def test_no_port_or_input_still_alerts_at_normal_startup_timeout():
    state, reports = run({})
    first_alert = next(t for t, s in reports if s.communication.alert_active)
    assert first_alert == 120
    assert state.reading.last_reading is None


def test_late_recovery_keeps_values_then_restores_contact_with_latched_alert():
    state, reports = run({0: [READING], 124: [READING]})
    outage = next(s for t, s in reports if t == 120)
    assert outage.communication.timed_out
    assert outage.reading.last_reading.received_at == 0
    assert state.reading.last_reading.received_at == 124
    assert not state.communication.timed_out
    assert state.communication.alert_active


def test_recognized_errors_keep_contact_but_sensor_alerts_and_retains_reading():
    error = '{"type":"error","message":"sensor failed"}'
    events = {0: [READING], **{t: [error] for t in range(1, 126, 3)}}
    state, _ = run(events)
    assert not state.communication.alert_active
    assert state.sensor.alert_active
    assert state.reading.last_reading.received_at == 0


def test_garbled_noise_does_not_keep_communication_alive():
    state, _ = run({t: ["boot text"] for t in range(126)})
    assert state.communication.alert_active
    assert state.communication.last_message_at is None


def test_output_preserves_timestamp_and_masks_calibration_on_outage():
    state, reports = run({0: [READING]})
    transport = Transport()
    initial = next(s for t, s in reports if s.reading.last_reading is not None)
    before = status_record(initial, 0, transport, monotonic_origin=0, utc_origin=1000)
    after = status_record(state, 125, transport, monotonic_origin=0, utc_origin=1000)
    assert before["gas_calibration"] == "calibrated"
    assert after["gas_calibration"] == "unavailable"
    assert after["gas_warmup"] == "unavailable"
    assert after["measurement_age_s"] == 125
    assert after["last_measurement_received_utc_estimate"] == before["last_measurement_received_utc_estimate"]


def test_keyboard_interrupt_closes_transport():
    transport = Transport()

    def interrupt(*_):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        run_monitor(transport, ALERTS, RUNTIME, interrupt)
    assert transport.closed


def test_real_transport_reconnect_does_not_reset_monitor_startup_timeout():
    clock, attempts, reports = Clock(), [], []

    def missing_port(*_):
        attempts.append(clock.now)
        raise OSError("missing")

    transport = SerialTransport("explicit", 115200, 5, missing_port)
    state = run_monitor(
        transport, ALERTS, RUNTIME, lambda s, t, io: reports.append((t, s)),
        clock=clock, sleep=clock.sleep, should_stop=lambda: clock.now >= 126,
    )
    assert attempts[:3] == [0, 5, 10]
    assert state.communication.started_at == 0
    assert state.communication.alert_active
    assert next(t for t, s in reports if s.communication.alert_active) == 120


def test_delayed_tick_uses_current_time_without_replaying_old_times():
    clock, transport, times = Clock(), Transport(), []

    def jump(_):
        clock.now += 121

    state = run_monitor(
        transport, ALERTS, RUNTIME, lambda s, t, io: times.append(t),
        clock=clock, sleep=jump, should_stop=lambda: clock.now >= 242,
    )
    assert times == [0, 121]
    assert state.communication.alert_active
