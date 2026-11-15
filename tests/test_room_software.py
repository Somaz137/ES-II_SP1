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
