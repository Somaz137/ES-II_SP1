"""Reading retention scenarios. Execution is deferred to the Linux environment."""

import pytest

from reading_state import ReadingState, commit_reading, record_reading_problem


def measurements():
    return {"temp_c": 24.0, "humidity_pct": 45.0,
            "pressure_hpa": 1005.0, "gas_ohms": 12000.0}


def test_startup_has_no_invented_measurement():
    state = ReadingState()
    assert state.last_reading is None
    assert state.input_status == "waiting_for_first_measurement"


def test_commit_copies_values_instead_of_retaining_mutable_dictionary():
    data = measurements()
    original = ReadingState()
    state = commit_reading(original, data, 10)
    data["temp_c"] = 99
    assert state.last_reading.temp_c == 24.0
    assert state.last_reading.received_at == 10
    assert state.input_status == "fresh"
    assert original.last_reading is None


@pytest.mark.parametrize("kind", ["incomplete", "sensor_error"])
def test_problem_preserves_complete_values_and_their_time(kind):
    state = commit_reading(ReadingState(), measurements(), 10)
    problem = record_reading_problem(state, kind, "Input problem")
    assert problem.last_reading is state.last_reading
    assert problem.last_reading.received_at == 10
    assert problem.input_status == kind
    assert problem.diagnostic == "Input problem"


def test_new_measurement_replaces_old_values_and_clears_diagnostic():
    old = commit_reading(ReadingState(), measurements(), 10)
    problem = record_reading_problem(old, "incomplete", "Missing gas")
    new = measurements()
    new["temp_c"] = 25
    state = commit_reading(problem, new, 20)
    assert state.last_reading.temp_c == 25
    assert state.last_reading.received_at == 20
    assert state.diagnostic is None
    assert old.last_reading.temp_c == 24


@pytest.mark.parametrize("now", [True, "10", float("nan"), float("inf"), 9])
def test_commit_rejects_invalid_or_backwards_time(now):
    state = commit_reading(ReadingState(), measurements(), 10)
    with pytest.raises(ValueError):
        commit_reading(state, measurements(), now)


def test_incomplete_dictionary_cannot_be_committed():
    with pytest.raises(ValueError):
        commit_reading(ReadingState(), {"temp_c": 24}, 10)


def test_problem_rejects_unknown_status():
    with pytest.raises(ValueError):
        record_reading_problem(ReadingState(), "fresh", "Not an error")
