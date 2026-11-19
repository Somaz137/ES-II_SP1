import io
import queue
import subprocess
import time

import pytest

from online_tunnel import Tunnel, find_url, tunnel_command

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


def make(processes, **options):
    calls = []

    def popen(command, **kwargs):
        calls.append((command, kwargs))
        return processes.pop(0)
    changes = []
    tunnel = Tunnel(["cloudflared", "tunnel"], popen=popen, which=lambda name: "/usr/bin/" + name,
                    retry_delay_s=0, on_change=changes.append, **options)
    return tunnel, calls, changes


def test_tunnel_goes_from_off_to_starting_to_active_and_back_to_off():
    process = FakeProcess(SAMPLE.splitlines(), wait_for_terminate=True)
    tunnel, calls, changes = make([process])
    assert tunnel.state() == {"state": "off", "url": None, "reason": None}
    tunnel.start()
    assert wait_for(tunnel, "active") == {"state": "active", "url": URL, "reason": None}
    command, kwargs = calls[0]
    assert command == ["cloudflared", "tunnel"] and not kwargs.get("shell")
    assert kwargs["stdout"] == subprocess.PIPE and kwargs["stderr"] == subprocess.STDOUT
    tunnel.stop()
    assert process.terminated
    assert tunnel.state() == {"state": "off", "url": None, "reason": None}
    assert [change["state"] for change in changes] == ["starting", "active", "off"]


def test_missing_binary_fails_without_starting_anything():
    tunnel = Tunnel(["cloudflared", "tunnel"], popen=pytest.fail, which=lambda name: None)
    tunnel.start()
    assert tunnel.state() == {"state": "failed", "url": None, "reason": "cloudflared not found"}
    tunnel.stop()


def test_a_child_that_keeps_exiting_is_retried_a_bounded_number_of_times():
    processes = [FakeProcess(["starting"], code=1) for _ in range(3)]
    tunnel, calls, _ = make(processes, retries=2)
    tunnel.start()
    state = wait_for(tunnel, "failed")
    assert len(calls) == 3
    assert state == {"state": "failed", "url": None, "reason": "cloudflared stopped (exit code 1)"}


def test_a_restarted_child_reports_its_new_link():
    first = FakeProcess(SAMPLE.splitlines(), code=1)
    second = FakeProcess([SAMPLE.replace("quiet-river", "other-hill")], wait_for_terminate=True)
    tunnel, calls, _ = make([first, second], retries=2)
    tunnel.start()
    deadline = time.monotonic() + 2
    while tunnel.state()["url"] != URL.replace("quiet-river", "other-hill"):
        assert time.monotonic() < deadline, tunnel.state()
        time.sleep(0.005)
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
