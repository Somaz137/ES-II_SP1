"""Real JSON-line classification; run with the pinned pytest on Linux."""

import json

import pytest

from serial_parser import parse_serial_line

VALID_LINE = (
    '{"type":"reading","temp_c":25.5,"humidity_pct":45,'
    '"pressure_hpa":1013.25,"gas_ohms":12000}'
)


def test_valid_reading_returns_only_committable_measurements():
    result = parse_serial_line(VALID_LINE)
    assert result.kind == "valid_reading"
    assert result.measurements == {
        "temp_c": 25.5, "humidity_pct": 45,
        "pressure_hpa": 1013.25, "gas_ohms": 12000,
    }
    assert result.message is None


def test_accepts_serial_line_whitespace():
    result = parse_serial_line(" \r\n" + VALID_LINE + "\r\n")
    assert result.kind == "valid_reading"


def test_extra_fields_do_not_enter_the_measurement_snapshot():
    data = json.loads(VALID_LINE)
    data["debug"] = {"status": "extra"}
    result = parse_serial_line(json.dumps(data))
    assert result.kind == "valid_reading"
    assert set(result.measurements) == {
        "temp_c", "humidity_pct", "pressure_hpa", "gas_ohms",
    }


@pytest.mark.parametrize("message", ["bme680_not_found", "sensor_read_failed"])
def test_explicit_sensor_error_has_no_committable_values(message):
    result = parse_serial_line(json.dumps({"type": "error", "message": message}))
    assert result.kind == "sensor_error"
    assert result.message == message
    assert result.measurements is None


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "error"},
        {"type": "error", "message": None},
        {"type": "error", "message": ""},
        {"type": "error", "message": 7},
    ],
)
def test_error_type_remains_recognized_without_usable_diagnostic_text(payload):
    result = parse_serial_line(json.dumps(payload))
    assert result.kind == "sensor_error"
    assert result.message == "Sensor reported an error."
    assert result.measurements is None


@pytest.mark.parametrize(
    "field", ["temp_c", "humidity_pct", "pressure_hpa", "gas_ohms"]
)
def test_missing_measurement_is_incomplete_without_partial_values(field):
    payload = json.loads(VALID_LINE)
    del payload[field]
    result = parse_serial_line(json.dumps(payload))
    assert result.kind == "incomplete_reading"
    assert field in result.message
    assert result.measurements is None


@pytest.mark.parametrize(
    "value", ["25", True, None, float("nan"), float("inf"), float("-inf")]
)
def test_invalid_measurement_is_incomplete_without_partial_values(value):
    payload = json.loads(VALID_LINE)
    payload["temp_c"] = value
    result = parse_serial_line(json.dumps(payload))
    assert result.kind == "incomplete_reading"
    assert "temp_c" in result.message
    assert result.measurements is None


def test_valid_json_numeric_overflow_is_not_a_valid_measurement():
    line = VALID_LINE.replace('"temp_c":25.5', '"temp_c":1e999')
    result = parse_serial_line(line)
    assert result.kind == "incomplete_reading"
    assert result.measurements is None


@pytest.mark.parametrize(
    "line",
    ["", "   ", "ESP32 booting", "{", '{"type":"reading",', "[1,2]",
     '"reading"', "123", "true", "null", "{}", '{"type":"unknown"}',
     '{"type":"Reading"}', '{"temp_c":25}'],
)
def test_unreadable_or_unrecognized_lines_are_ignored(line):
    result = parse_serial_line(line)
    assert result.kind == "ignored"
    assert result.measurements is None


def test_unreadable_deep_input_is_ignored():
    line = "[" * 2000 + "0" + "]" * 2000
    assert parse_serial_line(line).kind == "ignored"


@pytest.mark.parametrize("line", [None, {}, b'{"type":"error"}'])
def test_caller_must_supply_decoded_serial_text(line):
    with pytest.raises(TypeError, match="decoded"):
        parse_serial_line(line)

