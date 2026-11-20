"""BSEC calibration state kept on the laptop: parse, store, reply and show."""

from datetime import datetime
import json
import os
from pathlib import Path
import time

import pytest

from bsec_state_store import BsecStateKeeper, load_state, reply_for, save_state, state_path
from monitoring_loop import run_monitor
from monitoring_state import create_monitoring_state, monitoring_status, process_serial_line
from serial_parser import parse_serial_line
from simulated_input import SimulatedTransport

VERSION = "2.6.1.0"
FULL = "a5" * 238  # the board always sends the full 238-byte state
READING = ('{"type":"reading","temp_c":24,"humidity_pct":48,'
           '"pressure_hpa":1008,"gas_ohms":12000}')


def state_line(state=FULL, accuracy=3, version=VERSION):
    return json.dumps({"type": "bsec_state", "accuracy": accuracy,
                       "bsec_version": version, "state": state})


def request_line(version=VERSION):
    return json.dumps({"type": "bsec_state_request", "bsec_version": version})


# ---------- parser ----------

def test_parser_classifies_the_three_board_lines():
    parsed = parse_serial_line(state_line())
    assert parsed.kind == "bsec_state"
    assert parsed.bsec_state_hex == FULL and parsed.bsec_accuracy == 3
    assert parsed.bsec_version == VERSION
    parsed = parse_serial_line(request_line())
    assert parsed.kind == "bsec_state_request" and parsed.bsec_version == VERSION
    for ok in (True, False):
        parsed = parse_serial_line(json.dumps({"type": "bsec_state_restored", "ok": ok}))
        assert parsed.kind == "bsec_state_restored" and parsed.restore_ok is ok


def test_parser_accepts_uppercase_state_and_stores_it_lowercase():
    assert parse_serial_line(state_line("AB" * 4)).bsec_state_hex == "ab" * 4


def test_board_state_save_failure_is_its_own_kind_not_a_sensor_error():
    line = '{"type":"error","message":"bsec_state_save_failed","bsec_code":0,"sensor_code":0}'
    assert parse_serial_line(line).kind == "bsec_state_save_failed"


@pytest.mark.parametrize("payload", [
    {"type": "bsec_state", "accuracy": 3, "bsec_version": VERSION, "state": "zz" * 4},
    {"type": "bsec_state", "accuracy": 3, "bsec_version": VERSION, "state": "a5" * 239},
    {"type": "bsec_state", "accuracy": 3, "bsec_version": VERSION, "state": "abc"},
    {"type": "bsec_state", "accuracy": 3, "bsec_version": VERSION, "state": ""},
    {"type": "bsec_state", "accuracy": 3, "bsec_version": VERSION, "state": 7},
    {"type": "bsec_state", "accuracy": 4, "bsec_version": VERSION, "state": FULL},
    {"type": "bsec_state", "accuracy": True, "bsec_version": VERSION, "state": FULL},
    {"type": "bsec_state", "accuracy": 3, "bsec_version": "2.6", "state": FULL},
    {"type": "bsec_state", "accuracy": 3, "state": FULL},
    {"type": "bsec_state_request"},
    {"type": "bsec_state_request", "bsec_version": 2610},
    {"type": "bsec_state_restored", "ok": 1},
    {"type": "bsec_state_restored"},
])
def test_malformed_bsec_lines_are_ignored(payload):
    assert parse_serial_line(json.dumps(payload)).kind == "ignored"


# ---------- monitoring state ----------

def start():
    return create_monitoring_state(0, 120, 120)


def test_bsec_lines_do_not_reset_the_communication_timer():
    state = process_serial_line(start(), READING, 0)
    state = process_serial_line(state, request_line(), 130)
    assert state.communication.timed_out and monitoring_status(state) == "communication_lost"
    for line in (state_line(), '{"type":"bsec_state_restored","ok":true}',
                 '{"type":"error","message":"bsec_state_save_failed"}'):
        state = process_serial_line(state, line, 131)
        assert state.communication.timed_out and state.communication.last_message_at == 0


def test_bsec_lines_are_carried_with_counts_and_leave_readings_alone():
    state = process_serial_line(start(), READING, 1)
    before = state
    state = process_serial_line(state, request_line(), 2)
    state = process_serial_line(state, request_line("2.6.1.1"), 3)
    assert state.bsec_request == (2, "2.6.1.1", 3)
    state = process_serial_line(state, state_line(), 4)
    assert state.bsec_state.count == 1 and state.bsec_state.state_hex == FULL
    state = process_serial_line(state, '{"type":"bsec_state_restored","ok":false}', 5)
    assert state.bsec_restored == (1, False, 5)
    state = process_serial_line(state, '{"type":"error","message":"bsec_state_save_failed"}', 6)
    assert state.bsec_save_failed == (1, 6)
    assert state.reading == before.reading and state.gas == before.gas
    assert state.sensor.error_started_at is None and not state.sensor.alert_active
    assert state.sensor.last_valid_measurement_at == 1


# ---------- the file ----------

def test_state_path_sits_next_to_the_database():
    assert state_path(Path("/x/room.sqlite3")) == Path("/x/room.bsec_state.json")
    assert state_path(Path("/x/room-demo.sqlite3")) == Path("/x/room-demo.bsec_state.json")


def test_save_then_load_round_trips(tmp_path):
    path = tmp_path / "room.bsec_state.json"
    save_state(path, state_hex=FULL.upper(), bsec_version=VERSION, accuracy=3, saved_at=1000.5)
    assert load_state(path) == {"saved_at": 1000.5, "bsec_version": VERSION, "accuracy": 3,
                                "state": FULL}
    assert list(tmp_path.iterdir()) == [path]


def test_a_crash_before_the_rename_leaves_the_old_file_whole(tmp_path, monkeypatch):
    path = tmp_path / "room.bsec_state.json"
    save_state(path, state_hex="0011", bsec_version=VERSION, accuracy=3, saved_at=1)
    old = path.read_bytes()

    def crash(*args):
        raise OSError("power cut")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(OSError):
        save_state(path, state_hex=FULL, bsec_version=VERSION, accuracy=3, saved_at=2)
    assert path.read_bytes() == old
    assert list(tmp_path.iterdir()) == [path]


def test_load_state_of_a_missing_file_is_none(tmp_path):
    assert load_state(tmp_path / "none.json") is None


# ---------- the reply ----------

def iso(saved_at):
    return datetime.fromtimestamp(saved_at).astimezone().isoformat(timespec="seconds")


def test_reply_without_a_file_is_none(tmp_path):
    assert reply_for(tmp_path / "x.json", VERSION) == ("BSEC_STATE,NONE", "no saved state")


def test_reply_on_a_version_mismatch_is_none_naming_both_versions(tmp_path):
    path = tmp_path / "x.json"
    save_state(path, state_hex=FULL, bsec_version="2.5.0.2", accuracy=3, saved_at=1)
    assert reply_for(path, VERSION) == (
        "BSEC_STATE,NONE", "version mismatch (file 2.5.0.2, board 2.6.1.0)")


@pytest.mark.parametrize("content", [
    "{not json",
    "",
    "[]",
    json.dumps({"saved_at": 1, "bsec_version": VERSION, "accuracy": 3, "state": "abc"}),
    json.dumps({"saved_at": 1, "bsec_version": VERSION, "accuracy": 3, "state": "a5" * 239}),
    json.dumps({"saved_at": 1, "bsec_version": VERSION, "accuracy": 3, "state": "zz" * 4}),
    json.dumps({"saved_at": 1, "bsec_version": VERSION, "accuracy": 3}),
    json.dumps({"saved_at": "x", "bsec_version": VERSION, "accuracy": 3, "state": FULL}),
    json.dumps({"saved_at": 1e20, "bsec_version": VERSION, "accuracy": 3, "state": FULL}),
    json.dumps({"saved_at": -1e20, "bsec_version": VERSION, "accuracy": 3, "state": FULL}),
    json.dumps({"saved_at": 1e300, "bsec_version": VERSION, "accuracy": 3, "state": FULL}),
    json.dumps({"saved_at": 1, "bsec_version": 7, "accuracy": 3, "state": FULL}),
])
def test_reply_for_a_damaged_file_is_none(tmp_path, content):
    path = tmp_path / "x.json"
    path.write_text(content, encoding="utf-8")
    assert reply_for(path, VERSION) == ("BSEC_STATE,NONE", "file damaged")


def test_reply_for_undecodable_bytes_is_none(tmp_path):
    path = tmp_path / "x.json"
    path.write_bytes(b"\xff\xfe\x00")
    assert reply_for(path, VERSION) == ("BSEC_STATE,NONE", "file damaged")


def test_reply_for_a_good_file_sends_the_state(tmp_path):
    path = tmp_path / "x.json"
    save_state(path, state_hex=FULL, bsec_version=VERSION, accuracy=3, saved_at=1700000000)
    assert reply_for(path, VERSION) == (f"BSEC_STATE,{FULL}", f"restored from {iso(1700000000)}")


# ---------- monitor level ----------

class FakeTransport:
    connected = True
    last_error = None

    def __init__(self, batches=(), ok=True):
        self.batches = list(batches)
        self.sent = []
        self.ok = ok
        self.last_send_error = None if ok else "write failed"

    def send(self, line):
        self.sent.append(line)
        return self.ok

    def poll(self, now):
        return self.batches.pop(0) if self.batches else []

    def close(self):
        pass


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


def run(tmp_path, transport, until=2.0, saved=None):
    """run_monitor with the monitor's BSEC wiring: handle each published state."""
    path = tmp_path / "room.bsec_state.json"
    if saved:
        save_state(path, **saved)
    keeper = BsecStateKeeper(path)
    events, blocks = [], []
    clock = Clock()

    def publish(state, now, connection):
        events.extend(keeper.handle(state, now, 1000 + now, connection))
        blocks.append(keeper.block())

    run_monitor(transport, {"communication_timeout_s": 120, "sensor_error_timeout_s": 120},
                {"fault_check_interval_s": 5, "serial_poll_interval_s": 0.25}, publish,
                clock=clock, sleep=clock.sleep, should_stop=lambda: clock.now >= until)
    return path, events, blocks


def kinds(events):
    return [kind for kind, _ in events]


def test_a_request_in_the_first_poll_gets_exactly_one_reply(tmp_path):
    transport = FakeTransport([[request_line()]])
    _, events, blocks = run(tmp_path, transport)
    assert transport.sent == ["BSEC_STATE,NONE\n"]
    assert kinds(events) == ["bsec_state_not_sent"] and "no saved state" in events[0][1]
    assert blocks[-1]["last_reply_reason"] == "no saved state"
    assert blocks[-1]["last_request_at"] == pytest.approx(1000)
    assert blocks[-1]["saved_at"] is None and blocks[-1]["accuracy"] is None


def test_two_requests_in_one_poll_get_two_replies(tmp_path):
    transport = FakeTransport([[request_line(), request_line()]])
    run(tmp_path, transport)
    assert transport.sent == ["BSEC_STATE,NONE\n", "BSEC_STATE,NONE\n"]


def test_two_requests_in_a_row_get_two_replies_with_the_state(tmp_path):
    transport = FakeTransport([[request_line()], [request_line()]])
    _, events, _ = run(tmp_path, transport, saved=dict(
        state_hex=FULL, bsec_version=VERSION, accuracy=3, saved_at=1700000000))
    assert transport.sent == [f"BSEC_STATE,{FULL}\n"] * 2
    assert kinds(events) == ["bsec_state_sent"] * 2
    assert f"restored from {iso(1700000000)}" in events[0][1]


def test_a_damaged_file_sends_none_and_logs_file_damaged(tmp_path):
    (tmp_path / "room.bsec_state.json").write_text('{"state": "abc"', encoding="utf-8")
    transport = FakeTransport([[request_line()]])
    _, events, blocks = run(tmp_path, transport)
    assert transport.sent == ["BSEC_STATE,NONE\n"]
    assert kinds(events) == ["bsec_state_not_sent"] and "file damaged" in events[0][1]
    assert blocks[-1]["last_reply_reason"] == "file damaged" and blocks[-1]["saved_at"] is None


def test_a_version_mismatch_sends_none_and_logs_the_reason(tmp_path):
    transport = FakeTransport([[request_line("2.6.1.1")]])
    _, events, _ = run(tmp_path, transport, saved=dict(
        state_hex=FULL, bsec_version=VERSION, accuracy=3, saved_at=5))
    assert transport.sent == ["BSEC_STATE,NONE\n"]
    assert "version mismatch (file 2.6.1.0, board 2.6.1.1)" in events[0][1]


def test_a_failed_write_is_logged_as_not_sent(tmp_path):
    transport = FakeTransport([[request_line()]], ok=False)
    _, events, _ = run(tmp_path, transport, saved=dict(
        state_hex=FULL, bsec_version=VERSION, accuracy=3, saved_at=5))
    assert len(transport.sent) == 1
    assert kinds(events) == ["bsec_state_not_sent"] and "write failed" in events[0][1]


def test_a_state_line_writes_the_file_and_logs_saved(tmp_path):
    transport = FakeTransport([[state_line()]])
    path, events, blocks = run(tmp_path, transport)
    assert load_state(path) == {"saved_at": pytest.approx(1000), "bsec_version": VERSION,
                                "accuracy": 3, "state": FULL}
    assert kinds(events) == ["bsec_state_saved"]
    assert blocks[-1]["saved_at"] == pytest.approx(1000) and blocks[-1]["accuracy"] == 3
    assert transport.sent == []


def test_restore_results_and_board_save_failures_are_logged(tmp_path):
    transport = FakeTransport([['{"type":"bsec_state_restored","ok":true}'],
                               ['{"type":"bsec_state_restored","ok":false}'],
                               ['{"type":"error","message":"bsec_state_save_failed"}']])
    _, events, blocks = run(tmp_path, transport)
    assert kinds(events) == ["bsec_state_restored", "bsec_state_restore_failed",
                             "bsec_state_save_failed"]
    assert blocks[-1]["last_restore_ok"] is False


def test_the_block_shows_a_saved_file_from_before_the_start(tmp_path):
    _, _, blocks = run(tmp_path, FakeTransport(), saved=dict(
        state_hex=FULL, bsec_version=VERSION, accuracy=3, saved_at=77))
    assert blocks[0] == {"saved_at": 77, "accuracy": 3, "last_request_at": None,
                         "last_reply_reason": None, "last_restore_ok": None}


def test_a_host_write_failure_is_logged_and_does_not_stop_the_monitor(tmp_path, monkeypatch):
    def crash(*args):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", crash)
    _, events, blocks = run(tmp_path, FakeTransport([[state_line()]]))
    assert kinds(events) == ["bsec_state_save_failed"] and "disk full" in events[0][1]
    assert blocks[-1]["saved_at"] is None


# ---------- demo ----------

def test_demo_board_requests_at_start_and_restores_the_reply():
    transport = SimulatedTransport()
    first = transport.poll(0)
    assert json.loads(first[0]) == {"type": "bsec_state_request", "bsec_version": VERSION}
    assert transport.send("BSEC_STATE,NONE\n") is True
    assert all("bsec_state_restored" not in line for line in transport.poll(0.05))
    assert transport.send(f"BSEC_STATE,{FULL}\n") is True
    assert json.loads(transport.poll(0.1)[0]) == {"type": "bsec_state_restored", "ok": True}


def test_demo_board_sends_one_state_line_after_60_s():
    transport = SimulatedTransport()
    lines = [line for now in range(0, 130) for line in transport.poll(float(now))]
    states = [json.loads(line) for line in lines if '"bsec_state"' in line]
    assert len(states) == 1
    assert parse_serial_line(json.dumps(states[0])).kind == "bsec_state"


# ---------- dashboard ----------

@pytest.fixture
def app_store(tmp_path):
    pytest.importorskip("flask")
    from dashboard import create_app
    from room_store import RoomStore

    path = tmp_path / "room.sqlite3"
    return create_app(path).test_client(), RoomStore(path)


BLOCK = {"saved_at": None, "accuracy": None, "last_request_at": None,
         "last_reply_reason": None, "last_restore_ok": None}


def test_api_health_carries_the_bsec_state(app_store):
    client, store = app_store
    assert client.get("/api/room").json["health"]["bsec_state"]["state"] == "unknown"
    store.write("status", {"updated_at": time.time(), "bsec_state": BLOCK})
    entry = client.get("/api/room").json["health"]["bsec_state"]
    assert entry["state"] == "not_saved" and entry["text"] == "Bosch calibration not saved yet"
    saved_at = time.time() - 60
    store.write("status", {"updated_at": time.time(), "bsec_state": {
        **BLOCK, "saved_at": saved_at, "accuracy": 3, "last_request_at": saved_at,
        "last_reply_reason": "no saved state", "last_restore_ok": True}})
    entry = client.get("/api/room").json["health"]["bsec_state"]
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(saved_at))
    assert entry["state"] == "saved"
    assert entry["text"] == f"Bosch calibration saved: {stamp}, accuracy 3"
    assert entry["saved_age_s"] == pytest.approx(60, abs=5)
    assert entry["last_reply_reason"] == "no saved state" and entry["last_restore_ok"] is True


def test_system_page_has_the_bosch_calibration_row(app_store):
    client, _ = app_store
    page = client.get("/system").get_data(as_text=True)
    assert 'id="path-bsec_state"' in page and "Bosch calibration" in page
    script = (Path(__file__).resolve().parents[1] / "static/room.js").read_text(encoding="utf-8")
    assert 'pathRow("bsec_state"' in script


# ---------- a saved_at time that no clock can show ----------

@pytest.mark.parametrize("saved_at", [1e20, -1e20, 1e300])
def test_an_impossible_saved_at_is_damaged_at_start_and_on_request(tmp_path, saved_at):
    (tmp_path / "room.bsec_state.json").write_text(json.dumps(
        {"saved_at": saved_at, "bsec_version": VERSION, "accuracy": 3, "state": FULL}),
        encoding="utf-8")
    transport = FakeTransport([[request_line()]])
    _, events, blocks = run(tmp_path, transport)
    assert blocks[0]["saved_at"] is None and blocks[0]["accuracy"] is None
    assert transport.sent == ["BSEC_STATE,NONE\n"]
    assert kinds(events) == ["bsec_state_not_sent"] and "file damaged" in events[0][1]


@pytest.mark.parametrize("saved_at", [1e20, -1e20, 1e300])
def test_dashboard_api_survives_an_impossible_saved_at(app_store, tmp_path, saved_at):
    client, store = app_store
    path = tmp_path / "other.bsec_state.json"
    path.write_text(json.dumps({"saved_at": saved_at, "bsec_version": VERSION, "accuracy": 3,
                                "state": FULL}), encoding="utf-8")
    store.write("status", {"updated_at": time.time(), "bsec_state": BsecStateKeeper(path).block()})
    response = client.get("/api/room")
    assert response.status_code == 200
    assert response.json["health"]["bsec_state"]["text"] == "Bosch calibration not saved yet"
    # A status block written by anything else with such a time does not break the API either.
    store.write("status", {"updated_at": time.time(), "bsec_state": {**BLOCK, "saved_at": saved_at}})
    response = client.get("/api/room")
    assert response.status_code == 200
    assert response.json["health"]["bsec_state"]["state"] == "not_saved"
