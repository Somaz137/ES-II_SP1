"""Pure occupancy rule: camera check results in, automatic state out.

No I/O and no clock reads. Callers pass the times (monotonic seconds).
"""
from collections import deque
from math import ceil


class OccupancyRule:
    def __init__(self, interval_s, confirm_s, fraction, hold_s):
        self.interval_s = interval_s
        self.confirm_s = confirm_s
        self.fraction = fraction
        self.hold_s = hold_s
        self.expected = max(1, round(confirm_s / interval_s))
        self.needed = ceil(round(fraction * self.expected, 9))
        self._checks = deque()  # (at, seen) of the checks in the window
        self._last_ok_at = None  # last check that was not "failed"
        self._last_seen_at = None
        self._entered = False

    def _window(self, now):
        return [c for c in self._checks if c[0] > now - self.confirm_s]

    def _window_full(self, window, now):
        return bool(window) and now - window[0][0] >= self.confirm_s - self.interval_s

    def add(self, result, at):
        if self._entered and at - self._last_seen_at >= self.hold_s:
            self._entered = False
        seen = result == "seen"
        self._checks.append((at, seen))
        while self._checks and self._checks[0][0] <= at - self.confirm_s:
            self._checks.popleft()
        if result != "failed":
            self._last_ok_at = at
        if seen:
            self._last_seen_at = at
        window = self._window(at)
        if (self._window_full(window, at)
                and sum(1 for c in window if c[1]) >= self.needed):
            self._entered = True

    def assume_occupied(self, at):
        if self._last_seen_at is None or at > self._last_seen_at:
            self._last_seen_at = at
        self._entered = True

    def state(self, now):
        window = self._window(now)
        seen = sum(1 for c in window if c[1])
        working = (self._last_ok_at is not None
                   and now - self._last_ok_at <= 3 * self.interval_s)
        in_hold = (self._entered
                   and now - self._last_seen_at < self.hold_s)
        if in_hold:
            state = "occupied"
        elif working:
            state = "not_seen"
        else:
            state = "unknown"
        confirmed = self._window_full(window, now) and seen >= self.needed
        return {
            "state": state,
            "camera_working": working,
            "last_seen_at": self._last_seen_at,
            "seen": seen,
            "checks": len(window),
            "needed": self.needed,
            "held": in_hold and not confirmed,
        }
