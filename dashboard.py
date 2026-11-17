"""Serve the local room dashboard from SQLite without owning sensor inputs."""
import argparse
import math
from pathlib import Path
import time

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from room_store import (DEFAULT_DB, DEMO_DB, EVENT_LIMIT_MAX, LABEL_MAX, METRICS, SERIES, SYSTEM_METRICS,
                        RoomStore, validate_label)
from settings import RUNTIME_DEFAULTS


def effective_timing(status):
    """Timing published by the monitor; the defaults apply before the first status."""
    published = status.get("timing") if isinstance(status, dict) else None
    return {**RUNTIME_DEFAULTS, **(published if isinstance(published, dict) else {})}


def parse_number(text):
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def parse_profile_form(form):
    """Convert form text to a profile; each error message names its field."""
    errors, limits = [], {}
    for metric, (name, _) in METRICS.items():
        low = form.get(metric + "_low", "").strip()
        high = form.get(metric + "_high", "").strip()
        if not low and not high:
            continue
        if not low or not high:
            errors.append(f"Enter both {name} limits, or leave both blank.")
            continue
        pair = [parse_number(low), parse_number(high)]
        for value, label in zip(pair, ("lower", "upper")):
            if value is None:
                errors.append(f"{name} {label} limit must be a finite number.")
        if None in pair:
            continue
        if pair[0] >= pair[1]:
            errors.append(f"{name} lower limit must be less than the upper limit.")
        limits[metric] = pair
    hold_text = form.get("hold_s", "").strip()
    hold = parse_number(hold_text) if hold_text else None
    if not hold_text:
        errors.append("Enter the sustained duration in seconds.")
    elif hold is None:
        errors.append("The sustained duration must be a finite number of seconds.")
    elif hold <= 0:
        errors.append("The sustained duration must be positive.")
    label = form.get("label", "").strip()
    try:
        validate_label(label)
    except ValueError as error:
        errors.append(str(error))
    if errors:
        raise ValueError(" ".join(errors))
    profile = {"limits": limits, "hold_s": hold}
    if label:  # an empty label is not written to the file
        profile["label"] = label
    return profile


def aged(value, extra):
    return None if value is None else value + extra


def system_health(status, now):
    """Derive component states from the status; ages are recalculated to `now`."""
    if not status:
        unknown = {"state": "unknown", "reported_state": None}
        return {"monitor": {"state": "waiting", "updated_at": None, "age_s": None},
                "serial": {**unknown, "error": None, "communication_timed_out": None,
                           "communication_alert_active": None, "last_contact_age_s": None},
                "bme680": {**unknown, "measurement_current": False, "measurement_age_s": None,
                           "alert_active": None},
                "dust": {**unknown, "age_s": None, "alert_active": None},
                "occupancy": {**unknown, "source": None, "observation_age_s": None},
                "profile": {**unknown, "error": None},
                "alarm": {**unknown, "wanted_level": None, "confirmed_level": None, "silenced": None,
                          "confirmation_age_s": None}}
    updated = status.get("updated_at")
    age = now - updated if isinstance(updated, (int, float)) else None
    current = age is not None and age <= effective_timing(status)["status_stale_after_s"]
    since = age or 0
    dust = status.get("dust") or {}
    monitoring = status.get("limit_monitoring") or {}

    def component(reported, **facts):
        return {"state": reported if current else "unknown", "reported_state": reported, **facts}

    profile_state = ("error" if status.get("profile_error") else
                     "none" if monitoring.get("reason") == "no_profile" else "loaded")
    connected = status.get("transport_connected")
    alarm = status.get("alarm") if isinstance(status.get("alarm"), dict) else {}
    return {
        "monitor": {"state": "current" if current else "overdue", "updated_at": updated, "age_s": age},
        "serial": component("unknown" if connected is None else "connected" if connected else "disconnected",
                            error=status.get("transport_error"),
                            communication_timed_out=status.get("communication_timed_out"),
                            communication_alert_active=status.get("communication_alert_active"),
                            last_contact_age_s=aged(status.get("last_contact_age_s"), since)),
        "bme680": component(status.get("input_status", "unknown"),
                            measurement_current=bool(current and status.get("measurement_current")),
                            measurement_age_s=aged(status.get("measurement_age_s"), since),
                            alert_active=status.get("sensor_alert_active")),
        "dust": component(dust.get("status", "unknown"), age_s=aged(dust.get("age_s"), since),
                          alert_active=dust.get("alert_active")),
        "occupancy": component(status.get("occupancy", "unknown"), source=status.get("occupancy_source"),
                               observation_age_s=aged(status.get("occupancy_observation_age_s"), since)),
        "profile": component(profile_state, error=status.get("profile_error")),
        "alarm": component(alarm.get("state", "unknown"), wanted_level=alarm.get("wanted_level"),
                           confirmed_level=alarm.get("confirmed_level"), silenced=alarm.get("silenced"),
                           confirmation_age_s=aged(alarm.get("confirmation_age_s"), since)),
    }


def create_app(path=DEFAULT_DB, *, demo=False):
    app = Flask(__name__)
    store = RoomStore(path)

    @app.before_request
    def local_form_only():
        if request.host.split(':', 1)[0] not in {'localhost', '127.0.0.1'}:
            abort(403)
        if request.method == "POST":
            origin = request.headers.get("Origin")
            if request.headers.get("Sec-Fetch-Site") == "cross-site":
                abort(403)
            if origin and origin.rstrip("/") != request.host_url.rstrip("/"):
                abort(403)

    def current_status():
        """The stored status if it is a mapping and not overdue, otherwise None."""
        status = store.read("status")
        status = status if isinstance(status, dict) else {}
        updated = status.get("updated_at")
        if (isinstance(updated, bool) or not isinstance(updated, (int, float))
                or time.time() - updated > effective_timing(status)["status_stale_after_s"]):
            return None
        return status

    def load_profile():
        try:
            return store.load_profile(), None
        except (OSError, ValueError) as error:
            return None, str(error)

    def render_profile(error=None, form=None):
        profile, profile_error = load_profile()
        error = error or profile_error
        profile = profile or {"limits": {}, "hold_s": ""}
        fields = {"hold_s": profile["hold_s"], "label": profile.get("label", "")}
        for metric in METRICS:
            fields[metric + "_low"], fields[metric + "_high"] = profile["limits"].get(metric, ["", ""])
        if form is not None:
            fields = {key: form.get(key, "") for key in fields}
        return render_template("room.html", charts=SERIES, metrics=METRICS, demo=demo,
                               fields=fields, error=error, label_max=LABEL_MAX)

    @app.get("/")
    def index():
        return render_profile()

    def query_int(name, default):
        text = request.args.get(name)
        if text is None:
            return default
        if not text.isdigit() or int(text) < 1:
            abort(400)
        return int(text)

    @app.get("/api/room")
    def room_data():
        before = query_int("events_before", None)
        limit = min(query_int("limit", 50), EVENT_LIMIT_MAX)
        now = time.time()
        status = store.read("status")
        profile, profile_error = load_profile()
        events = store.events(before, limit)
        more = bool(events) and bool(store.events(events[-1]["id"], 1))
        def limit_checked(key):
            """Patient measurements, and the estimates whose system limit the monitor published."""
            if key in METRICS:
                return True
            block = status.get(key) if isinstance(status, dict) else None
            return key in SYSTEM_METRICS and isinstance(block, dict) and block.get("limit") is not None

        trends = {key: {"name": name, "unit": unit, "limit_checked": limit_checked(key),
                        "estimate": key in SYSTEM_METRICS, "buckets": buckets}
                  for (key, (name, unit)), buckets in zip(SERIES.items(), store.trends(now).values())}
        if profile is not None:
            profile = {**profile, "label": profile.get("label", "")}
        return jsonify(status=status, profile=profile, profile_error=profile_error, trends=trends,
                       events=events, events_has_more=more, health=system_health(status, now),
                       timing=effective_timing(status), now=now)

    @app.post("/profile")
    def profile():
        try:
            store.save_profile(parse_profile_form(request.form))
        except ValueError as error:
            return render_profile(str(error), request.form), 400
        except OSError:
            return render_profile("Could not save the patient profile.", request.form), 503
        return redirect(url_for("index"), code=303)

    @app.post("/acknowledge")
    def acknowledge():
        status = store.read("status")
        status = status if isinstance(status, dict) else {}
        token = request.form.get("alert_id")
        updated = status.get("updated_at")
        if (not token or token != status.get("communication_alert_id")
                or status.get("communication_timed_out") is not False
                or isinstance(updated, bool) or not isinstance(updated, (int, float))
                or time.time() - updated > effective_timing(status)["status_stale_after_s"]):
            abort(409)
        store.write("communication_ack", token)
        return redirect(url_for("index"), code=303)

    @app.post("/silence")
    def silence():
        """Ask the monitor to silence the buzzer for the limit alerts shown."""
        status = current_status()
        if status is None:
            abort(409, description="No current monitor status. The alarm was not silenced.")
        alarm = status.get("alarm")
        if not isinstance(alarm, dict):
            abort(409, description="No local alarm state is published. The alarm was not silenced.")
        current = alarm.get("silence_token")
        if not current:
            abort(409, description="No unsilenced limit alert is active. Nothing was silenced.")
        if request.form.get("token") != current:
            abort(409, description="The active limit alerts changed. Reload the page and try again.")
        store.write("alarm_silence", current)
        return redirect(url_for("index"), code=303)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    create_app(args.db or (DEMO_DB if args.demo else DEFAULT_DB), demo=args.demo).run(host="127.0.0.1")
