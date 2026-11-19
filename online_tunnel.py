"""Start and watch the cloudflared tunnel that publishes the online dashboard origin."""
import re
import shutil
import subprocess
import threading

# A quick-tunnel link; the trycloudflare.com API host is not a link.
QUICK_URL = re.compile(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com(?![\w.-])")
CONNECTED = "Registered tunnel connection"


def find_url(line):
    match = QUICK_URL.search(line)
    return match.group(0) if match else None


def tunnel_command(binary, port, name=None):
    """Argument list (no shell). A quick tunnel unless a named tunnel is configured."""
    origin = f"http://127.0.0.1:{port}"
    if name:
        return [binary, "tunnel", "--no-autoupdate", "run", "--url", origin, name]
    return [binary, "tunnel", "--no-autoupdate", "--url", origin]


class Tunnel:
    """State: off, starting, active (with url) or failed (with reason).

    A child that exits on its own is started again at most `retries` times.
    `public_url` is set for a named tunnel; a quick tunnel reads its link from the output.
    """

    def __init__(self, command, *, public_url=None, retries=2, retry_delay_s=5,
                 popen=subprocess.Popen, which=shutil.which, on_change=None):
        self.command, self.public_url = list(command), public_url
        self.retries, self.retry_delay_s = retries, retry_delay_s
        self.popen, self.which, self.on_change = popen, which, on_change
        self._lock = threading.Lock()
        self._state = {"state": "off", "url": None, "reason": None}
        self._process = None
        self._thread = None
        self._stopping = threading.Event()

    def state(self):
        with self._lock:
            return dict(self._state)

    def _set(self, state, url=None, reason=None):
        new = {"state": state, "url": url, "reason": reason}
        with self._lock:
            if new == self._state:
                return
            self._state = new
        if self.on_change:
            self.on_change(dict(new))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        if self.which(self.command[0]) is None:
            self._set("failed", reason="cloudflared not found")
            return
        self._stopping.clear()
        self._set("starting")
        self._thread = threading.Thread(target=self._run, name="online-tunnel", daemon=True)
        self._thread.start()

    def _run(self):
        attempts = 0
        while not self._stopping.is_set():
            try:
                process = self.popen(self.command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, bufsize=1)
            except OSError as error:
                self._set("failed", reason=f"could not start cloudflared ({error.strerror or error})")
                return
            with self._lock:
                self._process = process
            if self._stopping.is_set():
                process.terminate()
            for line in process.stdout:
                url = self.public_url if self.public_url and CONNECTED in line else (
                    None if self.public_url else find_url(line))
                if url:
                    self._set("active", url=url)
            code = process.wait()
            if self._stopping.is_set():
                return
            attempts += 1
            reason = f"cloudflared stopped (exit code {code})"
            if attempts > self.retries:
                self._set("failed", reason=reason)
                return
            self._set("starting", reason=reason + ", starting again")
            if self._stopping.wait(self.retry_delay_s):
                return

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
