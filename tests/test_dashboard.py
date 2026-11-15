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
