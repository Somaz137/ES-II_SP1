"""Classify decoded ESP32 serial lines without hardware or tracker side effects."""

from dataclasses import dataclass, field
import json
from typing import Literal

from measurements import MEASUREMENT_FIELDS, validate_measurements
from gas_readiness import GasReadiness, parse_gas_readiness

MessageKind = Literal[
    "valid_reading", "sensor_error", "incomplete_reading", "ignored"
]


@dataclass(frozen=True)
class ParsedSerialMessage:
    """One classification; only valid_reading carries committable values."""

    kind: MessageKind
    measurements: dict[str, int | float] | None = None
    message: str | None = None
    gas: GasReadiness = field(default_factory=GasReadiness)


def parse_serial_line(line: str) -> ParsedSerialMessage:
    """Parse one decoded line using the starter firmware's JSON record types.

    Decoder failures, non-object JSON and unknown types are ignored.
    Reading records with missing/unusable values are incomplete sensor input;
    they carry no partial values to commit. The standard decoder can accept
    NaN/Infinity, but measurement validation rejects them as incomplete.
    Error records remain recognized even without usable diagnostic text.

    This function does not read ports, update timers, or store measurements.
    """
    if not isinstance(line, str):
        raise TypeError("line must be decoded serial text.")
    try:
        payload = json.loads(line)
    except (ValueError, RecursionError):
        return ParsedSerialMessage(kind="ignored")

    if not isinstance(payload, dict):
        return ParsedSerialMessage(kind="ignored")

    record_type = payload.get("type")
    if record_type == "error":
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            message = "Sensor reported an error."
        return ParsedSerialMessage(
            kind="sensor_error", message=message,
            gas=parse_gas_readiness(payload.get("bsec")),
        )

    if record_type != "reading":
        return ParsedSerialMessage(kind="ignored")

    try:
        validate_measurements(payload)
    except ValueError as error:
        return ParsedSerialMessage(
            kind="incomplete_reading", message=str(error),
            gas=parse_gas_readiness(payload.get("bsec")),
        )

    return ParsedSerialMessage(
        kind="valid_reading",
        measurements={field: payload[field] for field in MEASUREMENT_FIELDS},
        gas=parse_gas_readiness(payload.get("bsec")),
    )
