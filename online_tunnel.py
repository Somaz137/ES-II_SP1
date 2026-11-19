"""Start and watch the cloudflared tunnel that publishes the online dashboard origin."""
from collections import deque
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

# A quick-tunnel link; the trycloudflare.com API host is not a link.
QUICK_URL = re.compile(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com(?![\w.-])")
CONNECTED = "Registered tunnel connection"
# Waits before attempts 2, 3, ...; one more attempt than waits (settings: online_retry_waits_s).
DEFAULT_WAITS_S = (5, 10, 20, 40, 60)
TAIL_LINES = 20
REASON_MAX = 160
_STAMP = re.compile(r"^(\d{4}-\d\d-\d\dT\S+|\d{4}/\d\d/\d\d \d\d:\d\d:\d\d)\s+")
_LEVEL = re.compile(r"^(DBG|INF|WRN|ERR|FTL)\s+")
# quic-go prints this on most hosts; it is not why cloudflared stops.
_HARMLESS = ("receive buffer size",)


def find_url(line):
    match = QUICK_URL.search(line)
    return match.group(0) if match else None


def failure_detail(lines):
    """The last ERR/FTL line, else the last line naming an error, without time stamp or link."""
    levelled, worded = None, None
    for line in lines:
        body = _STAMP.sub("", line.strip())
        if body.startswith(("ERR ", "FTL ")):
            levelled = body
        elif re.search(r"error|failed", body, re.I) and not any(text in body for text in _HARMLESS):
            worded = body
    chosen = levelled or worded
    if chosen is None:
        return None
    text = QUICK_URL.sub("<link>", _LEVEL.sub("", chosen)).strip()
    return text if len(text) <= REASON_MAX else text[:REASON_MAX - 3] + "..."


class BoundedLog:
    """Appends lines to a file; past `max_bytes` the file moves to `<name>.1` (one old file kept)."""

    def __init__(self, path, max_bytes=256 * 1024):
        self.path, self.max_bytes = Path(path), max_bytes
        self.old = self.path.with_name(self.path.name + ".1")

    def write(self, line):
        data = (line.rstrip("\n") + "\n").encode("utf-8", "replace")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            size = 0
        if size and size + len(data) > self.max_bytes:
            os.replace(self.path, self.old)
        with self.path.open("ab") as file:
            file.write(data[:self.max_bytes])


def tunnel_command(binary, port, name=None):
    """Argument list (no shell). A quick tunnel unless a named tunnel is configured."""
    origin = f"http://127.0.0.1:{port}"
    if name:
        return [binary, "tunnel", "--no-autoupdate", "run", "--url", origin, name]
    return [binary, "tunnel", "--no-autoupdate", "--url", origin]


class Tunnel:
    """State: off, starting, active (with url) or failed (with reason).

    A child that exits is started again after each of `waits` in turn (len(waits) + 1 attempts);
    a child that had its link and then stopped starts again from attempt 1 after the first wait.
    The reason names the last error line cloudflared printed. Every output line goes to `log`
    (a BoundedLog, optional) and the last TAIL_LINES stay in memory (`tail()`).
    `public_url` is set for a named tunnel; a quick tunnel reads its link from the output.
    """

    def __init__(self, command, *, public_url=None, waits=DEFAULT_WAITS_S, log=None, wait=None,
                 clock=time.monotonic, popen=subprocess.Popen, which=shutil.which, on_change=None):
        self.command, self.public_url = list(command), public_url
        self.waits, self.attempts = tuple(waits), len(waits) + 1
        self.log, self.clock = log, clock
        self.popen, self.which, self.on_change = popen, which, on_change
        self._lock = threading.Lock()
        self._state = {"state": "off", "url": None, "reason": None, "attempt": None, "wait_s": None}
        self._retry_at = None
        self._tail = deque(maxlen=TAIL_LINES)
        self._process = None
        self._thread = None
        self._stopping = threading.Event()
        self.wait = wait or self._stopping.wait  # returns True when stop() was called

    def _public(self, state, retry_in_s):
        return {"state": state["state"], "url": state["url"], "reason": state["reason"],
                "attempt": state["attempt"], "attempts": self.attempts, "retry_in_s": retry_in_s}

    def state(self):
        with self._lock:
            state, retry_at = dict(self._state), self._retry_at
        retry_in_s = None if retry_at is None else max(0, math.ceil(retry_at - self.clock()))
        return self._public(state, retry_in_s)

    def tail(self):
        with self._lock:
            return list(self._tail)

    def _set(self, state, url=None, reason=None, attempt=None, wait_s=None):
        new = {"state": state, "url": url, "reason": reason, "attempt": attempt, "wait_s": wait_s}
        with self._lock:
            if new == self._state:
                return
            self._state = new
            self._retry_at = None if wait_s is None else self.clock() + wait_s
        if self.on_change:
            self.on_change(self._public(new, wait_s))

    def _write_log(self, line):
        if self.log is None:
            return
        try:
            self.log.write(line)
        except OSError:
            self.log = None  # an unwritable log must not stop online access

    def start(self):
        """Start, or start again after failed or off; nothing happens while running."""
        if self._thread and self._thread.is_alive():
            return
        if self.which(self.command[0]) is None:
            self._set("failed", reason="cloudflared not found")
            return
        self._stopping.clear()
        self._set("starting", attempt=1)
        self._thread = threading.Thread(target=self._run, name="online-tunnel", daemon=True)
        self._thread.start()

    def _run(self):
        attempt, wait_s, reason = 1, 0, None
        while True:
            if wait_s:
                self._set("starting", reason=reason, attempt=attempt, wait_s=wait_s)
                if self.wait(wait_s):
                    return
            if self._stopping.is_set():
                return
            self._set("starting", reason=reason, attempt=attempt)
            self._write_log(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} attempt {attempt} of {self.attempts}: "
                            + " ".join(self.command))
            try:
                process = self.popen(self.command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
            except OSError as error:
                self._set("failed", reason=f"could not start cloudflared ({error.strerror or error})",
                          attempt=attempt)
                return
            lines = deque(maxlen=TAIL_LINES)
            with self._lock:
                self._process, self._tail = process, lines
            if self._stopping.is_set():
                process.terminate()
            became_active = False
            for line in process.stdout:
                self._write_log(line)
                with self._lock:
                    lines.append(line.rstrip("\n"))
                url = self.public_url if self.public_url and CONNECTED in line else (
                    None if self.public_url else find_url(line))
                if url:
                    became_active = True
                    self._set("active", url=url, attempt=attempt)
            code = process.wait()
            if self._stopping.is_set():
                return
            detail = failure_detail(list(lines))
            reason = f"cloudflared stopped (exit code {code})" + (f": {detail}" if detail else "")
            self._write_log(f"--- {reason}")
            if became_active and self.waits:
                attempt, wait_s = 1, self.waits[0]
            elif attempt >= self.attempts:
                self._set("failed", reason=reason, attempt=attempt)
                return
            else:
                attempt, wait_s = attempt + 1, self.waits[attempt - 1]

    def stop(self):
        """Terminate the child (kill after 5 s) and show the state as off."""
        self._stopping.set()
        with self._lock:
            process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if self._thread is not None:
            self._thread.join(timeout=5)
        if self.state()["state"] != "off":
            self._set("off")
