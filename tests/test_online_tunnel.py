import io
import queue
import subprocess
import time

import pytest

from online_tunnel import BoundedLog, Tunnel, failure_detail, find_url, tunnel_command

SAMPLE = """2026-11-19T10:00:00Z INF Thank you for trying Cloudflare Tunnel. Doing so, without a Cloudflare account, is a quick way to experiment and try it out.
2026-11-19T10:00:00Z INF Requesting new quick Tunnel on trycloudflare.com...
2026-11-19T10:00:01Z INF +--------------------------------------------------------------------------------------------+
2026-11-19T10:00:01Z INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2026-11-19T10:00:01Z INF |  https://quiet-river-sample-words.trycloudflare.com                                        |
2026-11-19T10:00:01Z INF +--------------------------------------------------------------------------------------------+
2026-11-19T10:00:02Z INF Registered tunnel connection connIndex=0 location=fra08 protocol=quic
"""
URL = "https://quiet-river-sample-words.trycloudflare.com"


def test_link_is_found_in_cloudflared_output():
    found = [find_url(line) for line in SAMPLE.splitlines()]
    assert [url for url in found if url] == [URL]


@pytest.mark.parametrize("line", ["Requesting new quick Tunnel on trycloudflare.com...",
                                  "error from https://api.trycloudflare.com/tunnel", "https://example.com",
                                  "https://evil.trycloudflare.com.example.net/x"])
def test_other_addresses_are_not_taken_for_the_link(line):
    assert find_url(line) is None


def test_commands_use_a_local_origin_and_no_shell():
    assert tunnel_command("cloudflared", 5001) == [
        "cloudflared", "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:5001"]
    assert tunnel_command("/opt/cloudflared", 5002, "room") == [
        "/opt/cloudflared", "tunnel", "--no-autoupdate", "run", "--url", "http://127.0.0.1:5002", "room"]


class FakeProcess:
    """Output lines are fed through a queue; the process ends at None or on terminate."""

    def __init__(self, lines=(), code=1, wait_for_terminate=False):
        self.lines = queue.Queue()
        for line in lines:
            self.lines.put(line + "\n")
        if not wait_for_terminate:
            self.lines.put(None)
        self.code, self.returncode, self.terminated = code, None, False
        self.stdout = iter(self._read, None)

    def _read(self):
        return self.lines.get()

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.lines.put(None)

    def kill(self):
        self.terminate()

    def wait(self, timeout=None):
        self.returncode = -15 if self.terminated else self.code
        return self.returncode


def wait_for(tunnel, state, timeout=2):
    deadline = time.monotonic() + timeout
    while tunnel.state()["state"] != state:
        assert time.monotonic() < deadline, tunnel.state()
        time.sleep(0.005)
    return tunnel.state()


def make(processes, waited=None, **options):
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return processes.pop(0)
    changes = []
    waited = [] if waited is None else waited

    def wait(seconds):  # no real waiting; records the backoff
        waited.append(seconds)
        return False
    tunnel = Tunnel(["cloudflared", "tunnel"], popen=popen, which=lambda name: "/usr/bin/" + name,
                    wait=wait, clock=lambda: 100.0, on_change=changes.append, **options)
    return tunnel, calls, changes


OFF = {"state": "off", "url": None, "reason": None, "attempt": None, "attempts": 6, "retry_in_s": None}


def test_tunnel_goes_from_off_to_starting_to_active_and_back_to_off():
    process = FakeProcess(SAMPLE.splitlines(), wait_for_terminate=True)
    tunnel, calls, changes = make([process])
    assert tunnel.state() == OFF
    tunnel.start()
    assert wait_for(tunnel, "active") == {**OFF, "state": "active", "url": URL, "attempt": 1}
    command, kwargs = calls[0]
    assert command == ["cloudflared", "tunnel"] and not kwargs.get("shell")
    assert kwargs["stdout"] == subprocess.PIPE and kwargs["stderr"] == subprocess.STDOUT
    tunnel.stop()
    assert process.terminated
    assert tunnel.state() == OFF
    assert [change["state"] for change in changes] == ["starting", "active", "off"]


def test_missing_binary_fails_without_starting_anything():
    tunnel = Tunnel(["cloudflared", "tunnel"], popen=pytest.fail, which=lambda name: None)
    tunnel.start()
    assert tunnel.state() == {**OFF, "state": "failed", "reason": "cloudflared not found"}
    tunnel.stop()


RATE_LIMITED = ["2026-11-19T10:00:00Z INF Requesting new quick Tunnel on trycloudflare.com...",
                "2026/11/19 10:00:00 failed to sufficiently increase receive buffer size (was: 208 kiB)",
                "2026-11-19T10:00:01Z ERR Error unmarshaling QuickTunnel response: error=\"429 Too Many Requests\"",
                "failed to request quick Tunnel: 429 Too Many Requests"]


def test_a_child_that_keeps_exiting_is_retried_with_backoff_then_fails_with_its_error():
    processes = [FakeProcess(RATE_LIMITED, code=1) for _ in range(6)]
    waited = []
    tunnel, calls, changes = make(processes, waited)
    tunnel.start()
    state = wait_for(tunnel, "failed")
    assert len(calls) == 6 and waited == [5, 10, 20, 40, 60]
    assert state == {**OFF, "state": "failed", "attempt": 6, "reason": (
        'cloudflared stopped (exit code 1): Error unmarshaling QuickTunnel response: error="429 Too Many Requests"')}
    retries = [(c["attempt"], c["retry_in_s"]) for c in changes if c["retry_in_s"] is not None]
    assert retries == [(2, 5), (3, 10), (4, 20), (5, 40), (6, 60)]
    assert all(c["reason"].startswith("cloudflared stopped (exit code 1): ") for c in changes if c["retry_in_s"])


def test_retry_waits_and_attempts_follow_the_setting():
    processes = [FakeProcess(["x"], code=2) for _ in range(3)]
    waited = []
    tunnel, calls, _ = make(processes, waited, waits=(1, 2))
    tunnel.start()
    assert wait_for(tunnel, "failed")["attempts"] == 3
    assert len(calls) == 3 and waited == [1, 2]


def test_a_later_attempt_can_succeed():
    processes = [FakeProcess(RATE_LIMITED, code=1), FakeProcess(RATE_LIMITED, code=1),
                 FakeProcess(SAMPLE.splitlines(), wait_for_terminate=True)]
    waited = []
    tunnel, calls, _ = make(processes, waited)
    tunnel.start()
    state = wait_for(tunnel, "active")
    assert state["url"] == URL and state["reason"] is None and state["attempt"] == 3
    assert waited == [5, 10]
    tunnel.stop()


def test_waiting_state_counts_down_to_the_next_attempt():
    now = [100.0]
    tunnel = Tunnel(["cloudflared"], clock=lambda: now[0])
    tunnel._set("starting", reason="cloudflared stopped (exit code 1)", attempt=3, wait_s=20)
    assert tunnel.state()["retry_in_s"] == 20
    now[0] = 112.5
    assert tunnel.state()["retry_in_s"] == 8
    now[0] = 130
    assert tunnel.state()["retry_in_s"] == 0


@pytest.mark.parametrize("lines, detail", [
    (RATE_LIMITED, 'Error unmarshaling QuickTunnel response: error="429 Too Many Requests"'),
    (["INF Requesting", "failed to request quick Tunnel: 429 Too Many Requests"],
     "failed to request quick Tunnel: 429 Too Many Requests"),
    (["2026/11/19 19:25:28 failed to sufficiently increase receive buffer size"], None),
    (["2026-11-19T10:00:00Z INF all good"], None),
    (["2026-11-19T10:00:00Z ERR lost link to " + URL + " now"], "lost link to <link> now"),
    (["2026-11-19T10:00:00Z ERR " + "x" * 400], "x" * 157 + "..."),
])
def test_failure_detail_picks_the_last_error_line_without_stamp_or_link(lines, detail):
    assert failure_detail(lines) == detail


def test_cloudflared_output_is_kept_in_a_bounded_log_and_in_memory(tmp_path):
    log_path = tmp_path / "logs" / "cloudflared.log"
    lines = [f"2026-11-19T10:00:00Z INF line {n:03d}" for n in range(200)]
    tunnel, _, _ = make([FakeProcess(lines + RATE_LIMITED, code=1)], waits=(),
                        log=BoundedLog(log_path, max_bytes=2000))
    tunnel.start()
    wait_for(tunnel, "failed")
    old = log_path.with_name("cloudflared.log.1")
    assert log_path.stat().st_size <= 2000 and old.stat().st_size <= 2000
    written = log_path.read_text().splitlines()
    assert written[-2:] == [RATE_LIMITED[-1], "--- " + tunnel.state()["reason"]]
    assert "line 199" in log_path.read_text() + old.read_text()
    tail = tunnel.tail()
    assert len(tail) == 20 and tail[-1] == RATE_LIMITED[-1]


def test_an_unwritable_log_does_not_stop_the_tunnel(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("")
    tunnel, _, _ = make([FakeProcess(SAMPLE.splitlines(), wait_for_terminate=True)],
                        log=BoundedLog(blocker / "cloudflared.log"))
    tunnel.start()
    assert wait_for(tunnel, "active")["url"] == URL
    tunnel.stop()


def test_a_failed_tunnel_can_be_started_again():
    processes = [FakeProcess(["ERR boom"], code=1), FakeProcess(SAMPLE.splitlines(), wait_for_terminate=True)]
    tunnel, calls, _ = make(processes, waits=())
    tunnel.start()
    assert wait_for(tunnel, "failed")["reason"] == "cloudflared stopped (exit code 1): boom"
    tunnel.start()
    assert wait_for(tunnel, "active")["url"] == URL
    tunnel.stop()


def test_a_dropped_tunnel_restarts_with_backoff_and_reports_its_new_link():
    first = FakeProcess(SAMPLE.splitlines() + ["2026-11-19T10:05:00Z ERR connection lost"], code=1)
    second = FakeProcess([SAMPLE.replace("quiet-river", "other-hill")], wait_for_terminate=True)
    waited = []
    tunnel, calls, changes = make([first, second], waited)
    tunnel.start()
    deadline = time.monotonic() + 2
    while tunnel.state()["url"] != URL.replace("quiet-river", "other-hill"):
        assert time.monotonic() < deadline, tunnel.state()
        time.sleep(0.005)
    assert waited == [5]
    assert {"state": "starting", "url": None, "reason": "cloudflared stopped (exit code 1): connection lost",
            "attempt": 1, "attempts": 6, "retry_in_s": 5} in changes
    tunnel.stop()
    assert second.terminated


def test_a_program_that_cannot_start_fails_with_a_reason():
    def popen(command, **kwargs):
        raise PermissionError(13, "Permission denied")
    tunnel = Tunnel(["cloudflared"], popen=popen, which=lambda name: name)
    tunnel.start()
    assert wait_for(tunnel, "failed")["reason"] == "could not start cloudflared (Permission denied)"


def test_named_tunnel_is_active_with_its_configured_address_once_connected():
    process = FakeProcess(["INF Starting tunnel", "INF Registered tunnel connection connIndex=0"],
                          wait_for_terminate=True)
    tunnel, _, _ = make([process], public_url="https://room.example.org")
    tunnel.start()
    assert wait_for(tunnel, "active")["url"] == "https://room.example.org"
    tunnel.stop()
