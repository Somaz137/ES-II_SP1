"""Persist operator status and evaluate patient and system limits with a monotonic clock."""
from air_quality import air_quality_state, band_word
from alarm import command_line
from dust import DustBaseline, estimate_dust
from room_store import LIMITED, METRICS, SYSTEM_METRICS
from settings import RUNTIME_DEFAULTS, SYSTEM_DEFAULTS

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


PATIENT = tuple(METRICS)
# Measurements checked on each BME680 reading: the patient limits and the Bosch index.
BME_CHECKED = PATIENT + ("air_quality",)
SECTION = {"air_quality": "air_quality", "dust_ugm3": "dust"}


# Occupancy that pauses limit checks: (reason code, page text, alert-end cause). Anything else is unknown.
OCCUPANCY_PAUSE = {
    "not_seen": ("occupancy_not_seen", "No person seen", "because no person is seen"),
    "not_occupied": ("occupancy_manual", "Set to not occupied by hand",
                     "because the room was set to not occupied by hand"),
}
OCCUPANCY_UNKNOWN = ("occupancy_unknown", "Occupancy is unknown", "because occupancy is unknown")


def occupancy_pause(occupancy):
    return OCCUPANCY_PAUSE.get(occupancy, OCCUPANCY_UNKNOWN)


def quantity(metric, value):
    unit = LIMITED[metric][1]
    return f"{value:.6g} {unit}" if unit else f"{value:.6g}"


def condition(metric, direction, limit):
    word = "below" if direction == "low" else "above"
    return f"{LIMITED[metric][0]} {word} the configured limit of {quantity(metric, limit)}"


def describe_profile(profile):
    label = profile.get("label", "")
    limits = "; ".join(f"{METRICS[metric][0]} {low:.6g} to {quantity(metric, high)}"
                       for metric, (low, high) in profile["limits"].items())
    return (f"Patient profile changed. {f'Label {chr(34)}{label}{chr(34)}.' if label else 'No label.'} "
            f"{limits or 'No measurement limits'}. Sustained duration {format_duration(profile['hold_s'])}.")


def check_state(state, reason, message):
    return {"state": state, "reason": reason, "message": message}


class RoomSession:
    prune_batch = 5000

    def __init__(self, store, *, demo=False, timing=None, alarm=None, system=None):
        self.store = store
        self.alarm = alarm  # an alarm.AlarmTracker, or None for no local alarm
        self.demo = demo
        self.timing = dict(RUNTIME_DEFAULTS if timing is None else timing)
        self.gap_s = self.timing["reading_gap_limit_s"]
        self.profile = None
        self.profile_seen = False
        # Air quality and dust limits, bands and baseline rule: config/system.yaml.
        self.system = SYSTEM_DEFAULTS if system is None else system
        dust = self.system["dust"]
        self.baseline = DustBaseline(dust["baseline_window_s"], dust["baseline_min_s"], self.gap_s)
        # metric -> {"direction", "start", "alert_at", "value"}; times are monotonic receipt times.
        self.breaches = {}
        self.last_bme = None
        self.last_dust = None
        self.previous_faults = set()
        self.pending_events = []
        self.next_prune = None

    def note_event(self, kind, message):
        """Queue an event; it is logged on the next update."""
        self.pending_events.append((kind, message))

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
        if metric in SYSTEM_METRICS:
            return self.system[SECTION[metric]]["upper_limit"]
        low, high = self.profile["limits"][metric]
        return low if direction == "low" else high

    def hold(self, metric):
        if metric in SYSTEM_METRICS:
            return self.system[SECTION[metric]]["hold_s"]
        return self.profile["hold_s"]

    def end_all(self, kind, because, after, now, metrics):
        events = []
        for metric, breach in sorted(self.breaches.items()):
            if metric not in metrics:
                continue
            if breach["alert_at"] is not None:
                events.append((kind, (
                    f"{condition(metric, breach['direction'], self.limit(metric, breach['direction']))}: "
                    f"alert stopped after {format_duration(now - breach['alert_at'])} {because}. "
                    f"Last value {quantity(metric, breach['value'])}. {after}")))
            del self.breaches[metric]
        return events

    def check_reading(self, reading, bme_at):
        events = []
        for metric, (low, high) in self.profile["limits"].items():
            value = reading[metric]
            events += self.track(metric, "low" if value < low else "high" if value > high else None,
                                 value, bme_at)
        return events

    def check_upper(self, metric, value, at):
        """One system-limit sample: above the upper limit or not."""
        return self.track(metric, "high" if value > self.limit(metric, "high") else None, value, at)

    def track(self, metric, direction, value, at):
        """Advance one measurement's sustained-breach record; return its events."""
        events = []
        current = self.breaches.get(metric)
        ended = current is not None and current["alert_at"] is not None and current["direction"] != direction
        if ended:
            old = condition(metric, current["direction"], self.limit(metric, current["direction"]))
            lasted = format_duration(at - current["alert_at"])
            if direction is None:
                events.append(("limit_ended", f"{old}: alert ended after {lasted}. "
                               f"Value {quantity(metric, value)} is within the configured limits."))
            else:
                new = condition(metric, direction, self.limit(metric, direction)).split(" ", 1)[1]
                events.append(("limit_reversed", f"{old}: alert ended after {lasted}. "
                               f"Value {quantity(metric, value)} is {new}."))
        if direction is None:
            self.breaches.pop(metric, None)
            return events
        if current is None or current["direction"] != direction:
            current = {"direction": direction, "start": at, "alert_at": None}
        current["value"] = value
        if current["alert_at"] is None and at - current["start"] >= self.hold(metric):
            current["alert_at"] = at
            events.append(("limit_alert", (
                f"{condition(metric, direction, self.limit(metric, direction))} for "
                f"{format_duration(at - current['start'])}. Value {quantity(metric, value)}.")))
        self.breaches[metric] = current
        return events

    def check_air_quality(self, state, iaq, at):
        """Called for each new current BME680 reading while the room is occupied."""
        if self.limit("air_quality", "high") is None:
            return []
        if state != "current":
            because = ("because the Bosch index is calibrating" if state == "calibrating"
                       else "because no air quality index is reported")
            return self.end_all("limit_reset_estimate", because, "The air quality check is paused.",
                                at, ("air_quality",))
        return self.check_upper("air_quality", iaq, at)

    def air_quality_block(self, state, iaq, accuracy, good, occupancy):
        settings = self.system["air_quality"]
        if settings["upper_limit"] is None:
            check = check_state("off", "no_limit", "No air quality limit is set in the system settings.")
        elif not good:
            check = check_state("paused", "reading_not_current",
                                "The BME680 reading is not current. The air quality check is paused.")
        elif occupancy != "occupied":
            reason, subject, _ = occupancy_pause(occupancy)
            check = check_state("paused", reason, f"{subject}. The air quality check is paused.")
        elif state == "calibrating":
            check = check_state("paused", "calibrating",
                                "The Bosch index is calibrating. The air quality check is paused.")
        elif state != "current":
            check = check_state("paused", "index_unavailable",
                                "No air quality index is reported. The air quality check is paused.")
        else:
            check = check_state("running", None, "The air quality check is running.")
        return {"name": SYSTEM_METRICS["air_quality"][0], "unit": SYSTEM_METRICS["air_quality"][1],
                "estimate": True, "source": "Bosch estimate", "state": state, "value": iaq,
                "band": band_word(iaq, settings["bands"]), "accuracy": accuracy,
                "limit": settings["upper_limit"], "hold_s": settings["hold_s"], "check": check}

    def update_dust(self, dust, now, wall, occupancy):
        """Baseline, estimate and system-limit check for the dust record. Returns events, block, samples."""
        settings = self.system["dust"]
        events, samples = [], []
        dust_at = now - dust["age_s"] if dust["age_s"] is not None else None
        new = dust_at is not None and (self.last_dust is None or abs(dust_at - self.last_dust) > 1e-6)
        gap = new and self.last_dust is not None and dust_at - self.last_dust > self.gap_s
        current = dust["status"] == "fresh" and dust["age_s"] is not None and dust["age_s"] <= self.gap_s
        if new:
            samples.append(("dust_mv", wall - dust["age_s"], dust["sensor_mv"]))
            self.last_dust = dust_at
        if dust["status"] != "fresh":
            self.baseline.reset()  # a dust fault: the clean-air baseline starts again
        elif new:
            self.baseline.add(dust["sensor_mv"], dust_at)
        baseline = self.baseline.value(dust_at) if current else None
        value = None
        if baseline is not None:
            value = estimate_dust(dust["sensor_mv"], baseline, settings["sensitivity_mv_per_mg_m3"])
        state = "unavailable" if not current else "establishing_baseline" if value is None else "current"
        if new and value is not None:
            samples.append(("dust_ugm3", wall - dust["age_s"], value))
        dust["estimated_dust_ug_m3"] = value
        dust["calibration"] = "automatic_baseline" if value is not None else "establishing_baseline"

        group = ("dust_ugm3",)
        limited = settings["upper_limit"] is not None
        if not current:
            events += self.end_all("limit_reset_reading", "because dust readings are not current",
                                   "The dust check is paused.", now, group)
            check = check_state("paused", "reading_not_current",
                                "The dust reading is not current. The dust check is paused.")
        elif gap:
            events += self.end_all("limit_reset_reading",
                                   f"because dust readings were more than {format_duration(self.gap_s)} apart",
                                   "The sustained timer restarts.", dust_at, group)
        if current and occupancy != "occupied":
            reason, subject, because = occupancy_pause(occupancy)
            events += self.end_all("limit_reset_occupancy", because, "The dust check is paused.", now, group)
            check = check_state("paused", reason, f"{subject}. The dust check is paused.")
        elif current and value is None:
            events += self.end_all("limit_reset_estimate", "because the dust baseline is not established",
                                   "The dust check is paused.", now, group)
            check = check_state("paused", "establishing_baseline",
                                "The dust baseline is being established. The dust check is paused.")
        elif current:
            if new and limited:
                events += self.check_upper("dust_ugm3", value, dust_at)
            check = check_state("running", None, "The dust check is running.")
        if not limited:
            check = check_state("off", "no_limit", "No dust limit is set in the system settings.")
        block = {"name": SYSTEM_METRICS["dust_ugm3"][0], "unit": SYSTEM_METRICS["dust_ugm3"][1],
                 "estimate": True, "source": "estimate", "state": state, "value": value,
                 "level": band_word(value, settings["levels"]), "baseline_mv": baseline,
                 "sensitivity_mv_per_mg_m3": settings["sensitivity_mv_per_mg_m3"],
                 "limit": settings["upper_limit"], "hold_s": settings["hold_s"], "check": check}
        return events, block, samples

    def limit_state(self, now, wall):
        alerts, pending = [], []
        for metric, breach in sorted(self.breaches.items()):
            entry = {"metric": metric, "name": LIMITED[metric][0], "unit": LIMITED[metric][1],
                     "direction": breach["direction"], "limit": self.limit(metric, breach["direction"]),
                     "value": breach["value"], "breach_started_at": wall - (now - breach["start"]),
                     "elapsed_s": now - breach["start"]}
            if breach["alert_at"] is None:
                hold = self.hold(metric)
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
            reason, subject, _ = occupancy_pause(occupancy)
            return "paused", reason, f"{subject}. Limit monitoring is paused."
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
            if self.profile_seen and profile is not None:
                events.append(("profile_changed", describe_profile(profile)))
            events += self.end_all("limit_reset_profile", "because the patient limits changed",
                                   "The sustained timer restarts.", now, PATIENT)
            self.profile = profile
        self.profile_seen = True
        reading = status["last_reading"]
        bme_at = reading["received_at"] if reading else None
        good = status["input_status"] == "fresh" and bme_at is not None and now - bme_at <= self.gap_s
        samples = []
        bme_new = bme_at is not None and bme_at != self.last_bme
        if bme_new:
            samples.extend((field, wall - (now - bme_at), reading[field]) for field in STORED_READING_FIELDS)
        aq_state = air_quality_state(status["bsec_iaq"], status["bsec_iaq_accuracy"], good)
        iaq = status["bsec_iaq"] if aq_state == "current" else None
        if bme_new and iaq is not None:
            samples.append(("air_quality", wall - (now - bme_at), iaq))

        if not profile:
            for metric in PATIENT:
                self.breaches.pop(metric, None)
        if not good:
            events += self.end_all("limit_reset_reading", "because readings are not current",
                                   "Limit monitoring is paused.", now, BME_CHECKED)
        elif occupancy != "occupied":
            events += self.end_all("limit_reset_occupancy", occupancy_pause(occupancy)[2],
                                   "Limit monitoring is paused.", now, BME_CHECKED)
        elif bme_new:
            if self.last_bme is not None and bme_at - self.last_bme > self.gap_s:
                events += self.end_all("limit_reset_reading",
                                       f"because readings were more than {format_duration(self.gap_s)} apart",
                                       "The sustained timer restarts.", bme_at, BME_CHECKED)
            if profile:
                events += self.check_reading(reading, bme_at)
            events += self.check_air_quality(aq_state, iaq, bme_at)
        self.last_bme = bme_at

        dust_events, dust_block, dust_samples = self.update_dust(status["dust"], now, wall, occupancy)
        events += dust_events
        samples += dust_samples
        dust = status["dust"]

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
        status["air_quality"] = self.air_quality_block(aq_state, iaq, status["bsec_iaq_accuracy"],
                                                       good, occupancy)
        status["dust_ugm3"] = dust_block
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
