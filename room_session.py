"""Persist operator status and evaluate patient limits with a monotonic clock."""
from alarm import command_line
from room_store import METRICS
from settings import RUNTIME_DEFAULTS

STORED_READING_FIELDS = ("temp_c", "humidity_pct", "pressure_hpa", "gas_ohms")
PRUNE_INTERVAL_S = 3600


def format_duration(seconds):
    hours, rest = divmod(int(round(seconds)), 3600)
    minutes, secs = divmod(rest, 60)
    parts = [f"{hours} h"] if hours else []
    if minutes:
        parts.append(f"{minutes} min")
    if secs or not parts:
        parts.append(f"{secs} s")
    return " ".join(parts)


def quantity(metric, value):
    return f"{value:.6g} {METRICS[metric][1]}"


def condition(metric, direction, limit):
    word = "below" if direction == "low" else "above"
    return f"{METRICS[metric][0]} {word} the configured limit of {quantity(metric, limit)}"


class RoomSession:
    prune_batch = 5000

    def __init__(self, store, *, demo=False, timing=None, alarm=None):
        self.store = store
        self.alarm = alarm  # an alarm.AlarmTracker, or None for no local alarm
        self.demo = demo
        self.timing = dict(RUNTIME_DEFAULTS if timing is None else timing)
        self.gap_s = self.timing["reading_gap_limit_s"]
        self.profile = None
        # metric -> {"direction", "start", "alert_at", "value"}; times are monotonic receipt times.
        self.breaches = {}
        self.last_bme = None
        self.last_dust = None
        self.previous_faults = set()
        self.pending_events = []
        self.next_prune = None

    def note_acknowledgment(self):
        """Record that a person acknowledged the communication alert; logged on the next update."""
        self.pending_events.append(
            ("communication_acknowledged", "Communication alert acknowledged on the dashboard."))

    def alarm_fault_check(self):
        if self.alarm is not None:
            self.alarm.fault_check()

    def silence_alarm(self, token, wall):
        """Apply a dashboard silence request; True and an event only when applied."""
        if self.alarm is None:
            return False
        keys = self.alarm.silence(token, wall)
        if not keys:
            return False
        conditions = "; ".join(condition(metric, direction, self.limit(metric, direction))
                               for metric, direction, _ in keys)
        self.pending_events.append(("alarm_silenced", (
            f"Local alarm silenced on the dashboard. Buzzer off for: {conditions}. "
            "The LED stays on while the alert is active.")))
        return True

    def update_alarm(self, status, now, reply, transport):
        """Decide the level after the limit state is built; send it when due."""
        keys = [(metric, breach["direction"], breach["alert_at"])
                for metric, breach in sorted(self.breaches.items()) if breach["alert_at"] is not None]
        fault = bool(status["communication_alert_active"] or status["sensor_alert_active"]
                     or status["dust"]["alert_active"])
        connected = transport is not None and bool(transport.connected)
        level = self.alarm.update(alert_keys=keys, fault_active=fault, connected=connected,
                                  reply=reply, now=now)
        if level is not None:
            try:
                ok = transport.send(command_line(level)) is True
                error = None if ok else getattr(transport, "last_send_error", None)
            except Exception as failure:  # noqa: BLE001 - the alarm must not stop publication
                ok, error = False, str(failure) or type(failure).__name__
            self.alarm.sent(level, ok, now, error)
        status["alarm"] = self.alarm.block(now)
        return self.alarm.take_events()

    def limit(self, metric, direction):
        low, high = self.profile["limits"][metric]
        return low if direction == "low" else high

    def end_all(self, kind, because, after, now):
        events = []
        for metric, breach in sorted(self.breaches.items()):
            if breach["alert_at"] is not None:
                events.append((kind, (
                    f"{condition(metric, breach['direction'], self.limit(metric, breach['direction']))}: "
                    f"alert stopped after {format_duration(now - breach['alert_at'])} {because}. "
                    f"Last value {quantity(metric, breach['value'])}. {after}")))
        self.breaches.clear()
        return events

    def check_reading(self, reading, bme_at):
        events = []
        if self.last_bme is not None and bme_at - self.last_bme > self.gap_s:
            events += self.end_all("limit_reset_reading",
                                   f"because readings were more than {format_duration(self.gap_s)} apart",
                                   "The sustained timer restarts.", bme_at)
        for metric, (low, high) in self.profile["limits"].items():
            value = reading[metric]
            direction = "low" if value < low else "high" if value > high else None
            current = self.breaches.get(metric)
            ended = current is not None and current["alert_at"] is not None and current["direction"] != direction
            if ended:
                old = condition(metric, current["direction"], self.limit(metric, current["direction"]))
                lasted = format_duration(bme_at - current["alert_at"])
                if direction is None:
                    events.append(("limit_ended", f"{old}: alert ended after {lasted}. "
                                   f"Value {quantity(metric, value)} is within the configured limits."))
                else:
                    new = condition(metric, direction, self.limit(metric, direction)).split(" ", 1)[1]
                    events.append(("limit_reversed", f"{old}: alert ended after {lasted}. "
                                   f"Value {quantity(metric, value)} is {new}."))
            if direction is None:
                self.breaches.pop(metric, None)
                continue
            if current is None or current["direction"] != direction:
                current = {"direction": direction, "start": bme_at, "alert_at": None}
            current["value"] = value
            if current["alert_at"] is None and bme_at - current["start"] >= self.profile["hold_s"]:
                current["alert_at"] = bme_at
                events.append(("limit_alert", (
                    f"{condition(metric, direction, self.limit(metric, direction))} for "
                    f"{format_duration(bme_at - current['start'])}. Value {quantity(metric, value)}.")))
            self.breaches[metric] = current
        return events

    def limit_state(self, now, wall):
        alerts, pending = [], []
        for metric, breach in sorted(self.breaches.items()):
            entry = {"metric": metric, "name": METRICS[metric][0], "unit": METRICS[metric][1],
                     "direction": breach["direction"], "limit": self.limit(metric, breach["direction"]),
                     "value": breach["value"], "breach_started_at": wall - (now - breach["start"]),
                     "elapsed_s": now - breach["start"]}
            if breach["alert_at"] is None:
                hold = self.profile["hold_s"]
                pending.append({**entry, "hold_s": hold, "remaining_s": max(0, hold - entry["elapsed_s"])})
            else:
                alerts.append({**entry, "alert_started_at": wall - (now - breach["alert_at"])})
        return alerts, pending

    def monitoring_state(self, profile, profile_error, good, occupancy):
        if profile is None and profile_error:
            return "off", "profile_invalid", "The patient profile file is invalid and no valid profile is loaded."
        if profile is None:
            return "off", "no_profile", "No patient profile is configured."
        if not profile["limits"]:
            return "off", "no_limits", "No measurement has patient limits enabled."
        if not good:
            return "paused", "reading_not_current", "The BME680 reading is not current. Limit monitoring is paused."
        if occupancy != "occupied":
            return "paused", "occupancy_unknown", "Occupancy is unknown. Limit monitoring is paused."
        if profile_error:
            return ("running", "profile_invalid",
                    "The patient profile file is invalid. Monitoring continues on the last valid profile.")
        return "running", None, "Limit monitoring is running."

    def update(self, status, now, wall, occupancy="unknown", *, alarm_reply=None, transport=None):
        events, self.pending_events = self.pending_events, []
        profile_error = None
        try:
            profile = self.store.load_profile()
        except (OSError, ValueError) as error:
            profile = self.profile
            profile_error = str(error)
        if self.profile != profile:
            events += self.end_all("limit_reset_profile", "because the patient limits changed",
                                   "The sustained timer restarts.", now)
            self.profile = profile
        reading = status["last_reading"]
        bme_at = reading["received_at"] if reading else None
        good = status["input_status"] == "fresh" and bme_at is not None and now - bme_at <= self.gap_s
        samples = []
        if bme_at is not None and bme_at != self.last_bme:
            samples.extend((field, wall - (now - bme_at), reading[field]) for field in STORED_READING_FIELDS)
        dust = status["dust"]
        dust_at = now - dust["age_s"] if dust["age_s"] is not None else None
        if dust_at is not None and (self.last_dust is None or abs(dust_at - self.last_dust) > 1e-6):
            samples.append(("dust_mv", wall - dust["age_s"], dust["sensor_mv"]))
            self.last_dust = dust_at

        if not profile:
            self.breaches.clear()
        elif not good:
            events += self.end_all("limit_reset_reading", "because readings are not current",
                                   "Limit monitoring is paused.", now)
        elif occupancy != "occupied":
            events += self.end_all("limit_reset_occupancy", "because occupancy is unknown",
                                   "Limit monitoring is paused.", now)
        elif bme_at != self.last_bme:
            events += self.check_reading(reading, bme_at)
        self.last_bme = bme_at

        faults = {key for key, active_flag in {
            "Communication": status["communication_alert_active"],
            "BME680": status["sensor_alert_active"],
            "Dust": dust["alert_active"],
            "Patient profile": profile_error is not None,
        }.items() if active_flag}
        events += [("fault", f"{name} alert active.") for name in sorted(faults - self.previous_faults)]
        events += [("fault_ended", f"{name} alert cleared.") for name in sorted(self.previous_faults - faults)]
        self.previous_faults = faults
        alerts, pending = self.limit_state(now, wall)
        state, reason, message = self.monitoring_state(profile, profile_error, good, occupancy)
        status.update(updated_at=wall, occupancy=occupancy, demo=self.demo,
                      measurement_current=good, profile_error=profile_error,
                      limit_alerts=alerts, limit_pending=pending,
                      limit_monitoring={"state": state, "reason": reason, "message": message},
                      timing=self.timing)
        if self.alarm is not None:
            events += self.update_alarm(status, now, alarm_reply, transport)
        self.store.publish(status, samples, events, wall)
        self.prune(now, wall)

    def prune(self, now, wall):
        """Delete old readings at start-up, then hourly, in bounded batches."""
        if self.next_prune is not None and now < self.next_prune:
            return
        cutoff = wall - self.timing["readings_retention_days"] * 86400
        deleted = self.store.prune_readings(cutoff, self.prune_batch)
        self.next_prune = now if deleted >= self.prune_batch else now + PRUNE_INTERVAL_S
