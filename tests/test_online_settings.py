from pathlib import Path

import pytest

from settings import ONLINE_DEFAULTS, load_online_settings, validate_runtime_settings

BASE = "fault_check_interval_s: 5\nserial_retry_interval_s: 5\nserial_poll_interval_s: 0.05\n"
BASE_DICT = {"fault_check_interval_s": 5, "serial_retry_interval_s": 5, "serial_poll_interval_s": 0.05}


def test_online_defaults_apply_when_keys_are_absent(tmp_path):
    path = tmp_path / "runtime.yaml"
    path.write_text(BASE)
    assert load_online_settings(path) == ONLINE_DEFAULTS
    assert ONLINE_DEFAULTS["online_port"] == 5001
    assert ONLINE_DEFAULTS["cloudflared_path"] == "cloudflared"
    assert ONLINE_DEFAULTS["online_session_hours"] == 8


def test_project_runtime_file_has_the_online_defaults():
    loaded = load_online_settings(Path(__file__).resolve().parents[1] / "config/runtime.yaml")
    assert loaded == ONLINE_DEFAULTS


def test_online_keys_override_defaults(tmp_path):
    path = tmp_path / "runtime.yaml"
    path.write_text(BASE + "online_port: 6001\ncloudflared_path: /opt/cf/cloudflared\nonline_session_hours: 2\n"
                    "cloudflared_tunnel: room\nonline_public_url: https://room.example.org\n")
    loaded = load_online_settings(path)
    assert loaded["online_port"] == 6001 and loaded["cloudflared_path"] == "/opt/cf/cloudflared"
    assert loaded["cloudflared_tunnel"] == "room" and loaded["online_public_url"] == "https://room.example.org"


@pytest.mark.parametrize("extra, message", [
    ({"online_port": 5000}, "online_port"), ({"online_port": 80}, "online_port"),
    ({"online_port": 70000}, "online_port"), ({"online_port": "5001"}, "online_port"),
    ({"online_port": True}, "online_port"), ({"cloudflared_path": ""}, "cloudflared_path"),
    ({"cloudflared_path": 5}, "cloudflared_path"), ({"online_session_hours": 0}, "online_session_hours"),
    ({"cloudflared_tunnel": "room"}, "online_public_url"),
    ({"cloudflared_tunnel": "room", "online_public_url": "http://room.example.org"}, "online_public_url"),
    ({"cloudflared_tunnel": ""}, "cloudflared_tunnel"),
    ({"online_retry_waits_s": 5}, "online_retry_waits_s"), ({"online_retry_waits_s": [5, 0]}, "online_retry_waits_s"),
    ({"online_retry_waits_s": [5, True]}, "online_retry_waits_s"),
    ({"online_retry_waits_s": [5, "10"]}, "online_retry_waits_s"),
    ({"online_retry_waits_s": [5, 3601]}, "online_retry_waits_s"),
    ({"online_retry_waits_s": [1] * 21}, "online_retry_waits_s"),
    ({"cloudflared_log": ""}, "cloudflared_log"), ({"cloudflared_log": 3}, "cloudflared_log"),
])
def test_invalid_online_settings_are_refused(extra, message):
    with pytest.raises(ValueError, match=message):
        validate_runtime_settings({**BASE_DICT, **extra})


def test_retry_waits_default_to_six_attempts_and_may_be_empty(tmp_path):
    assert ONLINE_DEFAULTS["online_retry_waits_s"] == [5, 10, 20, 40, 60]
    assert ONLINE_DEFAULTS["cloudflared_log"] == "logs/cloudflared.log"
    validate_runtime_settings({**BASE_DICT, "online_retry_waits_s": []})
    validate_runtime_settings({**BASE_DICT, "online_retry_waits_s": [0.5, 3600]})


def test_the_default_cloudflared_log_is_ignored_by_git():
    ignored = (Path(__file__).resolve().parents[1] / ".gitignore").read_text().splitlines()
    assert "/logs/" in ignored
