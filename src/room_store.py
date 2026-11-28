"""SQLite state shared by the monitor and the local dashboard."""
from contextlib import contextmanager
import json
import time
import math
import os
import sqlite3
from pathlib import Path
from tempfile import NamedTemporaryFile
import unicodedata

METRICS = {"temp_c": ("Temperature", "°C"), "humidity_pct": ("Humidity", "%"),
           "pressure_hpa": ("Pressure", "hPa")}
# Estimates checked against system-setup limits (src/config/system.yaml), never patient limits.
SYSTEM_METRICS = {"air_quality": ("Air quality index", ""), "dust_ugm3": ("Dust estimate", "µg/m³")}
LIMITED = {**METRICS, **SYSTEM_METRICS}
# Stored and charted series. Only METRICS accept patient limits. Raw gas resistance and dust
# voltage stay stored as system details; the two estimates are stored only while current.
SERIES = {**METRICS, "gas_ohms": ("Gas resistance", "Ω"), "dust_mv": ("Dust signal", "mV"),
          **SYSTEM_METRICS}
LABEL_MAX = 40
EVENT_LIMIT_MAX = 200
DEFAULT_DB = Path(__file__).resolve().parent / "room.sqlite3"
DEMO_DB = DEFAULT_DB.with_name("room-demo.sqlite3")


def validate_label(label):
    """A short trimmed label such as a bed number. Not a patient name field."""
    if not isinstance(label, str):
        raise ValueError("The profile label must be text.")
    if label != label.strip():
        raise ValueError("The profile label must not start or end with spaces.")
    if len(label) > LABEL_MAX:
        raise ValueError(f"The profile label must be at most {LABEL_MAX} characters.")
    if any(unicodedata.category(char) in ("Cc", "Cf", "Zl", "Zp") for char in label):
        raise ValueError("The profile label must not contain control characters or line breaks.")


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) - {"label"} != {"limits", "hold_s"}:
        raise ValueError("Supply limits and a sustained duration.")
    if "label" in profile:
        validate_label(profile["label"])
    limits = profile["limits"]
    if not isinstance(limits, dict) or not limits.keys() <= METRICS.keys():
        raise ValueError("Choose a supported measurement.")
    for bounds in limits.values():
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError("Enter both limits for each enabled measurement.")
        for value in bounds:
            validate_number(value)
        if bounds[0] >= bounds[1]:
            raise ValueError("The lower limit must be less than the upper limit.")
    validate_number(profile["hold_s"])
    if profile["hold_s"] <= 0:
        raise ValueError("Enter a positive sustained duration.")


def validate_number(value):
    try:
        if type(value) in (int, float) and math.isfinite(value):
            return
    except OverflowError:
        pass
    raise ValueError("Enter finite numbers.")


class RoomStore:
    def __init__(self, path):
        self.path = Path(path)
        self.profile_path = self.path.with_suffix('.profile.yaml')
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS readings (
                    metric TEXT, at REAL, value REAL, PRIMARY KEY (metric, at));
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, at REAL, kind TEXT, message TEXT);
                CREATE INDEX IF NOT EXISTS readings_at ON readings(at);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()

    def read(self, key, default=None):
        with self.connection() as db:
            row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def write(self, key, value):
        with self.connection() as db:
            self._write(db, key, value)

    @staticmethod
    def _write(db, key, value):
        db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                   (key, json.dumps(value, allow_nan=False)))

    def load_profile(self):
        try:
            raw = self.profile_path.read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            # Preserve profiles saved by the first draft of the software.
            legacy = self.read("profile")
            if legacy is not None:
                try:
                    validate_profile(legacy)
                except ValueError as error:
                    raise ValueError(f"The legacy stored profile is invalid: {error}") from error
            return legacy
        try:
            profile = json.loads(raw)
        except ValueError:
            try:
                import yaml
            except ImportError as error:
                raise ValueError("Reading this YAML profile requires the pinned PyYAML package.") from error
            try:
                profile = yaml.safe_load(raw)
            except yaml.YAMLError as error:
                raise ValueError("The patient profile contains invalid YAML.") from error
        validate_profile(profile)
        return profile

    def save_profile(self, profile):
        validate_profile(profile)
        try:
            import yaml
        except ImportError:
            # JSON is valid YAML and keeps the simulator runnable with the standard library.
            content = json.dumps(profile, indent=2, allow_nan=False) + "\n"
        else:
            content = yaml.safe_dump(profile, sort_keys=False)
        temp_path = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.profile_path.parent,
                                    delete=False) as temp:
                temp_path = Path(temp.name)
                temp.write(content)
            os.replace(temp_path, self.profile_path)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def publish(self, status, samples, events, now):
        with self.connection() as db:
            self._write(db, "status", status)
            db.executemany("INSERT OR IGNORE INTO readings VALUES (?, ?, ?)", samples)
            db.executemany("INSERT INTO events(at, kind, message) VALUES (?, ?, ?)",
                           ((now, kind, message) for kind, message in events))

    def add_event(self, kind, message, now=None):
        """Record one event outside the monitor's publish, e.g. online access and sign-in."""
        with self.connection() as db:
            db.execute("INSERT INTO events(at, kind, message) VALUES (?, ?, ?)",
                       (time.time() if now is None else now, kind, message))

    def trends(self, now, span_s=86400, bucket_s=60):
        """Return average, minimum and maximum buckets; by default one-minute buckets for 24 hours."""
        result = {metric: [] for metric in SERIES}
        with self.connection() as db:
            rows = db.execute("""
                SELECT metric, CAST(at / ? AS INTEGER) AS slot, AVG(value), MIN(value), MAX(value)
                FROM readings WHERE at BETWEEN ? AND ? GROUP BY metric, slot ORDER BY slot
            """, (bucket_s, now - span_s, now)).fetchall()
        for metric, slot, average, low, high in rows:
            if metric in result:
                result[metric].append({"at": slot * bucket_s, "avg": average, "min": low, "max": high})
        return result

    def history(self, metric, now):
        return self.trends(now)[metric]

    def events(self, before=None, limit=50):
        """Newest first; `before` is an event id for paging to older events."""
        limit = max(1, min(int(limit), EVENT_LIMIT_MAX))
        with self.connection() as db:
            rows = db.execute(
                "SELECT id, at, kind, message FROM events WHERE id < ? ORDER BY id DESC LIMIT ?",
                (before if before is not None else 2 ** 63 - 1, limit)).fetchall()
        return [dict(zip(("id", "at", "kind", "message"), row)) for row in rows]

    def prune_readings(self, before, limit=5000):
        """Delete at most `limit` readings older than `before`; return the number deleted."""
        with self.connection() as db:
            return db.execute("""
                DELETE FROM readings WHERE rowid IN (
                    SELECT rowid FROM readings WHERE at < ? ORDER BY at LIMIT ?)
            """, (before, limit)).rowcount
