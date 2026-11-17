import time

import pytest

from room_store import RoomStore


def test_dashboard_renders_and_saves_profile(tmp_path):
    pytest.importorskip("flask")
    from dashboard import create_app

    path = tmp_path / "demo.sqlite3"
    client = create_app(path, demo=True).test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Simulation" in response.data
    assert client.get("/api/room").json["status"] is None
    response = client.post("/profile", data={"temp_c_low": 20, "temp_c_high": 27, "hold_s": 9})
    assert response.status_code == 303
    store = RoomStore(path)
    assert store.load_profile() == {"limits": {"temp_c": [20, 27]}, "hold_s": 9}
    assert client.post("/profile", data={"hold_s": 0}).status_code == 400
    assert client.post("/profile", data={"hold_s": 9}, headers={"Origin": "http://example.com"}).status_code == 403
    store.write("status", {"communication_alert_id": "example", "communication_timed_out": False,
                           "updated_at": time.time()})
    assert client.post("/acknowledge", data={"alert_id": "old"}).status_code == 409
    assert client.post("/acknowledge", data={"alert_id": "example"}).status_code == 303
    assert store.read("communication_ack") == "example"


from types import SimpleNamespace

from monitoring_state import create_monitoring_state, process_serial_line
from room_session import RoomSession
from settings import RUNTIME_DEFAULTS
from status_output import status_record

API_KEYS = {"status", "profile", "profile_error", "trends", "events", "events_has_more",
            "health", "timing", "now"}
HEALTH_KEYS = {"monitor", "serial", "bme680", "dust", "occupancy", "profile", "alarm"}
LINE = '{"type":"reading","temp_c":%s,"humidity_pct":48,"pressure_hpa":1008,"gas_ohms":12000}'


@pytest.fixture
def app_store(tmp_path):
    pytest.importorskip("flask")
    from dashboard import create_app

    path = tmp_path / "room.sqlite3"
    return create_app(path).test_client(), RoomStore(path)


def publish_live(store, temps, *, timing=None, occupancy="occupied", extra=None):
    """Run real readings through the session with the wall clock anchored to now."""
    session = RoomSession(store, timing=timing)
    state = create_monitoring_state(0, 120, 120)
    transport = SimpleNamespace(connected=True, last_error=None)
    anchor = time.time() - 3 * (len(temps) - 1)
    for index, temp in enumerate(temps):
        now = 3 * index
        state = process_serial_line(state, LINE % temp, now)
        state = process_serial_line(state, '{"type":"dust","sensor_mv":920}', now)
        status = status_record(state, now, transport, monotonic_origin=0, utc_origin=anchor)
        status.update(extra or {"occupancy_source": "camera", "occupancy_observation_age_s": 4})
        session.update(status, now, anchor + now, occupancy)
    return session


def test_api_without_status_uses_defaults(app_store):
    client, _ = app_store
    data = client.get("/api/room").json
    assert set(data) == API_KEYS
    assert data["status"] is None and data["profile"] is None and data["profile_error"] is None
    assert data["timing"] == RUNTIME_DEFAULTS
    assert data["events"] == [] and data["events_has_more"] is False
    assert set(data["health"]) == HEALTH_KEYS
    assert data["health"]["monitor"] == {"state": "waiting", "updated_at": None, "age_s": None}
    assert data["health"]["serial"]["state"] == "unknown"
    assert set(data["trends"]) == {"temp_c", "humidity_pct", "pressure_hpa", "gas_ohms", "dust_mv",
                                   "air_quality", "dust_ugm3"}
    assert data["trends"]["gas_ohms"] == {"name": "Gas resistance", "unit": "Ω",
                                          "limit_checked": False, "estimate": False, "buckets": []}
    assert data["trends"]["air_quality"] == {"name": "Air quality index", "unit": "",
                                             "limit_checked": False, "estimate": True, "buckets": []}
    assert data["trends"]["dust_ugm3"]["estimate"] is True
    assert data["trends"]["temp_c"]["limit_checked"] is True
    assert abs(data["now"] - time.time()) < 5


def test_api_returns_alert_profile_trends_and_health(app_store):
    client, store = app_store
    profile = {"limits": {"temp_c": [20, 27]}, "hold_s": 3}
    store.save_profile(profile)
    timing = {**RUNTIME_DEFAULTS, "status_stale_after_s": 30, "fault_check_interval_s": 5}
    publish_live(store, [31, 31, 31], timing=timing)
    data = client.get("/api/room?metric=ignored").json
    assert data["profile"] == {**profile, "label": ""} and data["timing"] == timing
    alert = data["status"]["limit_alerts"][0]
    assert {key: alert[key] for key in ("metric", "direction", "limit", "value")} == {
        "metric": "temp_c", "direction": "high", "limit": 27, "value": 31}
    assert data["status"]["limit_monitoring"]["state"] == "running"
    assert [event["kind"] for event in data["events"]] == ["limit_alert"]
    assert set(data["events"][0]) == {"id", "at", "kind", "message"}
    for key in ("temp_c", "humidity_pct", "pressure_hpa", "gas_ohms", "dust_mv"):
        assert data["trends"][key]["buckets"], key
        assert set(data["trends"][key]["buckets"][0]) == {"at", "avg", "min", "max"}
    temps = data["trends"]["temp_c"]["buckets"]
    assert [bucket["at"] for bucket in temps] == sorted(bucket["at"] for bucket in temps)
    health = data["health"]
    assert health["monitor"]["state"] == "current" and health["monitor"]["age_s"] < 5
    assert health["serial"]["state"] == "connected" and health["serial"]["error"] is None
    assert health["bme680"]["state"] == "fresh" and health["bme680"]["measurement_current"]
    assert health["dust"]["state"] == "fresh"
    assert health["occupancy"] == {"state": "occupied", "reported_state": "occupied",
                                   "source": "camera", "observation_age_s": pytest.approx(4, abs=2)}
    assert health["profile"] == {"state": "loaded", "reported_state": "loaded", "error": None}


def test_health_ages_count_from_server_time_and_overdue_status_is_not_current(app_store):
    client, store = app_store
    publish_live(store, [24], extra={"occupancy_source": "none", "occupancy_observation_age_s": None},
                 occupancy="unknown")
    status = store.read("status")
    status["updated_at"] -= 40
    store.write("status", status)
    health = client.get("/api/room").json["health"]
    assert health["monitor"]["state"] == "overdue" and health["monitor"]["age_s"] >= 40
    assert health["bme680"]["measurement_age_s"] >= 40
    assert health["bme680"]["state"] == "unknown" and health["bme680"]["reported_state"] == "fresh"
    assert health["occupancy"]["source"] == "none" and health["occupancy"]["observation_age_s"] is None
    assert health["profile"]["reported_state"] == "none"


def test_events_page_through_query_parameters(app_store):
    client, store = app_store
    store.publish({}, [], [("fault", f"Event {n}.") for n in range(5)], 100)
    first = client.get("/api/room?limit=2").json
    assert [event["message"] for event in first["events"]] == ["Event 4.", "Event 3."]
    assert first["events_has_more"] is True
    older = client.get(f"/api/room?limit=10&events_before={first['events'][-1]['id']}").json
    assert [event["message"] for event in older["events"]] == ["Event 2.", "Event 1.", "Event 0."]
    assert older["events_has_more"] is False
    store.publish({}, [], [("fault", "More.")] * 250, 100)
    assert len(client.get("/api/room?limit=1000").json["events"]) == 200
    for query in ("limit=0", "limit=x", "events_before=-1", "events_before=abc"):
        assert client.get("/api/room?" + query).status_code == 400, query


def test_dashboard_reports_its_own_profile_error(app_store):
    client, store = app_store
    store.profile_path.write_text("[]", encoding="utf-8")
    data = client.get("/api/room").json
    assert data["profile"] is None and data["profile_error"]


@pytest.mark.parametrize("form, message", [
    ({"temp_c_low": "20", "hold_s": "9"}, "Enter both Temperature limits, or leave both blank."),
    ({"humidity_pct_high": "60", "hold_s": "9"}, "Enter both Humidity limits, or leave both blank."),
    ({"temp_c_low": "20", "temp_c_high": "27", "hold_s": ""}, "Enter the sustained duration in seconds."),
    ({"temp_c_low": "20", "temp_c_high": "abc", "hold_s": "9"}, "Temperature upper limit must be a finite number."),
    ({"temp_c_low": "inf", "temp_c_high": "27", "hold_s": "9"}, "Temperature lower limit must be a finite number."),
    ({"temp_c_low": "27", "temp_c_high": "20", "hold_s": "9"}, "Temperature lower limit must be less than the upper limit."),
    ({"hold_s": "-1"}, "The sustained duration must be positive."),
    ({"hold_s": "soon"}, "The sustained duration must be a finite number of seconds."),
])
def test_profile_form_errors_name_the_field_and_keep_input(app_store, form, message):
    client, store = app_store
    response = client.post("/profile", data=form)
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert message in page
    assert "could not convert" not in page
    for key, value in form.items():
        if value:
            assert f'name="{key}" value="{value}"' in page or f'name="{key}" required value="{value}"' in page
    assert store.load_profile() is None


@pytest.mark.parametrize("status", [
    {"communication_alert_id": "token", "updated_at": time.time()},
    {"communication_alert_id": "token", "communication_timed_out": False},
    {"communication_alert_id": "token", "communication_timed_out": False, "updated_at": "now"},
])
def test_acknowledge_with_incomplete_status_is_rejected(app_store, status):
    client, store = app_store
    store.write("status", status)
    assert client.post("/acknowledge", data={"alert_id": "token"}).status_code == 409
    assert store.read("communication_ack") is None


def test_acknowledge_uses_published_staleness_limit(app_store):
    client, store = app_store
    status = {"communication_alert_id": "token", "communication_timed_out": False,
              "updated_at": time.time() - 20}
    store.write("status", status)
    assert client.post("/acknowledge", data={"alert_id": "token"}).status_code == 409
    store.write("status", {**status, "timing": {**RUNTIME_DEFAULTS, "status_stale_after_s": 30}})
    assert client.post("/acknowledge", data={"alert_id": "token"}).status_code == 303
    store.write("status", {**status, "communication_timed_out": True, "updated_at": time.time()})
    assert client.post("/acknowledge", data={"alert_id": "token"}).status_code == 409


def test_requests_for_other_hosts_and_cross_site_posts_are_refused(app_store):
    client, _ = app_store
    assert client.get("/api/room", headers={"Host": "example.com"}).status_code == 403
    assert client.get("/", headers={"Host": "localhost:5000"}).status_code == 200
    assert client.post("/profile", data={"hold_s": "9"},
                       headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_page_lists_every_stored_series(app_store):
    client, _ = app_store
    page = client.get("/").get_data(as_text=True)
    for key in ("temp_c", "humidity_pct", "pressure_hpa", "gas_ohms", "dust_mv", "air_quality", "dust_ugm3"):
        assert f'<option value="{key}"' in page and f'id="{key}"' in page


ALARM = {"wanted_level": 2, "requested_level": 2, "confirmed_level": 2, "state": "confirmed",
         "reason": None, "silenced": False, "silenced_at": None, "silence_token": "run-1",
         "confirmation_age_s": 1.5, "send_error": None}


def test_silence_request_is_stored_for_the_monitor(app_store):
    client, store = app_store
    store.write("status", {"updated_at": time.time(), "alarm": ALARM})
    assert client.post("/silence", data={"token": "run-1"}).status_code == 303
    assert store.read("alarm_silence") == "run-1"


@pytest.mark.parametrize("status, token, reason", [
    (None, "run-1", "No current monitor status"),
    ({"updated_at": time.time() - 40, "alarm": ALARM}, "run-1", "No current monitor status"),
    ({"updated_at": "now", "alarm": ALARM}, "run-1", "No current monitor status"),
    ({"updated_at": time.time()}, "run-1", "No local alarm state"),
    ({"updated_at": time.time(), "alarm": "on"}, "run-1", "No local alarm state"),
    ({"updated_at": time.time(), "alarm": {**ALARM, "silence_token": None}}, "run-1",
     "No unsilenced limit alert"),
    ({"updated_at": time.time(), "alarm": ALARM}, "run-2", "changed"),
    ({"updated_at": time.time(), "alarm": ALARM}, "", "changed"),
])
def test_silence_without_an_unsilenced_alert_is_rejected(app_store, status, token, reason):
    client, store = app_store
    if status is not None:
        store.write("status", status)
    response = client.post("/silence", data={"token": token})
    assert response.status_code == 409
    assert reason in response.get_data(as_text=True)
    assert store.read("alarm_silence") is None


def test_cross_site_silence_is_refused(app_store):
    client, store = app_store
    store.write("status", {"updated_at": time.time(), "alarm": ALARM})
    assert client.post("/silence", data={"token": "run-1"},
                       headers={"Origin": "http://example.com"}).status_code == 403
    assert client.post("/silence", data={"token": "run-1"},
                       headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.post("/silence", data={"token": "run-1"},
                       headers={"Host": "example.com"}).status_code == 403
    assert store.read("alarm_silence") is None


def test_alarm_health_entry(app_store):
    client, store = app_store
    assert client.get("/api/room").json["health"]["alarm"] == {
        "state": "unknown", "reported_state": None, "wanted_level": None, "confirmed_level": None,
        "silenced": None, "confirmation_age_s": None}
    store.write("status", {"updated_at": time.time() - 2, "alarm": ALARM})
    data = client.get("/api/room").json
    assert data["status"]["alarm"] == ALARM
    health = data["health"]["alarm"]
    assert health["state"] == "confirmed" and health["reported_state"] == "confirmed"
    assert health["wanted_level"] == 2 and health["confirmed_level"] == 2 and health["silenced"] is False
    assert health["confirmation_age_s"] == pytest.approx(3.5, abs=1)
    store.write("status", {"updated_at": time.time() - 40, "alarm": ALARM})
    health = client.get("/api/room").json["health"]["alarm"]
    assert health["state"] == "unknown" and health["reported_state"] == "confirmed"
    store.write("status", {"updated_at": time.time()})
    assert client.get("/api/room").json["health"]["alarm"]["reported_state"] == "unknown"


def test_page_has_hidden_silence_control(app_store):
    client, _ = app_store
    page = client.get("/").get_data(as_text=True)
    assert 'id="alarm"' in page
    assert '<form id="silence" action="/silence" method="post" hidden>' in page
    assert 'name="token"' in page and "Silence alarm" in page


def test_label_is_trimmed_saved_returned_and_escaped(app_store):
    client, store = app_store
    form = {"temp_c_low": "20", "temp_c_high": "27", "hold_s": "9"}
    assert client.post("/profile", data={**form, "label": "  Bed 3 "}).status_code == 303
    assert store.load_profile() == {"limits": {"temp_c": [20, 27]}, "hold_s": 9, "label": "Bed 3"}
    assert client.get("/api/room").json["profile"]["label"] == "Bed 3"
    assert 'value="Bed 3"' in client.get("/").get_data(as_text=True)
    assert client.post("/profile", data={**form, "label": "<b>Bed</b>"}).status_code == 303
    page = client.get("/").get_data(as_text=True)
    assert "<b>Bed</b>" not in page and "&lt;b&gt;Bed&lt;/b&gt;" in page
    assert client.post("/profile", data={**form, "label": ""}).status_code == 303
    assert store.load_profile() == {"limits": {"temp_c": [20, 27]}, "hold_s": 9}
    assert client.get("/api/room").json["profile"]["label"] == ""


@pytest.mark.parametrize("label, message", [("x" * 41, "at most 40 characters"),
                                            ("Bed\x073", "control characters")])
def test_invalid_label_is_refused_and_kept_in_the_form(app_store, label, message):
    client, store = app_store
    response = client.post("/profile", data={"hold_s": "9", "label": label})
    assert response.status_code == 400
    page = response.get_data(as_text=True)
    assert message in page
    if len(label) == 41:
        assert f'value="{label}"' in page  # the typed text is kept
    assert store.load_profile() is None


def test_system_limit_trends_follow_the_published_limits(app_store):
    client, store = app_store
    store.write("status", {"updated_at": time.time(), "air_quality": {"limit": 150},
                           "dust_ugm3": {"limit": None}})
    trends = client.get("/api/room").json["trends"]
    assert trends["air_quality"]["limit_checked"] is True
    assert trends["dust_ugm3"]["limit_checked"] is False


def test_api_returns_the_new_measurement_blocks(app_store):
    client, store = app_store
    publish_live(store, [24, 24])
    status = client.get("/api/room").json["status"]
    assert status["air_quality"]["state"] == "unavailable"  # this line has no Bosch fields
    assert status["air_quality"]["source"] == "Bosch estimate"
    assert status["dust_ugm3"]["state"] == "establishing_baseline"
    assert status["dust_ugm3"]["source"] == "estimate"
    assert status["gas_calibration"] and "gas_ohms" in status["last_reading"]
    assert status["dust"]["sensor_mv"] == 920


def test_page_has_no_form_for_system_limits(app_store):
    client, _ = app_store
    page = client.get("/").get_data(as_text=True)
    assert 'name="label"' in page and 'maxlength="40"' in page
    assert 'name="air_quality' not in page and 'name="dust' not in page
    assert 'id="system-limits"' in page and 'id="profile-label"' in page
