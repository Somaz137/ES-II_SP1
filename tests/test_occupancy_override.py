"""The manual occupancy override: parsing, resolution, expiry, events and the camera hold seed."""
import time

import pytest

from occupancy_override import OverrideTracker, parse_override, resolve


class FakeStore:
    def __init__(self, value=None):
        self.value = value

    def read(self, key, default=None):
        assert key == "occupancy_override"
        return self.value if self.value is not None else default


class FakeSession:
    def __init__(self):
        self.events = []

    def note_event(self, kind, message):
        self.events.append((kind, message))


class FakeCamera:
    def __init__(self):
        self.calls = []

    def assume_occupied(self, at):
        self.calls.append(at)


def request(mode, set_at, id="a", set_from="local"):
    return {"mode": mode, "set_at": set_at, "set_from": set_from, "id": id}


def test_manual_occupied_and_not_occupied_apply():
    assert resolve("not_seen", parse_override(request("occupied", 1000)), 1100, 900)[0] == "occupied"
    occupancy, source, info = resolve("occupied", parse_override(request("not_occupied", 1000)), 1100, 900)
    assert (occupancy, source) == ("not_occupied", "manual")
    assert info == {"mode": "not_occupied", "set_at": 1000, "set_from": "local", "expires_at": 1900}


def test_override_expires_at_900_s():
    override = parse_override(request("occupied", 1000))
    assert resolve("unknown", override, 1899, 900)[0] == "occupied"
    assert resolve("unknown", override, 1900, 900) == ("unknown", None, None)
    assert resolve("unknown", None, 1900, 900) == ("unknown", None, None)


@pytest.mark.parametrize("raw", ["x", {}, {"mode": "maybe", "set_at": 1}, {"mode": "occupied"},
                                 {"mode": "occupied", "set_at": True}, None, [],
                                 {"mode": "occupied", "set_at": float("nan")}])
def test_damaged_override_is_ignored(raw):
    assert parse_override(raw) is None


def test_auto_parses_to_none_and_good_request_keeps_fields():
    assert parse_override(request("auto", 5)) is None
    assert parse_override(request("occupied", 5, "q", "online")) == request("occupied", 5, "q", "online")


def test_override_survives_restart_until_expiry():
    session, camera = FakeSession(), FakeCamera()
    fresh = OverrideTracker(FakeStore(request("occupied", 700)), session, camera, 900)
    fresh.poll(1000, 50, log=False)
    assert fresh.resolve("unknown", 1000)[:2] == ("occupied", "manual")
    old = OverrideTracker(FakeStore(request("occupied", 0)), session, camera, 900)
    old.poll(1000, 50, log=False)
    assert old.resolve("unknown", 1000) == ("unknown", None, None)
    assert session.events == []


def test_damaged_stored_override_does_not_crash_tracker():
    tracker = OverrideTracker(FakeStore("garbage"), FakeSession(), None, 900)
    tracker.poll(10, 1)
    assert tracker.resolve("unknown", 10) == ("unknown", None, None)


def test_override_events():
    store, session = FakeStore(), FakeSession()
    tracker = OverrideTracker(store, session, None, 900)
    base = 1_700_000_000
    stamp = time.strftime("%H:%M", time.localtime(base))
    store.value = request("occupied", base, "1")
    tracker.poll(base, 1)
    tracker.resolve("unknown", base)
    store.value = request("auto", base + 60, "2")
    tracker.poll(base + 60, 61)
    tracker.resolve("unknown", base + 60)
    store.value = request("not_occupied", base + 100, "3")
    tracker.poll(base + 100, 101)
    tracker.resolve("unknown", base + 101)
    tracker.resolve("unknown", base + 1000)
    tracker.resolve("unknown", base + 1001)
    assert [kind for kind, _ in session.events] == [
        "occupancy_override_set", "occupancy_override_cleared",
        "occupancy_override_set", "occupancy_override_expired"]
    assert "occupied" in session.events[0][1] and stamp in session.events[0][1]
    assert "not occupied" in session.events[2][1]
    assert "not occupied" in session.events[3][1]


def test_manual_occupied_seeds_camera_hold():
    store, session, camera = FakeStore(request("occupied", 700, "a")), FakeSession(), FakeCamera()
    tracker = OverrideTracker(store, session, camera, 900)
    tracker.poll(1000, 5000, log=False)
    assert camera.calls == [4700]
    tracker.poll(1010, 5010)
    tracker.poll(1020, 5020)
    assert camera.calls == [4700]
    store.value = request("occupied", 1030, "b")
    tracker.poll(1030, 5030)
    assert camera.calls == [4700, 5030]
    store.value = request("not_occupied", 1040, "c")
    tracker.poll(1040, 5040)
    store.value = request("auto", 1050, "d")
    tracker.poll(1050, 5050)
    assert camera.calls == [4700, 5030]


def test_seed_is_clamped_and_skipped_when_expired():
    camera = FakeCamera()
    tracker = OverrideTracker(FakeStore(request("occupied", 1100, "a")), FakeSession(), camera, 900)
    tracker.poll(1000, 5000)  # set_at in the future: clock jump
    assert camera.calls == [5000]
    camera2 = FakeCamera()
    OverrideTracker(FakeStore(request("occupied", 0, "a")), FakeSession(), camera2, 900).poll(2000, 5000)
    assert camera2.calls == []


def test_no_camera_is_harmless():
    tracker = OverrideTracker(FakeStore(request("occupied", 990)), FakeSession(), None, 900)
    tracker.poll(1000, 5)
    assert tracker.resolve("unknown", 1000)[0] == "occupied"
