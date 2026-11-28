"""The manual occupancy override: parse the stored request, resolve it, log it, seed the camera hold."""
import math
import time

MODES = ("auto", "occupied", "not_occupied")
SOURCES = ("local", "online")
WORDS = {"auto": "Automatic", "occupied": "occupied", "not_occupied": "not occupied"}


def parse_request(raw):
    """The stored request as {mode, set_at, set_from, id}, or None when it is damaged."""
    if not isinstance(raw, dict) or raw.get("mode") not in MODES:
        return None
    set_at = raw.get("set_at")
    if isinstance(set_at, bool) or not isinstance(set_at, (int, float)) or not math.isfinite(set_at):
        return None
    set_from = raw.get("set_from")
    return {"mode": raw["mode"], "set_at": set_at,
            "set_from": set_from if set_from in SOURCES else "local", "id": raw.get("id")}


def parse_override(raw):
    """A manual request, or None for a damaged one and for mode auto."""
    request = parse_request(raw)
    return None if request is None or request["mode"] == "auto" else request


def resolve(automatic, override, wall, duration_s):
    """Returns (occupancy, source_override, info). A manual mode applies until set_at + duration_s."""
    if override is None or wall >= override["set_at"] + duration_s:
        return automatic, None, None
    info = {"mode": override["mode"], "set_at": override["set_at"], "set_from": override["set_from"],
            "expires_at": override["set_at"] + duration_s}
    return override["mode"], "manual", info


def clock_text(wall):
    return time.strftime("%H:%M", time.localtime(wall))


class OverrideTracker:
    """Reads the stored request, logs changes and expiry, and starts the camera hold once per request."""

    def __init__(self, store, session, camera, duration_s):
        self.store, self.session, self.camera, self.duration_s = store, session, camera, duration_s
        self.request = None
        self.key = None
        self.applying = False

    def poll(self, wall, now, log=True):
        """Read the request. `wall` is the clock time, `now` the monitor's monotonic time."""
        request = parse_request(self.store.read("occupancy_override"))
        key = None if request is None else (request["id"], request["set_at"], request["mode"])
        if key == self.key:
            return
        self.key, self.request = key, request
        self.applying = False
        if request is None:
            return
        mode, set_at = request["mode"], request["set_at"]
        if log:
            if mode == "auto":
                self.session.note_event("occupancy_override_cleared",
                                        f"Occupancy returned to Automatic by hand at {clock_text(set_at)}.")
            else:
                self.session.note_event("occupancy_override_set",
                                        f"Occupancy set to {WORDS[mode]} by hand at {clock_text(set_at)}. "
                                        f"It returns to the camera at {clock_text(set_at + self.duration_s)}.")
        elapsed = max(0, wall - set_at)
        if mode == "occupied" and self.camera is not None and elapsed < self.duration_s:
            self.camera.assume_occupied(now - elapsed)

    def resolve(self, automatic, wall):
        override = None if self.request is None else parse_override(self.request)
        occupancy, source, info = resolve(automatic, override, wall, self.duration_s)
        if info is not None:
            self.applying = True
        elif self.applying:
            self.applying = False
            self.session.note_event(
                "occupancy_override_expired",
                f"The manual setting {WORDS[override['mode']]} (set at {clock_text(override['set_at'])}) "
                f"expired at {clock_text(override['set_at'] + self.duration_s)}. Occupancy returns to the camera.")
        return occupancy, source, info
