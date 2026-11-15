"""The alarm path through the session and the monitor loop, with simulated I/O."""

import json

import pytest

from simulated_input import SimulatedTransport


def test_simulated_transport_echoes_alarm_commands_at_the_next_poll():
    transport = SimulatedTransport()
    transport.poll(0)
    assert transport.send("ALARM,2\n") is True
    assert transport.poll(0.05) == ['{"type": "alarm", "state": 2}']
    assert transport.poll(0.1) == []
    assert transport.send("\nALARM,1\n") is True
    assert transport.send("ALARM,7\n") is True
    assert transport.poll(0.15) == ['{"type": "alarm", "state": 1}']


def test_simulated_transport_can_stay_silent_or_fail():
    silent, failing = SimulatedTransport(alarm="silent"), SimulatedTransport(alarm="fail")
    assert silent.send("ALARM,2\n") is True and silent.poll(0)[-1].startswith('{"type": "dust"')
    assert failing.send("ALARM,2\n") is False
    assert failing.last_send_error == "Simulated write failure."
    with pytest.raises(ValueError):
        SimulatedTransport(alarm="other")


from alarm import AlarmTracker
from monitoring_loop import run_monitor
from room_session import RoomSession
from room_store import RoomStore
from status_output import status_record

ALERTS = {"communication_timeout_s": 120, "sensor_error_timeout_s": 120}
RUNTIME = {"fault_check_interval_s": 5, "serial_poll_interval_s": 0.25}
PROFILE = {"limits": {"temp_c": [20, 27]}, "hold_s": 9}


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class RaisingTransport(SimulatedTransport):
    def send(self, line):
        raise RuntimeError("driver bug")


class Room:
    """The monitor's publish and fault-check wiring, with a fake clock."""

    def __init__(self, tmp_path, transport, profile=PROFILE):
        self.store = RoomStore(tmp_path / "room.sqlite3")
        self.store.save_profile(profile)
        self.session = RoomSession(self.store, demo=True, alarm=AlarmTracker(2, id_prefix="t"))
        self.transport = transport
        self.clock = Clock()
        self.checks, self.published = [], []
        self.actions = {}  # fault-check time -> callable run before the alarm resend

    def publish(self, state, now, connection):
        record = status_record(state, now, connection, monotonic_origin=0, utc_origin=100000)
        self.session.update(record, now, now + 100000, "occupied",
                            alarm_reply=state.alarm_reply, transport=connection)
        self.published.append((now, record))

    def controls(self, state, now):
        self.checks.append(now)
        if now in self.actions:
            self.actions.pop(now)(now)
        self.session.alarm_fault_check()
        return state

    def run(self, until):
        return run_monitor(self.transport, ALERTS, RUNTIME, self.publish, clock=self.clock,
                           sleep=self.clock.sleep, should_stop=lambda: self.clock.now >= until,
                           apply_controls=self.controls)

    def kinds(self):
        return [event["kind"] for event in reversed(self.store.events(limit=200))]

    def alarm_at(self, now):
        return next(record["alarm"] for at, record in self.published if at >= now)


def test_demo_loop_sounds_confirms_and_clears(tmp_path):
    room = Room(tmp_path, SimulatedTransport())
    room.run(70)
    assert room.alarm_at(1)["state"] == "confirmed" and room.alarm_at(1)["confirmed_level"] == 0
    sounding = room.alarm_at(28)
    assert sounding["wanted_level"] == 2 and sounding["confirmed_level"] == 2
    assert sounding["state"] == "confirmed" and sounding["silence_token"]
    assert room.published[-1][1]["alarm"]["confirmed_level"] == 0
    assert room.kinds().count("alarm_confirmed") == 3
    assert "alarm_unreachable" not in room.kinds()


def monitoring_facts(room):
    """Everything the room reports except the alarm itself."""
    events = [(event["kind"], event["message"]) for event in room.store.events(limit=200)
              if not event["kind"].startswith("alarm_")]
    statuses = {at: {key: value for key, value in record.items() if key != "alarm"}
                for at, record in room.published}
    return room.checks, events, statuses, room.store.history("temp_c", 100100)


@pytest.mark.parametrize("mode, reason", [("fail", "send_failed"), ("silent", "no_confirmation")])
def test_monitoring_is_unchanged_when_the_alarm_cannot_be_reached(tmp_path, mode, reason):
    (tmp_path / "echo").mkdir()
    (tmp_path / mode).mkdir()
    reference = Room(tmp_path / "echo", SimulatedTransport())
    reference.run(45)
    room = Room(tmp_path / mode, SimulatedTransport(alarm=mode))
    state = room.run(45)

    assert room.checks == [5 * n for n in range(1, 9)]
    assert state.reading.last_reading.received_at >= 42
    assert "limit_alert" in room.kinds()
    assert room.published[-1][1]["limit_alerts"]
    assert all(at in [now for now, _ in room.published] for at in room.checks)
    checks, events, statuses, history = monitoring_facts(room)
    ref_checks, ref_events, ref_statuses, ref_history = monitoring_facts(reference)
    assert (checks, events, history) == (ref_checks, ref_events, ref_history)
    # The echo run also publishes when a reply arrives; every other publish is identical.
    assert statuses == {at: ref_statuses[at] for at in statuses}
    final = room.published[-1][1]["alarm"]
    assert final["state"] == "unreachable" and final["reason"] == reason
    assert final["wanted_level"] == 2 and final["confirmed_level"] is None
    assert room.kinds().count("alarm_unreachable") == 1
    assert room.store.read("status")["alarm"]["state"] == "unreachable"


def test_a_raising_send_is_reported_and_publication_continues(tmp_path):
    room = Room(tmp_path, RaisingTransport())
    room.run(30)
    assert room.checks == [5, 10, 15, 20, 25]
    final = room.published[-1][1]["alarm"]
    assert final["state"] == "unreachable" and final["send_error"] == "driver bug"
    assert "limit_alert" in room.kinds()


def test_disconnected_port_reports_not_connected(tmp_path):
    transport = SimulatedTransport()
    transport.connected = False
    room = Room(tmp_path, transport)
    room.run(10)
    assert room.published[-1][1]["alarm"]["reason"] == "not_connected"
    assert room.kinds().count("alarm_unreachable") == 1


def test_silence_through_the_session_logs_once_and_a_new_alert_sounds(tmp_path):
    room = Room(tmp_path, SimulatedTransport())
    assert room.session.silence_alarm("t-1", 100) is False
    results = []

    def silence(now):
        token = room.published[-1][1]["alarm"]["silence_token"]
        results.append(room.session.silence_alarm("wrong", now + 100000))
        results.append(room.session.silence_alarm(token, now + 100000))
        results.append(room.session.silence_alarm(token, now + 100000))

    def add_humidity_limit(now):
        room.store.save_profile({"limits": {"temp_c": [20, 27], "humidity_pct": [50, 60]}, "hold_s": 9})

    room.actions = {30: silence, 40: add_humidity_limit}
    room.run(60)
    assert results == [False, True, False]
    alarm = room.alarm_at(32)
    assert alarm["wanted_level"] == 1 and alarm["confirmed_level"] == 1 and alarm["silenced"]
    assert alarm["silenced_at"] == 100030 and alarm["silence_token"] is None
    silenced = [event for event in room.store.events() if event["kind"] == "alarm_silenced"]
    assert len(silenced) == 1
    assert "Temperature above the configured limit of 27 °C" in silenced[0]["message"]
    assert "LED stays on" in silenced[0]["message"]
    later = [record["alarm"] for at, record in room.published if at > 50]
    assert any(alarm["wanted_level"] == 2 and alarm["silence_token"] and not alarm["silenced"]
               for alarm in later)


class ReadingsStop(SimulatedTransport):
    """The board answers alarm commands but sends no readings."""

    def poll(self, now):
        replies, self.replies = self.replies, []
        return replies


def test_fault_alerts_light_the_led_without_the_buzzer(tmp_path):
    room = Room(tmp_path, ReadingsStop())
    room.run(125)
    record = room.published[-1][1]
    assert record["communication_alert_active"] and not record["limit_alerts"]
    assert record["alarm"]["wanted_level"] == 1 and record["alarm"]["confirmed_level"] == 1
