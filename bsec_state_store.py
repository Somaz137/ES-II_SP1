"""Keep the board's Bosch BSEC calibration state in a file next to the database.

The board sends its state when IAQ accuracy is 3 and asks for it at start.
The host stores it, answers each request with exactly one BSEC_STATE line,
and records what happened as events and a status block.
"""

from datetime import datetime
import json
import math
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

# Bsec2::getState does not report the length, so the board sends all
# BSEC_MAX_STATE_BLOB_SIZE (238) bytes: 476 hex characters.
STATE_HEX_MAX = 476
_HEX = re.compile(r"[0-9a-fA-F]+")
# major.minor.major_bugfix.minor_bugfix, compared as text on both sides.
_VERSION = re.compile(r"\d{1,3}(\.\d{1,3}){3}")
NONE_LINE = "BSEC_STATE,NONE"


class DamagedStateFile(ValueError):
    """The state file exists but cannot be used."""


def is_state_hex(text):
    return (isinstance(text, str) and 2 <= len(text) <= STATE_HEX_MAX and len(text) % 2 == 0
            and _HEX.fullmatch(text) is not None)


def is_bsec_version(text):
    return isinstance(text, str) and _VERSION.fullmatch(text) is not None


def is_accuracy(value):
    return type(value) is int and 0 <= value <= 3


def state_path(db_path):
    """room.sqlite3 gives room.bsec_state.json in the same folder."""
    return Path(db_path).with_suffix(".bsec_state.json")


def save_state(path, *, state_hex, bsec_version, accuracy, saved_at):
    """Write a temporary file in the same folder, then rename it over the old one."""
    if not is_state_hex(state_hex) or not is_bsec_version(bsec_version) or not is_accuracy(accuracy):
        raise ValueError("Not a valid BSEC state.")
    path = Path(path)
    content = json.dumps({"saved_at": saved_at, "bsec_version": bsec_version,
                          "accuracy": accuracy, "state": state_hex.lower()}, allow_nan=False)
    temp_path = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                prefix=path.name + ".", suffix=".tmp", delete=False) as temp:
            temp_path = Path(temp.name)
            temp.write(content + "\n")
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def load_state(path):
    """The saved state, or None when there is no file. DamagedStateFile when unusable."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as error:
        raise DamagedStateFile(str(error)) from error
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError) as error:
        raise DamagedStateFile("not JSON") from error
    if not isinstance(data, dict):
        raise DamagedStateFile("not a JSON object")
    saved_at = data.get("saved_at")
    if (type(saved_at) not in (int, float) or not math.isfinite(saved_at)
            or not is_bsec_version(data.get("bsec_version")) or not is_accuracy(data.get("accuracy"))
            or not is_state_hex(data.get("state"))):
        raise DamagedStateFile("missing or invalid fields")
    return {"saved_at": saved_at, "bsec_version": data["bsec_version"],
            "accuracy": data["accuracy"], "state": data["state"].lower()}


def iso_time(wall):
    return datetime.fromtimestamp(wall).astimezone().isoformat(timespec="seconds")


def reply_for(path, bsec_version):
    """(line, reason) for one board request; the line has no newline."""
    try:
        saved = load_state(path)
    except DamagedStateFile:
        return NONE_LINE, "file damaged"
    if saved is None:
        return NONE_LINE, "no saved state"
    if saved["bsec_version"] != bsec_version:
        return NONE_LINE, f"version mismatch (file {saved['bsec_version']}, board {bsec_version})"
    return f"BSEC_STATE,{saved['state']}", f"restored from {iso_time(saved['saved_at'])}"


class BsecStateKeeper:
    """The monitor's side: reply to requests, save state lines, report results.

    handle() runs on each published monitoring state. The state carries
    counts, so a request that arrived before the first publish, or two
    requests in one poll, each get exactly one reply.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.requests = self.states = self.restores = self.save_failures = 0
        self.last_request_at = self.last_reply_reason = self.last_restore_ok = None
        try:
            saved = load_state(self.path)
        except DamagedStateFile:
            saved = None
        self.saved_at = None if saved is None else saved["saved_at"]
        self.accuracy = None if saved is None else saved["accuracy"]

    def handle(self, state, now, wall, transport):
        """Return events as (kind, message); never raises for file or write problems."""
        def wall_at(received_at):
            return wall - (now - received_at)

        events = []
        request = state.bsec_request
        if request is not None and request.count > self.requests:
            for _ in range(request.count - self.requests):
                events.append(self.reply(request.bsec_version, transport))
            self.requests = request.count
            self.last_request_at = wall_at(request.received_at)
        report = state.bsec_state
        if report is not None and report.count > self.states:
            self.states = report.count
            events.append(self.save(report, wall_at(report.received_at)))
        restored = state.bsec_restored
        if restored is not None and restored.count > self.restores:
            self.restores = restored.count
            self.last_restore_ok = restored.ok
            events.append(("bsec_state_restored", "The board restored the saved Bosch calibration.")
                          if restored.ok else
                          ("bsec_state_restore_failed", "The board did not accept the saved Bosch "
                           "calibration. The Bosch calibration starts again."))
        failed = state.bsec_save_failed
        if failed is not None and failed.count > self.save_failures:
            self.save_failures = failed.count
            events.append(("bsec_state_save_failed", "The board could not read its Bosch "
                           "calibration state to save it. The board tries again."))
        return events

    def reply(self, bsec_version, transport):
        line, reason = reply_for(self.path, bsec_version)
        self.last_reply_reason = reason
        error = None
        if transport is None:
            error = "no connection to the board"
        else:
            try:
                if transport.send(line + "\n") is not True:
                    error = getattr(transport, "last_send_error", None) or "the write failed"
            except Exception as failure:  # noqa: BLE001 - a reply must not stop the monitor
                error = str(failure) or type(failure).__name__
        if error is not None:
            return ("bsec_state_not_sent", f"Board asked for the Bosch calibration "
                    f"(BSEC {bsec_version}). The reply was not sent: {error}. Reply was: {reason}.")
        if line == NONE_LINE:
            return ("bsec_state_not_sent", f"Board asked for the Bosch calibration "
                    f"(BSEC {bsec_version}). No state sent: {reason}.")
        return ("bsec_state_sent", f"Board asked for the Bosch calibration "
                f"(BSEC {bsec_version}). State sent, {reason}.")

    def save(self, report, saved_at):
        try:
            save_state(self.path, state_hex=report.state_hex, bsec_version=report.bsec_version,
                       accuracy=report.accuracy, saved_at=saved_at)
        except (OSError, ValueError) as error:
            return ("bsec_state_save_failed",
                    f"The host could not write the Bosch calibration file: {error}.")
        self.saved_at, self.accuracy = saved_at, report.accuracy
        return ("bsec_state_saved", f"Bosch calibration saved (accuracy {report.accuracy}, "
                f"BSEC {report.bsec_version}).")

    def block(self):
        return {"saved_at": self.saved_at, "accuracy": self.accuracy,
                "last_request_at": self.last_request_at,
                "last_reply_reason": self.last_reply_reason,
                "last_restore_ok": self.last_restore_ok}
