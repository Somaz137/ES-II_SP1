"""Password file, sign-in rate limit and CSRF tokens for the online dashboard origin."""
from collections import deque
import hmac
import os
from pathlib import Path
import secrets
import time

from werkzeug.security import check_password_hash, generate_password_hash

SECRET_FILE = Path(__file__).resolve().parent / "config" / "online_secret.yaml"
PASSWORD_MIN = 10


def write_secret(path, password):
    """Store a password hash and a new session key; the plain password is never written."""
    import yaml

    if len(password) < PASSWORD_MIN:
        raise ValueError(f"Use at least {PASSWORD_MIN} characters.")
    data = {"password_hash": generate_password_hash(password), "secret_key": secrets.token_hex(32)}
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as target:
        target.write("# Online sign-in. Written by dashboard.py --set-password. Do not commit.\n")
        yaml.safe_dump(data, target)
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def read_secret(path):
    """The stored hash and session key, or None when no password is set."""
    import yaml

    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError("The online password file is not valid YAML.") from error
    if (not isinstance(data, dict) or set(data) != {"password_hash", "secret_key"}
            or not all(isinstance(value, str) and value for value in data.values())):
        raise ValueError("The online password file is damaged. Run dashboard.py --set-password again.")
    return data


def check_password(secret, password):
    return check_password_hash(secret["password_hash"], password)


def prompt_password(ask):
    first = ask("New online password: ")
    if ask("Repeat the password: ") != first:
        raise ValueError("The two passwords did not match. Nothing was changed.")
    return first


def new_csrf_token():
    return secrets.token_urlsafe(32)


def tokens_match(expected, given):
    if not isinstance(expected, str) or not isinstance(given, str) or not expected:
        return False
    return hmac.compare_digest(expected.encode(), given.encode())


class LoginLimiter:
    """In-memory sign-in failures: a per-client limit and a total limit in a sliding window."""

    def __init__(self, per_client=5, total=20, window_s=300, clock=time.monotonic):
        self.per_client, self.total, self.window_s, self.clock = per_client, total, window_s, clock
        self.failures = {}
        self.all_failures = deque()

    def _trim(self, times, now):
        while times and times[0] <= now - self.window_s:
            times.popleft()

    def wait_s(self, client):
        """Seconds until this client may try again; 0 when it may try now."""
        now = self.clock()
        times = self.failures.get(client, deque())
        self._trim(times, now)
        self._trim(self.all_failures, now)
        waits = [0]
        if len(times) >= self.per_client:
            waits.append(times[0] + self.window_s - now)
        if len(self.all_failures) >= self.total:
            waits.append(self.all_failures[0] + self.window_s - now)
        return max(waits)

    def failed(self, client):
        now = self.clock()
        if len(self.failures) >= 1000:  # keep memory bounded: forget clients with no recent failure
            self.failures = {key: times for key, times in self.failures.items()
                             if times and times[-1] > now - self.window_s}
        self.failures.setdefault(client, deque()).append(now)
        self.all_failures.append(now)

    def succeeded(self, client):
        self.failures.pop(client, None)
