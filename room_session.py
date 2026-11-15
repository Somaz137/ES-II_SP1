"""Persist operator status and evaluate patient limits with a monotonic clock."""
from room_store import METRICS


class RoomSession:
    def __init__(self, store, *, demo=False):
        self.store = store
        self.demo = demo
        self.profile = None
        self.breaches = {}
        self.last_bme = None
        self.last_dust = None
        self.previous_faults = set()

    def update(self, status, now, wall, occupancy="unknown"):
        profile_error = None
        try:
            profile = self.store.load_profile()
        except (OSError, ValueError) as error:
            profile = self.profile
            profile_error = str(error)
        previous = self.breaches.copy()
        if self.profile != profile:
            self.breaches.clear()
            self.profile = profile
        reading = status["last_reading"]
        bme_at = reading["received_at"] if reading else None
        good = status["input_status"] == "fresh" and bme_at is not None and now - bme_at <= 6
        samples = []
        if bme_at is not None and bme_at != self.last_bme:
            samples.extend((metric, wall - (now - bme_at), reading[metric]) for metric in METRICS)
        dust = status["dust"]
        dust_at = now - dust["age_s"] if dust["age_s"] is not None else None
        if dust_at is not None and (self.last_dust is None or abs(dust_at - self.last_dust) > 1e-6):
            samples.append(("dust_mv", wall - dust["age_s"], dust["sensor_mv"]))
            self.last_dust = dust_at

        if not good or occupancy != "occupied" or not profile:
            self.breaches.clear()
        elif bme_at != self.last_bme:
            for metric, (low, high) in profile["limits"].items():
                value = reading[metric]
                direction = "low" if value < low else "high" if value > high else None
                if direction is None:
                    self.breaches.pop(metric, None)
                    continue
                current = self.breaches.get(metric)
                if current is None or current[0] != direction or bme_at - self.last_bme > 6:
                    current = (direction, bme_at, False)
                self.breaches[metric] = (direction, current[1], bme_at - current[1] >= profile["hold_s"])
        self.last_bme = bme_at

        before = {(metric, value[0]) for metric, value in previous.items() if value[2]}
        active = {(metric, value[0]) for metric, value in self.breaches.items() if value[2]}
        events = [("limit_alert", f"{METRICS[m][0]} remained {d}.") for m, d in sorted(active - before)]
        events += [("limit_ended", f"{METRICS[m][0]} {d} alert ended.") for m, d in sorted(before - active)]
        faults = {key for key, active_flag in {
            "Communication": status["communication_alert_active"],
            "BME680": status["sensor_alert_active"],
            "Dust": dust["alert_active"],
            "Patient profile": profile_error is not None,
        }.items() if active_flag}
        events += [("fault", f"{name} alert active.") for name in sorted(faults - self.previous_faults)]
        events += [("fault_ended", f"{name} alert cleared.") for name in sorted(self.previous_faults - faults)]
        self.previous_faults = faults
        status.update(updated_at=wall, occupancy=occupancy, demo=self.demo,
                      measurement_current=good, profile_error=profile_error,
                      limit_alerts=[f"{METRICS[m][0]} · {d}" for m, d in sorted(active)])
        self.store.publish(status, samples, events, wall)
