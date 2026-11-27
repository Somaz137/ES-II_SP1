import time
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
    assert [event["kind"] for event in store.events()] == ["limit_ended", "limit_alert"]
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
    assert [event["kind"] for event in store.events()] == ["fault_ended", "limit_alert", "fault"]


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
    assert [event["kind"] for event in store.events()] == ["fault_ended", "fault"]


def reading_line(temp):
    return ('{"type":"reading","temp_c":%s,"humidity_pct":48,"pressure_hpa":1008,"gas_ohms":12000}'
            % temp)


class Room:
    """Feed readings through the real state and status record into one session."""

    def __init__(self, tmp_path, profile=None, **session_options):
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.store = RoomStore(tmp_path / "room.sqlite3")
        if profile is not None:
            self.store.save_profile(profile)
        self.session = RoomSession(self.store, **session_options)
        self.state = create_monitoring_state(0, 120, 120)
        self.transport = SimpleNamespace(connected=True, last_error=None)

    def step(self, now, temp=None, occupancy="occupied"):
        if temp is not None:
            self.state = process_serial_line(self.state, reading_line(temp), now)
        status = status_record(self.state, now, self.transport, monotonic_origin=0, utc_origin=100000)
        self.session.update(status, now, now + 100000, occupancy)
        return status

    def kinds(self):
        return [event["kind"] for event in self.store.events()]


def test_pending_and_active_alerts_carry_condition_and_duration(tmp_path):
    room = Room(tmp_path, {"limits": {"temp_c": [20, 27]}, "hold_s": 9}, demo=True)
    transport = SimulatedTransport()
    seen = {}
    for now in range(0, 61, 3):
        for line in transport.poll(now):
            room.state = process_serial_line(room.state, line, now)
        status = status_record(room.state, now, transport, monotonic_origin=0, utc_origin=100000)
        room.session.update(status, now + 0.5, now + 100000.5, "occupied")
        seen[now] = status
    assert seen[15]["limit_pending"] == [] and seen[15]["limit_alerts"] == []
    assert seen[21]["limit_pending"] == [{
        "metric": "temp_c", "name": "Temperature", "unit": "°C", "direction": "high", "limit": 27,
        "value": 31, "breach_started_at": 100018, "elapsed_s": 3.5, "hold_s": 9, "remaining_s": 5.5}]
    assert seen[21]["limit_alerts"] == []
    assert seen[30]["limit_alerts"] == [{
        "metric": "temp_c", "name": "Temperature", "unit": "°C", "direction": "high", "limit": 27,
        "value": 31, "breach_started_at": 100018, "alert_started_at": 100027, "elapsed_s": 12.5}]
    assert seen[30]["limit_pending"] == []
    assert seen[30]["limit_monitoring"] == {"state": "running", "reason": None,
                                            "message": "Limit monitoring is running."}
    ended, started = room.store.events()
    assert started["kind"] == "limit_alert" and ended["kind"] == "limit_ended"
    assert started["message"] == "Temperature above the configured limit of 27 °C for 9 s. Value 31 °C."
    assert ended["message"] == ("Temperature above the configured limit of 27 °C: alert ended after 33 s. "
                                "Value 24 °C is within the configured limits.")
    assert started["at"] == 100027.5 and ended["id"] > started["id"]


def test_limit_monitoring_reasons(tmp_path):
    room = Room(tmp_path)
    assert room.step(0, 24)["limit_monitoring"]["reason"] == "no_profile"
    room.store.save_profile({"limits": {}, "hold_s": 9})
    assert room.step(3, 24)["limit_monitoring"] == {
        "state": "off", "reason": "no_limits", "message": "No measurement has patient limits enabled."}
    room.store.save_profile({"limits": {"temp_c": [20, 27]}, "hold_s": 9})
    assert room.step(6, 24, "unknown")["limit_monitoring"] == {
        "state": "paused", "reason": "occupancy_unknown",
        "message": "Occupancy is unknown. Limit monitoring is paused."}
    assert room.step(13)["limit_monitoring"] == {
        "state": "paused", "reason": "reading_not_current",
        "message": "The BME680 reading is not current. Limit monitoring is paused."}
    room.store.profile_path.write_text("[]", encoding="utf-8")
    status = room.step(15, 24)
    assert status["limit_monitoring"]["state"] == "running"
    assert status["limit_monitoring"]["reason"] == "profile_invalid"
    assert "last valid profile" in status["limit_monitoring"]["message"]
    fresh = Room(tmp_path / "fresh")
    fresh.store.profile_path.write_text("[]", encoding="utf-8")
    assert fresh.step(0, 24)["limit_monitoring"]["state"] == "off"


def test_occupancy_pause_reasons_are_split(tmp_path):
    room = Room(tmp_path)
    room.store.save_profile({"limits": {"temp_c": [20, 27]}, "hold_s": 9})
    assert room.step(0, 24, "not_seen")["limit_monitoring"] == {
        "state": "paused", "reason": "occupancy_not_seen",
        "message": "No person seen. Limit monitoring is paused."}
    assert room.step(3, 24, "not_occupied")["limit_monitoring"] == {
        "state": "paused", "reason": "occupancy_manual",
        "message": "Set to not occupied by hand. Limit monitoring is paused."}
    assert room.step(6, 24, "unknown")["limit_monitoring"]["reason"] == "occupancy_unknown"


def test_alert_end_texts_name_each_occupancy_cause(tmp_path):
    room = active_alert_room(tmp_path)
    room.step(6, 31, "not_seen")
    assert "because no person is seen." in room.store.events()[0]["message"]
    room = active_alert_room(tmp_path / "b")
    room.step(6, 31, "not_occupied")
    assert "because the room was set to not occupied by hand." in room.store.events()[0]["message"]


def test_note_event_is_logged_on_the_next_update(tmp_path):
    room = Room(tmp_path)
    room.session.note_event("occupancy_override_set", "Occupancy set to occupied by hand at 14:02.")
    room.step(0, 24)
    assert room.store.events()[0]["kind"] == "occupancy_override_set"


def active_alert_room(tmp_path):
    room = Room(tmp_path, {"limits": {"temp_c": [20, 27]}, "hold_s": 3})
    room.step(0, 31)
    assert room.step(3, 31)["limit_alerts"]
    return room


def test_alert_end_by_occupancy_names_reason(tmp_path):
    room = active_alert_room(tmp_path)
    assert not room.step(6, 31, "unknown")["limit_alerts"]
    assert room.kinds() == ["limit_reset_occupancy", "limit_alert"]
    assert room.store.events()[0]["message"] == (
        "Temperature above the configured limit of 27 °C: alert stopped after 3 s because occupancy "
        "is unknown. Last value 31 °C. Limit monitoring is paused.")


def test_alert_end_by_profile_change_names_reason(tmp_path):
    room = active_alert_room(tmp_path)
    room.store.save_profile({"limits": {"temp_c": [20, 28]}, "hold_s": 3})
    assert not room.step(6, 31)["limit_alerts"]
    assert room.kinds() == ["limit_reset_profile", "profile_changed", "limit_alert"]
    assert "because the patient limits changed" in room.store.events()[0]["message"]


def test_alert_end_by_stale_reading_names_reason(tmp_path):
    room = active_alert_room(tmp_path)
    status = room.step(10)
    assert not status["limit_alerts"] and not status["measurement_current"]
    assert room.kinds() == ["limit_reset_reading", "limit_alert"]
    assert "because readings are not current" in room.store.events()[0]["message"]


def test_alert_end_by_reading_gap_names_reason(tmp_path):
    room = active_alert_room(tmp_path)
    assert room.step(5)["limit_alerts"]
    assert not room.step(10, 31)["limit_alerts"]
    assert room.kinds() == ["limit_reset_reading", "limit_alert"]


def test_alert_reversal_names_new_direction(tmp_path):
    room = active_alert_room(tmp_path)
    status = room.step(6, 10)
    assert not status["limit_alerts"]
    assert status["limit_pending"][0]["direction"] == "low"
    assert room.kinds() == ["limit_reversed", "limit_alert"]
    assert room.store.events()[0]["message"] == (
        "Temperature above the configured limit of 27 °C: alert ended after 3 s. "
        "Value 10 °C is below the configured limit of 20 °C.")


def test_configured_reading_gap_is_used_and_published(tmp_path):
    from settings import RUNTIME_DEFAULTS

    timing = {**RUNTIME_DEFAULTS, "reading_gap_limit_s": 10, "fault_check_interval_s": 5}
    room = Room(tmp_path, {"limits": {"temp_c": [20, 27]}, "hold_s": 8}, timing=timing)
    room.step(0, 31)
    status = room.step(8, 31)
    assert status["limit_alerts"] and status["measurement_current"]
    assert status["timing"] == timing
    assert Room(tmp_path / "x").step(0, 24)["timing"] == RUNTIME_DEFAULTS


def test_acknowledgment_logs_distinct_event(tmp_path):
    from monitoring_state import acknowledge_monitoring_communication, evaluate_monitoring_faults

    room = Room(tmp_path)
    room.state = evaluate_monitoring_faults(room.state, 121)
    room.step(121)
    room.state = process_serial_line(room.state, reading_line(24), 122)
    room.step(122)
    room.state = acknowledge_monitoring_communication(room.state, 125)
    room.session.note_acknowledgment()
    room.step(125)
    events = room.store.events()
    assert [event["kind"] for event in events[:2]] == ["fault_ended", "communication_acknowledged"]
    assert events[1]["message"] == "Communication alert acknowledged on the dashboard."
    room.step(128)
    assert room.kinds().count("communication_acknowledged") == 1


def test_gas_resistance_is_stored_but_not_limit_checked(tmp_path):
    import pytest
    from room_store import METRICS, SERIES, validate_profile

    room = Room(tmp_path)
    room.step(0, 24)
    assert room.store.history("gas_ohms", 100000) == [{"at": 99960, "avg": 12000, "min": 12000, "max": 12000}]
    assert "gas_ohms" in SERIES and "gas_ohms" not in METRICS
    with pytest.raises(ValueError):
        validate_profile({"limits": {"gas_ohms": [1, 2]}, "hold_s": 9})


def test_trends_carry_minute_average_minimum_and_maximum(tmp_path):
    store = RoomStore(tmp_path / "room.sqlite3")
    store.publish({}, [("temp_c", 6000, 20), ("temp_c", 6030, 30), ("temp_c", 6059, 25),
                       ("temp_c", 6060, 22), ("dust_mv", 6010, 900), ("temp_c", 6200, 99)], [], 6060)
    trends = store.trends(6100)
    assert list(trends) == ["temp_c", "humidity_pct", "pressure_hpa", "gas_ohms", "dust_mv",
                            "air_quality", "dust_ugm3"]
    assert trends["temp_c"] == [{"at": 6000, "avg": 25, "min": 20, "max": 30},
                                {"at": 6060, "avg": 22, "min": 22, "max": 22}]
    assert trends["dust_mv"] == [{"at": 6000, "avg": 900, "min": 900, "max": 900}]
    assert trends["humidity_pct"] == []
    assert len(store.trends(100000)["temp_c"]) == 0


def test_events_page_by_id(tmp_path):
    store = RoomStore(tmp_path / "room.sqlite3")
    store.publish({}, [], [("fault", f"Event {n}.") for n in range(5)], 100)
    newest = store.events(limit=2)
    assert [event["message"] for event in newest] == ["Event 4.", "Event 3."]
    assert set(newest[0]) == {"id", "at", "kind", "message"}
    older = store.events(before=newest[-1]["id"], limit=10)
    assert [event["message"] for event in older] == ["Event 2.", "Event 1.", "Event 0."]


def test_session_prunes_old_readings_hourly_and_keeps_events(tmp_path):
    day = 86400
    room = Room(tmp_path)
    old = 100000 - 7 * day - 20
    room.store.publish({}, [("temp_c", old, 1), ("temp_c", old + 2, 1)], [("fault", "Old.")], old)
    room.step(0, 24)
    assert room.store.history("temp_c", old + 60) == []
    room.store.publish({}, [("temp_c", old + 10, 1)], [], old)
    room.step(3, 24)
    assert room.store.history("temp_c", old + 60)
    room.step(3603, 24)
    assert room.store.history("temp_c", old + 60) == []
    assert room.kinds()[-1] == "fault"


def test_full_prune_batch_continues_on_next_update(tmp_path):
    room = Room(tmp_path)
    room.session.prune_batch = 2
    old = 100000 - 7 * 86400 - 10
    room.store.publish({}, [("temp_c", old + n, 1) for n in range(5)], [], old)

    def old_rows():
        with room.store.connection() as db:
            return db.execute("SELECT COUNT(*) FROM readings WHERE at < 0").fetchone()[0]

    room.step(0, 24)
    assert old_rows() == 3
    room.step(1)
    assert old_rows() == 1
    room.step(2)
    assert old_rows() == 0


def test_prune_readings_deletes_only_older_rows(tmp_path):
    store = RoomStore(tmp_path / "room.sqlite3")
    store.publish({}, [("temp_c", 10, 1), ("temp_c", 20, 2), ("dust_mv", 15, 3)], [], 20)
    assert store.prune_readings(20) == 2
    assert store.history("temp_c", 30) == [{"at": 0, "avg": 2, "min": 2, "max": 2}]


def test_missing_profile_file_validates_legacy_profile(tmp_path):
    import pytest

    store = RoomStore(tmp_path / "room.sqlite3")
    assert store.load_profile() is None
    store.write("profile", {"limits": {"temp_c": [20, 27]}, "hold_s": 9})
    assert store.load_profile() == {"limits": {"temp_c": [20, 27]}, "hold_s": 9}
    store.write("profile", {"limits": {"temp_c": [27, 20]}, "hold_s": 9})
    with pytest.raises(ValueError, match="legacy"):
        store.load_profile()


CAMERA_TIMING = dict(camera_interval_s=10, occupancy_confirm_s=120, occupancy_confirm_fraction=0.75,
                     occupancy_hold_s=900, occupancy_override_s=900, person_confidence=0.5)


def test_camera_feeds_rule():
    from occupancy import CameraOccupancy

    camera = CameraOccupancy(0, CAMERA_TIMING, detector=object())
    assert camera.snapshot(0)["state"] == "unknown"
    for step in range(12):
        camera.record("seen", step * 10)
    assert camera.snapshot(110)["state"] == "occupied"


def test_camera_assume_occupied_reaches_rule():
    from occupancy import CameraOccupancy

    camera = CameraOccupancy(0, CAMERA_TIMING, detector=object())
    camera.assume_occupied(0)
    assert camera.snapshot(0)["state"] == "occupied"


def test_camera_worker_records_results_without_keeping_frames():
    from occupancy import CameraOccupancy

    class Capture:
        released = 0

        def __init__(self, frame):
            self.frame = frame

        def read(self):
            return (self.frame is not None), self.frame

        def release(self):
            Capture.released += 1

    class Detector:
        def detect(self, frame):
            return frame == "person"

    camera = CameraOccupancy(0, CAMERA_TIMING, detector=Detector())
    for frame in ("person", "empty", None):
        camera.check_once(lambda index, frame=frame: Capture(frame), Detector(), 5)
    assert Capture.released == 3
    assert [c[1] for c in camera.rule._checks] == [True, False, False]
    assert camera.last_check_at == 5


def test_camera_detector_error_records_failed_and_releases(capsys):
    from occupancy import CameraOccupancy

    class Capture:
        released = False

        def read(self):
            return True, "frame"

        def release(self):
            Capture.released = True

    class Detector:
        def detect(self, frame):
            raise RuntimeError("inference broke")

    camera = CameraOccupancy(0, CAMERA_TIMING, detector=Detector())
    camera.check_once(lambda index: Capture(), Detector(), 3)
    assert Capture.released and camera.last_check_at == 3
    assert camera.rule._last_ok_at is None and [c[1] for c in camera.rule._checks] == [False]
    assert "inference broke" in capsys.readouterr().err


def test_camera_model_load_failure_records_failed_and_names_reason(monkeypatch, capsys):
    import person_detector
    from occupancy import CameraOccupancy

    def broken(confidence):
        raise OSError("cannot load model")

    monkeypatch.setattr(person_detector, "PersonDetector", broken)
    timing = {**CAMERA_TIMING, "camera_interval_s": 0.01, "occupancy_confirm_s": 0.1}
    camera = CameraOccupancy(0, timing)
    with camera:
        deadline = time.monotonic() + 2
        while camera.last_check_at is None and time.monotonic() < deadline:
            time.sleep(0.01)
        time.sleep(0.05)
    assert camera.last_check_at is not None and camera.rule._last_ok_at is None
    assert capsys.readouterr().err.count("cannot load model") == 1
