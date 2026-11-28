"""Classify decoded ESP32 serial lines without hardware or tracker side effects."""

from dataclasses import dataclass, field
import json
from typing import Literal

from measurements import MEASUREMENT_FIELDS, validate_measurements
from gas_readiness import GasReadiness, parse_gas_readiness
from bsec_state_store import is_accuracy, is_bsec_version, is_state_hex

MessageKind = Literal[
    "valid_reading", "sensor_error", "incomplete_reading", "alarm_state",
    "bsec_state", "bsec_state_request", "bsec_state_restored", "bsec_state_save_failed",
    "ignored",
]
# The board's error message when it cannot read its BSEC state to save it.
BSEC_SAVE_FAILED = "bsec_state_save_failed"
ALARM_LEVELS = (0, 1, 2)


@dataclass(frozen=True)
class ParsedSerialMessage:
    """One classification; only valid_reading carries committable values."""

    kind: MessageKind
    measurements: dict[str, int | float] | None = None
    message: str | None = None
    gas: GasReadiness = field(default_factory=GasReadiness)
    alarm_level: int | None = None
    bsec_version: str | None = None
    bsec_accuracy: int | None = None
    bsec_state_hex: str | None = None  # lowercase
    restore_ok: bool | None = None


def parse_serial_line(line: str) -> ParsedSerialMessage:
    """Parse one decoded line using the starter firmware's JSON record types.

    Decoder failures, non-object JSON and unknown types are ignored.
    Reading records with missing/unusable values are incomplete sensor input;
    they carry no partial values to commit. The standard decoder can accept
    NaN/Infinity, but measurement validation rejects them as incomplete.
    Error records remain recognized even without usable diagnostic text.
    Alarm records with state 0, 1 or 2 are alarm_state; other alarm records
    are ignored. BSEC state records (state, request, restored) with unusable
    fields are ignored. The error message bsec_state_save_failed is its own
    kind, not a sensor error.

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
    if record_type == "error" and payload.get("message") == BSEC_SAVE_FAILED:
        return ParsedSerialMessage(kind="bsec_state_save_failed")
    if record_type == "error":
        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            message = "Sensor reported an error."
        return ParsedSerialMessage(
            kind="sensor_error", message=message,
            gas=parse_gas_readiness(payload.get("bsec")),
        )

    if record_type == "alarm":
        # The board's reply after applying an ALARM command. Not a reading.
        level = payload.get("state")
        if type(level) is int and level in ALARM_LEVELS:
            return ParsedSerialMessage(kind="alarm_state", alarm_level=level)
        return ParsedSerialMessage(kind="ignored")

    if record_type in ("bsec_state", "bsec_state_request", "bsec_state_restored"):
        return parse_bsec_record(record_type, payload)

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


def parse_bsec_record(record_type, payload):
    """One of the board's BSEC state lines, or ignored when a field is unusable."""
    version = payload.get("bsec_version")
    if record_type == "bsec_state_restored":
        ok = payload.get("ok")
        if type(ok) is bool:
            return ParsedSerialMessage(kind="bsec_state_restored", restore_ok=ok)
    elif not is_bsec_version(version):
        pass
    elif record_type == "bsec_state_request":
        return ParsedSerialMessage(kind="bsec_state_request", bsec_version=version)
    elif is_accuracy(payload.get("accuracy")) and is_state_hex(payload.get("state")):
        return ParsedSerialMessage(
            kind="bsec_state", bsec_version=version, bsec_accuracy=payload["accuracy"],
            bsec_state_hex=payload["state"].lower(),
        )
    return ParsedSerialMessage(kind="ignored")
