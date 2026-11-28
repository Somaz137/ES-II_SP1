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


@pytest.fixture(autouse=True)
def one_reading_makes_a_baseline_bucket(monkeypatch):
    """These room tests use a few dust records at 3 s. A 1 s bucket with 1 reading makes each record
    its own bucket (the lowest record is the baseline). The bucket-mean rule is tested in test_dust.py."""
    import dust
    import room_session
    monkeypatch.setattr(dust, "BASELINE_BUCKET_MIN_READINGS", 1)
    monkeypatch.setattr(room_session, "DustBaseline",
                        lambda window_s, min_s, gap_s: dust.DustBaseline(window_s, min_s, gap_s, bucket_s=1))


def system(aq=None, dust=None, min_s=9):
    data = copy.deepcopy(SYSTEM_DEFAULTS)
    if aq:
        data["air_quality"].update(upper_limit=aq[0], hold_s=aq[1])
    if dust:
        data["dust"].update(upper_limit=dust[0], hold_s=dust[1])
    data["dust"]["baseline_min_s"] = min_s
    return data


def reading(iaq=60, accuracy=3, temp=24, gas=12000):
    bsec = {"stabilization_status": 1, "run_in_status": 1, "iaq_accuracy": accuracy}
    if iaq is not None:
        bsec["iaq"] = iaq
    return json.dumps({"type": "reading", "temp_c": temp, "humidity_pct": 48, "pressure_hpa": 1008,
                       "gas_ohms": gas, "bsec": bsec})


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
    assert block["value"] == pytest.approx(50) and block["level"] == "clean"
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


def test_one_lost_dust_record_keeps_the_baseline(tmp_path):
    room = Room(tmp_path, system(min_s=3))
    room.step(0, reading(), dust_mv=920)
    room.step(3, reading(), dust_mv=930)
    assert room.step(10, reading(), dust_mv=1170)["dust_ugm3"]["state"] == "current"  # 7 s gap
    block = room.step(13, reading(), dust_mv=1170)["dust_ugm3"]
    assert block["state"] == "current" and block["baseline_mv"] == 920


def test_dust_gap_over_baseline_gap_s_resets_the_baseline(tmp_path):
    room = Room(tmp_path, system(min_s=3))
    room.step(0, reading(), dust_mv=920)
    room.step(3, reading(), dust_mv=930)
    assert room.step(70, reading(), dust_mv=930)["dust_ugm3"]["state"] == "establishing_baseline"


def test_limit_check_still_resets_after_a_gap_over_the_reading_limit(tmp_path):
    room = Room(tmp_path, system(dust=(100, 3), min_s=3))
    room.step(0, reading(), dust_mv=920)
    room.step(3, reading(), dust_mv=920)
    room.step(6, reading(), dust_mv=1600)
    assert room.step(9, reading(), dust_mv=1600)["limit_alerts"]
    status = room.step(16, reading(), dust_mv=1600)  # 7 s gap: the baseline stays, the alert ends
    assert room.kinds().count("limit_reset_reading") == 1
    assert status["dust_ugm3"]["state"] == "current" and status["limit_alerts"] == []


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


# Gas sensor fault: gas resistance stuck at the open-circuit value.

FAULT_OHMS = 12917166
FAULT_TEXT = "Not available: gas sensor fault"


def stuck(room, times, gas=FAULT_OHMS, iaq=60, start=0):
    status = None
    for index, now in enumerate(times):
        status = room.step(now, reading(iaq=iaq, gas=gas), occupancy="occupied")
    return status


def test_gas_fault_constants_live_in_one_place():
    import air_quality
    assert air_quality.GAS_FAULT_OHMS == FAULT_OHMS
    assert air_quality.GAS_FAULT_TOLERANCE == 2 and air_quality.GAS_FAULT_READINGS == 3
    assert air_quality.GAS_FAULT_CLEAR_READINGS == 20


def test_gas_fault_starts_after_three_readings_not_two(tmp_path):
    room = Room(tmp_path)
    status = stuck(room, [0, 3])
    assert status["air_quality"]["state"] == "current" and status["gas_sensor_fault"] is False
    status = room.step(6, reading(gas=FAULT_OHMS))
    block = status["air_quality"]
    assert status["gas_sensor_fault"] is True
    assert block["state"] == "unavailable" and block["value"] is None and block["band"] is None
    assert block["reason"] == "gas_sensor_fault" and block["message"] == FAULT_TEXT


@pytest.mark.parametrize("gas, faulted", [(FAULT_OHMS - 2, True), (FAULT_OHMS + 2, True),
                                          (FAULT_OHMS - 3, False), (FAULT_OHMS + 3, False)])
def test_gas_fault_tolerance_is_two_ohms(tmp_path, gas, faulted):
    status = stuck(Room(tmp_path), [0, 3, 6], gas=gas)
    assert status["gas_sensor_fault"] is faulted


def test_a_normal_reading_interrupts_the_start_count_and_twenty_clear_the_fault(tmp_path):
    room = Room(tmp_path)
    stuck(room, [0, 3])
    assert room.step(6, reading(gas=12000))["gas_sensor_fault"] is False
    assert room.step(9, reading(gas=FAULT_OHMS))["gas_sensor_fault"] is False  # the count restarted
    status = stuck(room, [12, 15])
    assert status["gas_sensor_fault"] is True
    status = room.step(18, reading(gas=250000))
    assert status["gas_sensor_fault"] is True  # one normal reading no longer clears it
    status = normal(room, 21, 19, iaq=60)
    assert status["gas_sensor_fault"] is False and status["air_quality"]["state"] == "current"
    assert status["air_quality"]["value"] == 60


def test_the_same_reading_seen_twice_counts_once(tmp_path):
    room = Room(tmp_path)
    room.step(0, reading(gas=FAULT_OHMS))
    room.step(3, reading(gas=FAULT_OHMS))
    assert room.step(4)["gas_sensor_fault"] is False
    assert room.step(5)["gas_sensor_fault"] is False


def test_air_quality_alarm_check_is_suppressed_while_faulted(tmp_path):
    room = Room(tmp_path, system(aq=(150, 6)))
    status = stuck(room, [0, 3, 6, 9, 12], iaq=400)
    assert status["gas_sensor_fault"] is True
    assert status["limit_alerts"] == [] and status["limit_pending"] == []
    assert not [m for m in room.messages() if "Air quality" in m and "limit" in m]
    assert status["air_quality"]["check"]["state"] == "paused"
    assert status["air_quality"]["check"]["reason"] == "gas_sensor_fault"


def test_a_breach_in_progress_ends_when_the_fault_starts(tmp_path):
    room = Room(tmp_path, system(aq=(150, 60)))
    room.step(0, reading(iaq=400))
    assert room.step(3, reading(iaq=400))["limit_pending"]
    for now in (6, 9, 12):
        status = room.step(now, reading(iaq=400, gas=FAULT_OHMS))
    assert status["limit_pending"] == []


def test_gas_fault_is_logged_when_it_starts_and_clears(tmp_path):
    room = Room(tmp_path)
    stuck(room, [0, 3, 6])
    normal(room, 9, 20, iaq=60, gas=12000)
    assert room.kinds().count("fault") == 1 and room.kinds().count("fault_ended") == 1
    assert "Gas sensor alert active." in room.messages()
    assert "Gas sensor alert cleared." in room.messages()


def test_system_page_script_shows_the_gas_sensor_fault():
    from pathlib import Path
    script = Path("static/room.js").read_text(encoding="utf-8")
    assert "gas_sensor_fault" in script and "block.message" in script
    assert 'name === "Gas sensor" && v.status.gas_sensor_fault' in script  # string check only: no JS runner in the repo


def normal(room, start, count, iaq=500, gas=250000):
    status = None
    for index in range(count):
        status = room.step(start + 3 * index, reading(iaq=iaq, gas=gas), occupancy="occupied")
    return status


@pytest.mark.parametrize("count", [1, 19])
def test_gas_fault_does_not_clear_before_twenty_normal_readings(tmp_path, count):
    room = Room(tmp_path)
    stuck(room, [0, 3, 6])
    status = normal(room, 9, count)
    assert status["gas_sensor_fault"] is True
    assert status["air_quality"]["state"] == "unavailable" and status["air_quality"]["value"] is None


def test_gas_fault_clears_after_twenty_normal_readings(tmp_path):
    room = Room(tmp_path)
    stuck(room, [0, 3, 6])
    status = normal(room, 9, 20)
    assert status["gas_sensor_fault"] is False
    assert status["air_quality"]["state"] == "current" and status["air_quality"]["value"] == 500


def test_a_stuck_reading_in_the_clearing_run_restarts_it(tmp_path):
    room = Room(tmp_path)
    stuck(room, [0, 3, 6])
    normal(room, 9, 19)
    assert room.step(100, reading(gas=FAULT_OHMS))["gas_sensor_fault"] is True
    assert normal(room, 103, 19)["gas_sensor_fault"] is True
    assert normal(room, 160, 1)["gas_sensor_fault"] is False


def test_no_air_quality_sample_is_stored_while_faulted_or_clearing(tmp_path):
    room = Room(tmp_path)
    stuck(room, [0, 3, 6])
    normal(room, 9, 19, iaq=500)
    assert [b["max"] for b in room.store.history("air_quality", 100100)] == [60.0]  # only the 2 readings before the fault
    assert "Gas sensor alert cleared." not in room.messages()
    normal(room, 70, 1, iaq=500)  # the 20th normal reading clears the fault and 500 is stored
    assert max(b["max"] for b in room.store.history("air_quality", 100100)) == 500


def test_one_fault_ended_event_when_the_fault_really_clears(tmp_path):
    room = Room(tmp_path)
    stuck(room, [0, 3, 6])
    normal(room, 9, 10)
    room.step(50, reading(gas=FAULT_OHMS))
    normal(room, 60, 25)
    assert room.messages().count("Gas sensor alert active.") == 1
    assert room.messages().count("Gas sensor alert cleared.") == 1
