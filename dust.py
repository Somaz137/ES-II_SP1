"""Independent Sharp dust records and an estimated concentration; not PM2.5 or AQI."""
from collections import deque
from dataclasses import dataclass, replace
import json
import math

@dataclass(frozen=True)
class DustState:
    started_at: float = 0.0
    last_voltage_mv: float | None = None
    received_at: float | None = None
    seen: bool = False
    diagnostic: str | None = None

def parse_dust(line):
    try:
        data = json.loads(line)
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("type") not in ("dust", "dust_error"):
        return None
    if data["type"] == "dust_error":
        return (None, "Dust acquisition failed.")
    value = data.get("sensor_mv")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 5500:
        return (None, "Invalid dust sensor voltage.")
    return (float(value), None)

def record_dust(state, parsed, now):
    value, error = parsed
    if error:
        return replace(state, seen=True, diagnostic=error)
    return replace(state, seen=True, last_voltage_mv=value, received_at=now, diagnostic=None)

def dust_status(state, now, timeout_s, disconnected):
    reference = state.started_at if state.received_at is None else state.received_at
    stale = now - reference >= timeout_s
    status = "communication_lost" if disconnected else (
        "stale" if stale else "sensor_error" if state.diagnostic else
        "waiting_for_first_measurement" if state.received_at is None else "fresh")
    return {"status": status, "sensor_mv": state.last_voltage_mv,
            "age_s": None if state.received_at is None else now-state.received_at,
            "alert_active": stale and not disconnected,
            "diagnostic": state.diagnostic, "calibration": "not_configured",
            "estimated_dust_ug_m3": None}


def estimate_dust(sensor_mv, baseline_mv, sensitivity_mv_per_mg_m3):
    """Return an estimate in ug/m3; caller supplies measured calibration."""
    for value in (sensor_mv, baseline_mv, sensitivity_mv_per_mg_m3):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Calibration values must be finite numbers.")
        try:
            valid = math.isfinite(value)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("Calibration values must be finite numbers.")
    if not 0 <= baseline_mv <= 5500 or not 0 < sensor_mv <= 5500 or sensitivity_mv_per_mg_m3 <= 0:
        raise ValueError("Invalid calibration range.")
    result = max(0.0, sensor_mv-baseline_mv) * 1000 / sensitivity_mv_per_mg_m3
    if not math.isfinite(result):
        raise ValueError("Dust estimate overflow.")
    return result


class DustBaseline:
    """Clean-air baseline: the lowest fresh sensor voltage in the last window_s.

    Keeps one minimum per bucket_s, so memory is bounded by window_s / bucket_s.
    The baseline exists only after an unbroken run of fresh records lasting
    min_s. Two records more than gap_s apart, or reset() on a dust fault,
    clear everything. The history is in memory only: a restart starts again.
    """

    def __init__(self, window_s, min_s, gap_s, bucket_s=60):
        self.window_s, self.min_s, self.gap_s, self.bucket_s = window_s, min_s, gap_s, bucket_s
        self.buckets = deque(maxlen=int(math.ceil(window_s / bucket_s)) + 1)
        self.run_start = None
        self.last_at = None

    def reset(self):
        self.buckets.clear()
        self.run_start = self.last_at = None

    def add(self, sensor_mv, at):
        """Record one fresh voltage at monotonic time `at`."""
        if self.last_at is not None and at - self.last_at > self.gap_s:
            self.reset()
        if self.run_start is None:
            self.run_start = at
        self.last_at = at
        key = math.floor(at / self.bucket_s)
        if self.buckets and self.buckets[-1][0] == key:
            self.buckets[-1][1] = min(self.buckets[-1][1], sensor_mv)
        else:
            self.buckets.append([key, sensor_mv])
        while self.buckets and (self.buckets[0][0] + 1) * self.bucket_s <= at - self.window_s:
            self.buckets.popleft()

    def value(self, at):
        """The baseline in mV, or None while it is being established."""
        if self.run_start is None or at - self.run_start < self.min_s or not self.buckets:
            return None
        return min(minimum for _, minimum in self.buckets)
