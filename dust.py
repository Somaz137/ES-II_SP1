"""Independent Sharp dust records; voltage is not PM2.5 or AQI."""
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
