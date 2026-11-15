"""SQLite state shared by the monitor and the local dashboard."""
from contextlib import contextmanager
import json
import math
import os
import sqlite3
from pathlib import Path
from tempfile import NamedTemporaryFile

METRICS = {"temp_c": ("Temperature", "°C"), "humidity_pct": ("Humidity", "%"),
           "pressure_hpa": ("Pressure", "hPa")}
DEFAULT_DB = Path(__file__).resolve().parent / "room.sqlite3"
DEMO_DB = DEFAULT_DB.with_name("room-demo.sqlite3")


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {"limits", "hold_s"}:
        raise ValueError("Supply limits and a sustained duration.")
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
            return self.read("profile")
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

    def history(self, metric, now):
        with self.connection() as db:
            # Minute averages keep the 24-hour response bounded.
            return db.execute("""
                SELECT MIN(at), AVG(value) FROM readings
                WHERE metric = ? AND at BETWEEN ? AND ? GROUP BY CAST(at / 60 AS INTEGER)
                ORDER BY MIN(at)
            """, (metric, now - 86400, now)).fetchall()

    def events(self):
        with self.connection() as db:
            return db.execute("SELECT at, kind, message FROM events ORDER BY id DESC LIMIT 50").fetchall()
