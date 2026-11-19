"""Pure alarm level, silence and reachability rules."""

import pytest

from alarm import AlarmTracker, command_line, wanted_level

TEMP = ("temp_c", "high", 10.0)
HUMIDITY = ("humidity_pct", "low", 12.0)


def tracker():
    return AlarmTracker(2, id_prefix="run")


def step(alarm, now, *, keys=(), fault=False, connected=True, reply=None, ok=True):
    """One publish: update, then record the send the caller would make."""
    level = alarm.update(alert_keys=list(keys), fault_active=fault, connected=connected,
                         reply=reply, now=now)
    if level is not None:
        alarm.sent(level, ok, now, None if ok else "write timeout")
    return level


def test_level_rules_never_sound_the_buzzer_without_the_led():
    assert wanted_level(unsilenced=False, silenced=False, fault=False) == 0
    assert wanted_level(unsilenced=False, silenced=False, fault=True) == 1
    assert wanted_level(unsilenced=False, silenced=True, fault=False) == 1
    assert wanted_level(unsilenced=True, silenced=True, fault=True) == 2
    assert command_line(2) == "ALARM,2\n"
    with pytest.raises(ValueError):
        command_line(3)


def test_faults_light_the_led_silently_and_limit_alerts_sound():
    alarm = tracker()
    assert step(alarm, 0, fault=True) == 1
    assert step(alarm, 1, fault=True, keys=[TEMP]) == 2
    assert alarm.block(1)["wanted_level"] == 2
    assert step(alarm, 2) == 0


def test_commands_are_sent_on_change_and_after_each_fault_check_only():
    alarm = tracker()
    assert step(alarm, 0) == 0
    assert step(alarm, 1, reply=(0, 0.5)) is None
    assert step(alarm, 2) is None
    alarm.fault_check()
    assert step(alarm, 5) == 0
    assert step(alarm, 6) is None
    assert alarm.block(6)["state"] == "confirmed"


def test_matching_reply_confirms_and_logs_once():
    alarm = tracker()
    step(alarm, 0, keys=[TEMP])
    assert alarm.block(0)["state"] == "pending"
    step(alarm, 1, keys=[TEMP], reply=(2, 0.5))
    block = alarm.block(1.5)
    assert block["state"] == "confirmed" and block["confirmed_level"] == 2
    assert block["requested_level"] == 2 and block["confirmation_age_s"] == 1.0
    alarm.fault_check()
    step(alarm, 5, keys=[TEMP])
    step(alarm, 5.1, keys=[TEMP], reply=(2, 5.05))
    assert [kind for kind, _ in alarm.take_events()] == ["alarm_confirmed"]
    assert alarm.take_events() == []


def test_board_reset_reply_is_corrected_at_once():
    alarm = tracker()
    step(alarm, 0, keys=[TEMP])
    step(alarm, 1, keys=[TEMP], reply=(2, 0.5))
    assert step(alarm, 9, keys=[TEMP], reply=(0, 8.9)) == 2
    assert alarm.block(9)["state"] == "pending"
    assert alarm.block(9)["confirmed_level"] == 0


def test_silent_board_becomes_unreachable_after_the_timeout_and_logs_once():
    alarm = tracker()
    step(alarm, 0, keys=[TEMP])
    step(alarm, 1.9, keys=[TEMP])
    assert alarm.block(1.9)["state"] == "pending"
    step(alarm, 2.1, keys=[TEMP])
    assert alarm.block(2.1)["state"] == "unreachable"
    assert alarm.block(2.1)["reason"] == "no_confirmation"
    for now in (5, 10, 15):
        alarm.fault_check()
        assert step(alarm, now, keys=[TEMP]) == 2
        assert alarm.block(now)["state"] == "unreachable"
    assert [kind for kind, _ in alarm.take_events()] == ["alarm_unreachable"]
    step(alarm, 16, keys=[TEMP], reply=(2, 15.5))
    assert alarm.block(16)["state"] == "confirmed"
    assert [kind for kind, _ in alarm.take_events()] == ["alarm_confirmed"]


def test_failed_send_is_retried_at_the_next_fault_check_not_every_publish():
    alarm = tracker()
    assert step(alarm, 0, keys=[TEMP], ok=False) == 2
    block = alarm.block(0)
    assert block["state"] == "unreachable" and block["reason"] == "send_failed"
    assert block["requested_level"] is None and block["send_error"] == "write timeout"
    assert step(alarm, 1, keys=[TEMP], ok=False) is None
    alarm.fault_check()
    assert step(alarm, 5, keys=[TEMP], ok=False) == 2
    assert step(alarm, 6, keys=[TEMP], fault=False, ok=False) is None
    assert step(alarm, 7, ok=False) == 0
    assert [kind for kind, _ in alarm.take_events()] == ["alarm_unreachable"]


def test_disconnected_port_sends_nothing_and_resends_on_reconnect():
    alarm = tracker()
    step(alarm, 0, keys=[TEMP])
    step(alarm, 1, keys=[TEMP], reply=(2, 0.5))
    assert step(alarm, 2, keys=[TEMP], connected=False) is None
    block = alarm.block(2)
    assert block["state"] == "unreachable" and block["reason"] == "not_connected"
    assert step(alarm, 3, keys=[TEMP], connected=False) is None
    assert step(alarm, 4, keys=[TEMP]) == 2
    assert alarm.block(4)["state"] == "pending"
    assert [kind for kind, _ in alarm.take_events()] == ["alarm_confirmed", "alarm_unreachable"]


def test_silence_covers_the_alerts_shown_and_a_new_alert_sounds_again():
    alarm = tracker()
    step(alarm, 0, keys=[TEMP])
    token = alarm.block(0)["silence_token"]
    assert token
    assert alarm.silence("other", 100) == []
    assert alarm.silence(token, 100) == [TEMP]
    assert step(alarm, 1, keys=[TEMP]) == 1
    block = alarm.block(1)
    assert block["silenced"] and block["silenced_at"] == 100 and block["silence_token"] is None
    assert alarm.silence(token, 101) == []
    assert step(alarm, 2, keys=[TEMP, HUMIDITY]) == 2
    assert alarm.block(2)["silence_token"] != token
    assert step(alarm, 3, keys=[TEMP]) == 1


def test_same_measurement_alerting_again_is_not_silenced():
    alarm = tracker()
    step(alarm, 0, keys=[TEMP])
    alarm.silence(alarm.block(0)["silence_token"], 100)
    assert step(alarm, 1, keys=[TEMP]) == 1
    assert step(alarm, 2) == 0
    block = alarm.block(2)
    assert not block["silenced"] and block["silenced_at"] is None
    assert step(alarm, 3, keys=[("temp_c", "high", 3.0)]) == 2


def test_silence_tokens_differ_between_trackers():
    first, second = AlarmTracker(2), AlarmTracker(2)
    first.update(alert_keys=[TEMP], fault_active=False, connected=True, reply=None, now=0)
    second.update(alert_keys=[TEMP], fault_active=False, connected=True, reply=None, now=0)
    assert first.block(0)["silence_token"] != second.block(0)["silence_token"]


def test_initial_block_before_any_update():
    block = tracker().block(0)
    assert block == {"wanted_level": 0, "requested_level": None, "confirmed_level": None,
                     "state": "pending", "reason": None, "silenced": False, "silenced_at": None,
                     "silence_token": None, "confirmation_age_s": None, "send_error": None}
