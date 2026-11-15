"""Decide the local alarm level and track whether the board confirmed it.

Pure logic: no serial access, no clock and no storage. Times are monotonic
host times supplied by the caller. Level 0 is off, 1 is LED only, 2 is LED
and buzzer. The buzzer sounds only for unsilenced patient-limit alerts.
"""
from uuid import uuid4

LEVELS = (0, 1, 2)
LEVEL_WORDS = {0: "LED off, buzzer off", 1: "LED on, buzzer off", 2: "LED on, buzzer on"}
UNREACHABLE_MESSAGES = {
    "not_connected": "the serial port is not connected. The host cannot command the LED or buzzer.",
    "send_failed": "the alarm command could not be written to the serial port.",
    "no_confirmation": "the board did not confirm the alarm command within {timeout} s.",
}


def wanted_level(*, unsilenced, silenced, fault):
    """2 for an unsilenced limit alert; 1 for a silenced one or any fault alert."""
    if unsilenced:
        return 2
    return 1 if silenced or fault else 0


def command_line(level):
    if level not in LEVELS:
        raise ValueError("Alarm level must be 0, 1 or 2.")
    return f"ALARM,{level}\n"


class AlarmTracker:
    """Call update() at each publish, then sent() for any level it returns."""

    def __init__(self, confirm_timeout_s, *, id_prefix=None):
        self.timeout_s = confirm_timeout_s
        self.prefix = id_prefix or uuid4().hex[:12]
        self.counter = 0
        self.ids = {}  # active limit alert key -> id
        self.silenced = set()  # ids
        self.silenced_at = None
        self.wanted = 0
        self.requested = None
        self.failed_level = None
        self.confirmed = None
        self.confirmed_at = None
        self.last_reply = None
        self.awaiting_since = None
        self.resend_due = False
        self.state, self.reason = "pending", None
        self.send_error = None
        self.events = []

    def fault_check(self):
        """Resend at each fault check so a board reset is corrected."""
        self.resend_due = True

    def _set_state(self, state, reason=None):
        if state != self.state:
            if state == "confirmed":
                self.events.append(("alarm_confirmed", (
                    f"Local alarm confirmed at level {self.confirmed}: {LEVEL_WORDS[self.confirmed]}.")))
            elif state == "unreachable":
                text = UNREACHABLE_MESSAGES[reason].format(timeout=f"{self.timeout_s:g}")
                self.events.append(("alarm_unreachable", f"Local alarm unreachable: {text}"))
        self.state, self.reason = state, reason

    def _unsilenced_keys(self):
        return [key for key in sorted(self.ids) if self.ids[key] not in self.silenced]

    def _token(self):
        keys = self._unsilenced_keys()
        return ",".join(self.ids[key] for key in keys) or None

    def update(self, *, alert_keys, fault_active, connected, reply, now):
        """Return the level to send now, or None.

        alert_keys identify active limit alerts: (metric, direction, alert start).
        reply is the latest (level, received_at) the board reported, or None.
        """
        active = set(alert_keys)
        for key in sorted(active - self.ids.keys()):
            self.counter += 1
            self.ids[key] = f"{self.prefix}-{self.counter}"
        self.ids = {key: value for key, value in self.ids.items() if key in active}
        self.silenced &= set(self.ids.values())
        if not self.silenced:
            self.silenced_at = None

        if reply is not None and reply != self.last_reply:
            self.last_reply = reply
            self.confirmed, self.confirmed_at = reply
            if self.confirmed == self.requested:
                self.awaiting_since = None
                self._set_state("confirmed")
            else:
                self.awaiting_since = None
                self.resend_due = True
                self._set_state("pending")

        unsilenced = bool(self._unsilenced_keys())
        self.wanted = wanted_level(unsilenced=unsilenced, silenced=bool(self.silenced),
                                   fault=fault_active)
        if not connected:
            self.awaiting_since = None
            self.resend_due = True
            self._set_state("unreachable", "not_connected")
            return None
        if self.awaiting_since is not None and now - self.awaiting_since > self.timeout_s:
            self._set_state("unreachable", "no_confirmation")
        changed = self.wanted != self.requested and self.wanted != self.failed_level
        return self.wanted if changed or self.resend_due else None

    def sent(self, level, ok, now, error=None):
        """Record the result of writing command_line(level)."""
        self.resend_due = False
        if not ok:
            self.failed_level = level
            self.send_error = error
            self._set_state("unreachable", "send_failed")
            return
        self.failed_level = None
        self.send_error = None
        self.requested = level
        if self.awaiting_since is None:
            self.awaiting_since = now
        if self.state == "unreachable" and self.reason == "no_confirmation":
            return
        if not (self.state == "confirmed" and self.confirmed == level):
            self._set_state("pending")

    def silence(self, token, wall):
        """Silence the alerts named by the published token; return their keys."""
        if token is None or token != self._token():
            return []
        keys = self._unsilenced_keys()
        self.silenced |= {self.ids[key] for key in keys}
        self.silenced_at = wall
        return keys

    def take_events(self):
        events, self.events = self.events, []
        return events

    def block(self, now):
        silenced = bool(self.silenced)
        return {
            "wanted_level": self.wanted,
            "requested_level": self.requested,
            "confirmed_level": self.confirmed,
            "state": self.state,
            "reason": self.reason,
            "silenced": silenced,
            "silenced_at": self.silenced_at if silenced else None,
            "silence_token": self._token(),
            "confirmation_age_s": None if self.confirmed_at is None else now - self.confirmed_at,
            "send_error": self.send_error,
        }
