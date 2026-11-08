"""JSON-ready terminal facts; no room-safety verdict or alert acknowledgment."""

from dataclasses import asdict
from datetime import datetime, timezone

from gas_readiness import gas_calibration_status
from monitoring_state import current_gas_warmup_status, monitoring_status


def status_record(state, now, transport, *, monotonic_origin, utc_origin):
    """Map receipt time to estimated UTC using one startup wall-clock anchor.

    Wall-clock corrections after startup do not alter timers or this mapping.
    Retained readings retain their original timestamp; UTC is an estimate.
    """
    reading = state.reading.last_reading
    received = None if reading is None else reading.received_at
    utc = None if received is None else datetime.fromtimestamp(
        utc_origin + received - monotonic_origin, timezone.utc
    ).isoformat()
    available = current_gas_warmup_status(state) != "unavailable"
    return {
        "input_status": monitoring_status(state),
        "transport_connected": transport.connected,
        "transport_error": transport.last_error,
        "last_reading": None if reading is None else asdict(reading),
        "last_measurement_received_utc_estimate": utc,
        "measurement_age_s": None if received is None else now - received,
        "last_contact_age_s": None if state.communication.last_message_at is None
        else now - state.communication.last_message_at,
        "communication_timed_out": state.communication.timed_out,
        "communication_alert_active": state.communication.alert_active,
        "sensor_alert_active": state.sensor.alert_active,
        "diagnostic": state.reading.diagnostic,
        "gas_warmup": current_gas_warmup_status(state),
        "gas_calibration": gas_calibration_status(state.gas) if available else "unavailable",
    }
