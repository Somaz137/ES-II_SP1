"""Route one decoded serial line through real parsing and monitoring state."""

from dataclasses import replace

from communication_fault import (
    evaluate_communication_fault,
    record_communication_message,
)
from monitoring_state import MonitoringState, evaluate_monitoring_faults
from reading_state import commit_reading, record_reading_problem
from sensor_fault import (
    evaluate_sensor_fault,
    record_sensor_error,
    record_valid_measurement,
)
from serial_parser import parse_serial_line


def process_serial_line(
    state: MonitoringState, line: str, now: float
) -> MonitoringState:
    """Return a new state for one line and its host receipt time.

    Supply finite, nondecreasing times in the same domain as startup and
    periodic checks. Ignored lines still allow fault checks. This function
    performs no port access, scheduling, notification or gas readiness work.
    """
    parsed = parse_serial_line(line)
    if parsed.kind == "ignored":
        return evaluate_monitoring_faults(state, now)

    # Detect preceding silence before the message restores communication.
    communication = evaluate_communication_fault(state.communication, now)
    sensor = state.sensor
    if communication.timed_out:
        sensor = evaluate_sensor_fault(sensor, now, communication_timed_out=True)
    communication = record_communication_message(communication, now)

    if parsed.kind == "valid_reading":
        reading = commit_reading(state.reading, parsed.measurements, now)
        sensor = record_valid_measurement(sensor, now)
    else:
        kind = "incomplete" if parsed.kind == "incomplete_reading" else "sensor_error"
        reading = record_reading_problem(state.reading, kind, parsed.message)
        sensor = record_sensor_error(sensor, now)

    return replace(state, communication=communication, sensor=sensor, reading=reading)
