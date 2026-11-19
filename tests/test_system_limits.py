"""Air quality and dust estimate: published state, system-limit alerts, alarm, and the profile label."""
import copy
import json
from types import SimpleNamespace

import pytest

from alarm import AlarmTracker
from monitoring_state import create_monitoring_state, evaluate_monitoring_faults, process_serial_line
from room_session import RoomSession
from room_store import RoomStore, validate_profile
from settings import DEMO_SYSTEM_SETTINGS, SYSTEM_DEFAULTS
from status_output import status_record


def system(aq=None, dust=None, min_s=9):
    data = copy.deepcopy(SYSTEM_DEFAULTS)
    if aq:
        data["air_quality"].update(upper_limit=aq[0], hold_s=aq[1])
    if dust:
        data["dust"].update(upper_limit=dust[0], hold_s=dust[1])
    data["dust"]["baseline_min_s"] = min_s
    return data


def reading(iaq=60, accuracy=3, temp=24):
    bsec = {"stabilization_status": 1, "run_in_status": 1, "iaq_accuracy": accuracy}
    if iaq is not None:
        bsec["iaq"] = iaq
    return json.dumps({"type": "reading", "temp_c": temp, "humidity_pct": 48, "pressure_hpa": 1008,
                       "gas_ohms": 12000, "bsec": bsec})


class Room:
    def __init__(self, tmp_path, settings=None, profile=None, alarm=None):
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.store = RoomStore(tmp_path / "room.sqlite3")
        if profile is not None:
            self.store.save_profile(profile)
        self.session = RoomSession(self.store, system=settings, alarm=alarm)
        self.state = create_monitoring_state(0, 120, 120)
        self.transport = SimpleNamespace(connected=True, last_error=None, send=lambda line: True)

    def step(self, now, line=None, dust_mv=None, occupancy="occupied", reply=None):
        if line is not None:
            self.state = process_serial_line(self.state, line, now)
        if dust_mv is not None:
            self.state = process_serial_line(self.state, json.dumps({"type": "dust", "sensor_mv": dust_mv}), now)
        status = status_record(self.state, now, self.transport, monotonic_origin=0, utc_origin=100000)
        self.session.update(status, now, now + 100000, occupancy,
                            alarm_reply=reply, transport=self.transport)
        return status

    def kinds(self):
        return [event["kind"] for event in self.store.events()]

    def messages(self):
        return [event["message"] for event in self.store.events()]


# Air quality.

def test_air_quality_block_is_calibrating_until_bosch_accuracy_reaches_two(tmp_path):
    room = Room(tmp_path, system(aq=(150, 6)))
    status = room.step(0, reading(iaq=None, accuracy=0))
    block = status["air_quality"]
    assert block["state"] == "calibrating" and block["value"] is None and block["band"] is None
    assert block["check"] == {"state": "paused", "reason": "calibrating",
                              "message": "The Bosch index is calibrating. The air quality check is paused."}
    assert block["name"] == "Air quality index" and block["unit"] == ""
    assert block["estimate"] is True and block["source"] == "Bosch estimate"
    assert block["limit"] == 150 and block["hold_s"] == 6
    status = room.step(3, reading(iaq=57.25, accuracy=2))
    assert status["air_quality"]["state"] == "current"
    assert status["air_quality"]["value"] == 57.25 and status["air_quality"]["band"] == "good"
    assert status["air_quality"]["accuracy"] == 2
    assert status["air_quality"]["check"]["state"] == "running"


def test_retained_index_is_not_shown_as_current(tmp_path):
    room = Room(tmp_path)
    room.step(0, reading(iaq=80))
    status = room.step(10)  # older than the reading-gap limit
    assert status["air_quality"]["state"] == "unavailable" and status["air_quality"]["value"] is None
    assert status["bsec_iaq"] == 80  # still available as a system detail


def test_shipped_settings_leave_both_checks_off(tmp_path):
    status = Room(tmp_path).step(0, reading(iaq=400), dust_mv=900)
    assert status["air_quality"]["check"] == {
        "state": "off", "reason": "no_limit",
        "message": "No air quality limit is set in the system settings."}
    assert status["dust_ugm3"]["check"] == {
        "state": "off", "reason": "no_limit", "message": "No dust limit is set in the system settings."}
    assert status["limit_alerts"] == [] and status["limit_pending"] == []


def test_sustained_air_quality_breach_alerts_and_ends(tmp_path):
    room = Room(tmp_path, system(aq=(150, 6)))
    room.step(0, reading(iaq=182))
    status = room.step(3, reading(iaq=182))
    assert status["limit_pending"] == [{
        "metric": "air_quality", "name": "Air quality index", "unit": "", "direction": "high",
        "limit": 150, "value": 182, "breach_started_at": 100000, "elapsed_s": 3, "hold_s": 6,
        "remaining_s": 3}]
    status = room.step(6, reading(iaq=182))
    assert [alert["metric"] for alert in status["limit_alerts"]] == ["air_quality"]
    assert room.messages()[0] == "Air quality index above the configured limit of 150 for 6 s. Value 182."
    room.step(9, reading(iaq=90))
    assert room.messages()[0] == ("Air quality index above the configured limit of 150: alert ended after 3 s. "
                                  "Value 90 is within the configured limits.")


def test_air_quality_alert_needs_occupancy_and_stops_when_bosch_recalibrates(tmp_path):
    room = Room(tmp_path, system(aq=(150, 3)))
    room.step(0, reading(iaq=182), occupancy="unknown")
    status = room.step(3, reading(iaq=182), occupancy="unknown")
    assert status["limit_pending"] == [] and status["air_quality"]["check"]["reason"] == "occupancy_unknown"
    room.step(6, reading(iaq=182))
    assert room.step(9, reading(iaq=182))["limit_alerts"]
    status = room.step(12, reading(iaq=182, accuracy=1))
    assert status["limit_alerts"] == []
    assert room.kinds()[0] == "limit_reset_estimate"
    assert room.messages()[0] == (
        "Air quality index above the configured limit of 150: alert stopped after 3 s because the Bosch "
        "index is calibrating. Last value 182. The air quality check is paused.")


def test_air_quality_check_is_independent_of_the_patient_profile(tmp_path):
    room = Room(tmp_path, system(aq=(150, 3)), profile={"limits": {"temp_c": [20, 27]}, "hold_s": 3})
    room.step(0, reading(iaq=182))
    assert room.step(3, reading(iaq=182))["limit_alerts"]
    room.store.save_profile({"limits": {"temp_c": [20, 28]}, "hold_s": 3})
    status = room.step(6, reading(iaq=182))
    assert [alert["metric"] for alert in status["limit_alerts"]] == ["air_quality"]
    room.store.profile_path.unlink()
    status = room.step(9, reading(iaq=182))
    assert status["limit_monitoring"]["reason"] == "no_profile"
    assert [alert["metric"] for alert in status["limit_alerts"]] == ["air_quality"]


# Dust estimate.

def test_dust_establishes_a_baseline_before_showing_an_estimate(tmp_path):
    room = Room(tmp_path, system(dust=(100, 6), min_s=6))
    status = room.step(0, reading(), dust_mv=920)
    block = status["dust_ugm3"]
    assert block["state"] == "establishing_baseline" and block["value"] is None and block["level"] is None
    assert block["check"] == {"state": "paused", "reason": "establishing_baseline",
                              "message": "The dust baseline is being established. The dust check is paused."}
    assert block["name"] == "Dust estimate" and block["unit"] == "µg/m³"
    assert block["estimate"] is True and block["source"] == "estimate"
    assert block["sensitivity_mv_per_mg_m3"] == 5000
    room.step(3, reading(), dust_mv=1000)
    status = room.step(6, reading(), dust_mv=1170)
    block = status["dust_ugm3"]
    assert block["state"] == "current" and block["baseline_mv"] == 920
    assert block["value"] == pytest.approx(50) and block["level"] == "low"
    assert status["dust"]["estimated_dust_ug_m3"] == pytest.approx(50)
    assert status["dust"]["calibration"] == "automatic_baseline"


def test_dust_fault_clears_the_baseline(tmp_path):
    room = Room(tmp_path, system(min_s=3))
    room.step(0, reading(), dust_mv=920)
    assert room.step(3, reading(), dust_mv=930)["dust_ugm3"]["state"] == "current"
    room.step(6, reading(), dust_mv=None)
    room.state = process_serial_line(room.state, '{"type":"dust_error"}', 6)
    assert room.step(6)["dust_ugm3"]["state"] == "unavailable"
    assert room.step(9, reading(), dust_mv=990)["dust_ugm3"]["state"] == "establishing_baseline"


def test_stale_dust_record_is_not_current(tmp_path):
    room = Room(tmp_path, system(min_s=3))
    room.step(0, reading(), dust_mv=920)
    room.step(3, reading(), dust_mv=930)
    status = room.step(10, reading())
    assert status["dust_ugm3"]["state"] == "unavailable" and status["dust_ugm3"]["value"] is None
    assert status["dust_ugm3"]["check"]["state"] == "off"


def test_sustained_dust_breach_alerts_and_sounds_the_buzzer(tmp_path):
    room = Room(tmp_path, system(dust=(100, 6), min_s=3), alarm=AlarmTracker(2, id_prefix="t"))
    room.step(0, reading(), dust_mv=920)
    room.step(3, reading(), dust_mv=920)
    room.step(6, reading(), dust_mv=1600)
    status = room.step(9, reading(), dust_mv=1600)
    assert status["limit_pending"][0]["metric"] == "dust_ugm3"
    status = room.step(12, reading(), dust_mv=1600)
    alert = status["limit_alerts"][0]
    assert {key: alert[key] for key in ("metric", "name", "unit", "direction", "limit")} == {
        "metric": "dust_ugm3", "name": "Dust estimate", "unit": "µg/m³", "direction": "high", "limit": 100}
    assert alert["value"] == pytest.approx(136)
    assert room.messages()[0] == "Dust estimate above the configured limit of 100 µg/m³ for 6 s. Value 136 µg/m³."
    assert status["alarm"]["wanted_level"] == 2
    token = status["alarm"]["silence_token"]
    assert room.session.silence_alarm(token, 100013)
    status = room.step(15, reading(), dust_mv=1600)
    assert status["alarm"]["wanted_level"] == 1 and status["alarm"]["silenced"]
    assert any(message.startswith("Local alarm silenced on the dashboard. Buzzer off for: Dust estimate above "
                                  "the configured limit of 100 µg/m³.") for message in room.messages())


def test_dust_alert_stops_when_dust_records_stop(tmp_path):
    room = Room(tmp_path, system(dust=(100, 3), min_s=3))
    room.step(0, reading(), dust_mv=920)
    room.step(3, reading(), dust_mv=1600)
    assert room.step(6, reading(), dust_mv=1600)["limit_alerts"]
    status = room.step(13, reading())
    assert status["limit_alerts"] == [] and room.kinds()[0] == "limit_reset_reading"
    assert "because dust readings are not current" in room.messages()[0]
    assert status["dust_ugm3"]["check"]["reason"] == "reading_not_current"


def test_current_estimates_are_stored_as_series(tmp_path):
    room = Room(tmp_path, system(min_s=3))
    room.step(0, reading(iaq=None, accuracy=0), dust_mv=920)
    room.step(3, reading(iaq=70), dust_mv=1420)
    assert room.store.history("air_quality", 100060) == [{"at": 99960, "avg": 70, "min": 70, "max": 70}]
    assert room.store.history("dust_ugm3", 100060) == [{"at": 99960, "avg": 100, "min": 100, "max": 100}]


def test_demo_settings_drive_the_simulated_episode(tmp_path):
    from simulated_input import SimulatedTransport

    room = Room(tmp_path, DEMO_SYSTEM_SETTINGS)
    transport = SimpleNamespace(connected=True, last_error=None, send=lambda line: True)
    simulated = SimulatedTransport()
    seen = {}
    for now in range(0, 301, 3):
        for line in simulated.poll(now):
            room.state = process_serial_line(room.state, line, now)
        status = status_record(room.state, now, transport, monotonic_origin=0, utc_origin=100000)
        room.session.update(status, now, now + 100000, "occupied")
        seen[now] = status
    assert seen[0]["air_quality"]["state"] == "calibrating"
    assert seen[60]["air_quality"]["state"] == "current"
    assert seen[90]["dust_ugm3"]["state"] == "current"
    metrics = {alert["metric"] for status in seen.values() for alert in status["limit_alerts"]}
    assert metrics == {"air_quality", "dust_ugm3"}


# Profile label.

@pytest.mark.parametrize("label", ["", "Bed 3", "x" * 40, "Zimmer 4 – Fenster"])
def test_valid_labels(label):
    validate_profile({"limits": {}, "hold_s": 9, "label": label})


@pytest.mark.parametrize("label", ["x" * 41, " Bed 3", "Bed 3 ", "Bed\n3", "Bed\t3", "Bed\x00", "Bed​3",
                                   "Bed 3", 3, None])
def test_invalid_labels(label):
    with pytest.raises(ValueError, match="label"):
        validate_profile({"limits": {}, "hold_s": 9, "label": label})


def test_profile_change_event_names_the_label(tmp_path):
    room = Room(tmp_path, profile={"limits": {"temp_c": [20, 27]}, "hold_s": 9})
    room.step(0, reading())
    assert "profile_changed" not in room.kinds()  # loading at start is not a change
    room.store.save_profile({"limits": {"temp_c": [20, 27], "humidity_pct": [30, 60]}, "hold_s": 9,
                             "label": "Bed 3"})
    room.step(3, reading())
    assert room.kinds() == ["profile_changed"]
    assert room.messages()[0] == ('Patient profile changed. Label "Bed 3". Temperature 20 to 27 °C; '
                                  'Humidity 30 to 60 %. Sustained duration 9 s.')
    room.store.save_profile({"limits": {}, "hold_s": 9})
    room.step(6, reading())
    assert room.messages()[0] == ("Patient profile changed. No label. No measurement limits. "
                                  "Sustained duration 9 s.")


# Dust floor.

@pytest.mark.parametrize("value", [0, -1, 5501, True])
def test_floor_setting_validated(value):
    from settings import validate_system_settings
    data = copy.deepcopy(SYSTEM_DEFAULTS)
    data["dust"]["disconnected_below_mv"] = value
    with pytest.raises(ValueError):
        validate_system_settings(data)


def test_floor_default_is_100_in_yaml_and_defaults():
    from pathlib import Path
    from settings import load_system_settings
    loaded = load_system_settings(Path(__file__).resolve().parents[1] / "config" / "system.yaml")
    assert loaded["dust"]["disconnected_below_mv"] == 100
    assert SYSTEM_DEFAULTS["dust"]["disconnected_below_mv"] == 100


def test_below_floor_records_give_no_dust_estimate_or_baseline(tmp_path):
    room = Room(tmp_path, system(dust=(100, 6), min_s=0))
    for now in range(0, 150, 3):
        status = room.step(now, reading(), dust_mv=50)
        assert status["dust_ugm3"]["baseline_mv"] is None
        assert status["dust"]["estimated_dust_ug_m3"] is None
    assert status["dust"]["status"] == "not_connected"
    assert room.session.baseline.value(now) is None and not room.session.baseline.buckets
    assert room.store.history("dust_ugm3", now + 100000) == []
    assert room.store.history("dust_mv", now + 100000) == []


@pytest.mark.parametrize("value", [100, 50.5, 5500])
def test_floor_setting_accepts_a_value_in_range(value):
    from settings import validate_system_settings
    data = copy.deepcopy(SYSTEM_DEFAULTS)
    data["dust"]["disconnected_below_mv"] = value
    validate_system_settings(data)
