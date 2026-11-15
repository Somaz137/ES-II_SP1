from types import SimpleNamespace

from monitoring_state import create_monitoring_state, process_serial_line
from room_session import RoomSession
from room_store import RoomStore
from simulated_input import SimulatedTransport
from status_output import status_record


def test_simulated_alert_recovers_and_persists(tmp_path):
    store = RoomStore(tmp_path / "demo.sqlite3")
    store.save_profile({"limits": {"temp_c": [20, 27]}, "hold_s": 9})
    session = RoomSession(store, demo=True)
    state = create_monitoring_state(0, 120, 120)
    transport = SimulatedTransport()
    for now in range(0, 61, 3):
        for line in transport.poll(now):
            state = process_serial_line(state, line, now)
        status = status_record(state, now, transport, monotonic_origin=0, utc_origin=100000)
        session.update(status, now, now + 100000, "occupied")
        assert bool(status["limit_alerts"]) == (27 <= now < 60)
    assert [kind for _, kind, _ in store.events()] == ["limit_ended", "limit_alert"]
    assert store.read("status")["demo"]
    assert len(store.history("temp_c", 100060)) == 2
    assert store.history("dust_mv", 100060)


def test_unknown_occupancy_and_updated_profile_restart_timer(tmp_path):
    store = RoomStore(tmp_path / "room.sqlite3")
    store.save_profile({"limits": {"temp_c": [20, 27]}, "hold_s": 6})
    session = RoomSession(store)
    state = create_monitoring_state(0, 120, 120)
    transport = SimpleNamespace(connected=True, last_error=None)
    for now in range(0, 22, 3):
        if now == 15:
            store.save_profile({"limits": {"temp_c": [20, 28]}, "hold_s": 6})
        state = process_serial_line(state, '{"type":"reading","temp_c":31,"humidity_pct":48,"pressure_hpa":1008,"gas_ohms":12000}', now)
        status = status_record(state, now, transport, monotonic_origin=0, utc_origin=100000)
        session.update(status, now, now + 100000, "unknown" if now == 6 else "occupied")
        assert bool(status["limit_alerts"]) == (now == 21)



def test_invalid_profile_preserves_limits_and_logs_recovery(tmp_path):
    store = RoomStore(tmp_path / "room.sqlite3")
    profile = {"limits": {"temp_c": [20, 27]}, "hold_s": 6}
    store.save_profile(profile)
    session = RoomSession(store)
    state = create_monitoring_state(0, 120, 120)
    transport = SimpleNamespace(connected=True, last_error=None)
    line = '{"type":"reading","temp_c":31,"humidity_pct":48,"pressure_hpa":1008,"gas_ohms":12000}'
    for now in (0, 3, 6, 9):
        if now == 3:
            store.profile_path.write_text("[]", encoding="utf-8")
        if now == 9:
            store.save_profile(profile)
        state = process_serial_line(state, line, now)
        status = status_record(state, now, transport, monotonic_origin=0, utc_origin=100000)
        session.update(status, now, now + 100000, "occupied")
        assert bool(status["profile_error"]) == (now in (3, 6))
        assert bool(status["limit_alerts"]) == (now >= 6)
    assert [event[1] for event in store.events()] == ["fault_ended", "limit_alert", "fault"]


def test_contact_loss_and_acknowledgment_persist_in_event_history(tmp_path):
    from monitoring_state import acknowledge_monitoring_communication, evaluate_monitoring_faults

    store = RoomStore(tmp_path / "room.sqlite3")
    session = RoomSession(store)
    state = create_monitoring_state(0, 120, 120)
    transport = SimpleNamespace(connected=True, last_error=None)
    line = '{"type":"reading","temp_c":31,"humidity_pct":48,"pressure_hpa":1008,"gas_ohms":12000}'
    state = process_serial_line(state, line, 1)
    state = evaluate_monitoring_faults(state, 121)
    status = status_record(state, 121, transport, monotonic_origin=0, utc_origin=100000)
    session.update(status, 121, 100121, "occupied")
    assert not status["measurement_current"]
    assert status["last_reading"]["temp_c"] == 31
    state = process_serial_line(state, line, 122)
    state = process_serial_line(state, '{"type":"dust","sensor_mv":920}', 122)
    status = status_record(state, 122, transport, monotonic_origin=0, utc_origin=100000)
    session.update(status, 122, 100122, "occupied")
    assert status["measurement_current"] and status["communication_alert_active"]
    state = acknowledge_monitoring_communication(state, 123)
    status = status_record(state, 123, transport, monotonic_origin=0, utc_origin=100000)
    session.update(status, 123, 100123, "occupied")
    assert [event[1] for event in store.events()] == ["fault_ended", "fault"]
