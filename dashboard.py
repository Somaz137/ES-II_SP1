"""Serve the local room dashboard from SQLite without owning sensor inputs."""
import argparse
from datetime import timedelta
import math
from pathlib import Path
import time

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

from online_auth import LoginLimiter, check_password, new_csrf_token, tokens_match

from room_store import (DEFAULT_DB, DEMO_DB, EVENT_LIMIT_MAX, LABEL_MAX, METRICS, SERIES, SYSTEM_METRICS,
                        RoomStore, validate_label)
from settings import RUNTIME_DEFAULTS


# (endpoint, path, title) for each page, in navigation order.
PAGES = [("index", "/", "Overview"), ("trends", "/trends", "Trends"), ("events", "/events", "Events"),
         ("limits", "/limits", "Patient limits"), ("system", "/system", "System")]
PAGE_PATHS = {path for _, path, _ in PAGES}
# Trend window name: (span in seconds, bucket size in seconds). Readings are kept 7 days.
TREND_WINDOWS = {"24h": (86400, 60), "7d": (7 * 86400, 600)}
TUNNEL_OFF = {"state": "off", "url": None, "reason": None}
# Online origin only. The pages use no inline script or style.
ONLINE_HEADERS = {
    "Cache-Control": "no-store",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
                                "connect-src 'self'; form-action 'self'; frame-ancestors 'none'; "
                                "base-uri 'none'; object-src 'none'"),
}


def duration_words(seconds):
    """Whole minutes and hours in words, e.g. 300 -> '5 min', 90 -> '1 min 30 s'."""
    total = max(0, round(seconds))
    hours, minutes, secs = total // 3600, total % 3600 // 60, total % 60
    parts = [f"{hours} h"] * bool(hours) + [f"{minutes} min"] * bool(minutes) + [f"{secs} s"] * bool(secs)
    return " ".join(parts) or "0 s"


def number_text(value):
    return f"{value:g}"


def in_force(profile):
    """Rows for the 'In force now' list, worded; None when no profile is loaded."""
    if profile is None:
        return None
    rows = [("Label", profile.get("label") or "not set")]
    for metric, (name, unit) in METRICS.items():
        pair = profile["limits"].get(metric)
        rows.append((name, f"{number_text(pair[0])} to {number_text(pair[1])} {unit}" if pair else "no limit set"))
    rows.append(("Sustained time", duration_words(profile["hold_s"])))
    return rows


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


class ProfileFormError(ValueError):
    """Invalid profile form; `fields` maps a field group to its messages."""

    def __init__(self, fields):
        self.fields = fields
        super().__init__(" ".join(message for messages in fields.values() for message in messages))


def parse_profile_form(form):
    """Convert form text to a profile; each error message names its field."""
    fields, limits = {}, {}

    def error(field, message):
        fields.setdefault(field, []).append(message)

    for metric, (name, _) in METRICS.items():
        low = form.get(metric + "_low", "").strip()
        high = form.get(metric + "_high", "").strip()
        if not low and not high:
            continue
        if not low or not high:
            error(metric, f"Enter both {name} limits, or leave both blank.")
            continue
        pair = [parse_number(low), parse_number(high)]
        for value, label in zip(pair, ("lower", "upper")):
            if value is None:
                error(metric, f"{name} {label} limit must be a finite number.")
        if None in pair:
            continue
        if pair[0] >= pair[1]:
            error(metric, f"{name} lower limit must be less than the upper limit.")
        limits[metric] = pair
    hold_text = form.get("hold_s", "").strip()
    hold = parse_number(hold_text) if hold_text else None
    if not hold_text:
        error("hold_s", "Enter the sustained duration in seconds.")
    elif hold is None:
        error("hold_s", "The sustained duration must be a finite number of seconds.")
    elif hold <= 0:
        error("hold_s", "The sustained duration must be positive.")
    label = form.get("label", "").strip()
    try:
        validate_label(label)
    except ValueError as problem:
        error("label", str(problem))
    if fields:
        raise ProfileFormError(fields)
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


def create_app(path=DEFAULT_DB, *, demo=False, online=False, secret=None, tunnel=None, session_hours=8,
               limiter=None):
    """The local origin (full controls), or with `online` the origin cloudflared points at.

    Online, every request counts as remote: reading is open, and every POST needs a signed-in
    session and its CSRF token. `secret` holds the password hash and the session key.
    """
    app = Flask(__name__)
    store = RoomStore(path)
    lifetime_s = session_hours * 3600
    if online:
        if not secret:
            raise ValueError("Online access needs a password. Run dashboard.py --set-password first.")
        app.secret_key = secret["secret_key"]
        app.config.update(SESSION_COOKIE_NAME="room_online", SESSION_COOKIE_SECURE=True,
                          SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                          SESSION_REFRESH_EACH_REQUEST=False,
                          PERMANENT_SESSION_LIFETIME=timedelta(seconds=lifetime_s))
        limiter = limiter or LoginLimiter()

    def signed_in():
        started = session.get("signed_in_at") if online else None
        return isinstance(started, (int, float)) and 0 <= time.time() - started < lifetime_s

    def csrf_token():
        if not online:
            return ""
        if "csrf" not in session:
            session["csrf"] = new_csrf_token()
        return session["csrf"]

    def tunnel_state():
        state = tunnel.state() if tunnel is not None else dict(TUNNEL_OFF)
        if online and not signed_in():
            state["url"] = None  # anonymous online visitors do not need the link
        return state

    @app.context_processor
    def online_context():
        return {"online": online, "signed_in": signed_in(), "locked": online and not signed_in(),
                "csrf_token": csrf_token(), "tunnel": tunnel_state()}

    @app.before_request
    def online_gate():
        if not online or request.method != "POST":
            return
        if request.headers.get("Sec-Fetch-Site") == "cross-site":
            abort(403)
        if not tokens_match(session.get("csrf"), request.form.get("csrf_token")):
            abort(403)
        if request.endpoint not in {"signin_post"} and not signed_in():
            abort(403)

    @app.after_request
    def online_headers(response):
        if online:
            response.headers.update(ONLINE_HEADERS)
        return response

    @app.before_request
    def local_form_only():
        if online:
            return
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

    def render_page(endpoint, **context):
        profile, profile_error = load_profile()
        return render_template(("overview" if endpoint == "index" else endpoint) + ".html", page=endpoint, pages=PAGES, demo=demo,
                               charts=SERIES, metrics=METRICS, system_metrics=SYSTEM_METRICS,
                               profile=profile, profile_error=profile_error,
                               label=(profile or {}).get("label", ""), **context)

    def last_profile_change():
        """Time of the newest profile change among the recent events, if any."""
        for event in store.events(None, EVENT_LIMIT_MAX):
            if event["kind"] == "profile_changed":
                return event["at"]
        return None

    def render_limits(error=None, form=None, field_errors=None):
        profile, profile_error = load_profile()
        saved = profile or {"limits": {}, "hold_s": ""}
        fields = {"hold_s": saved["hold_s"], "label": saved.get("label", "")}
        for metric in METRICS:
            fields[metric + "_low"], fields[metric + "_high"] = saved["limits"].get(metric, ["", ""])
        if form is not None:
            fields = {key: form.get(key, "") for key in fields}
        return render_page("limits", fields=fields, error=error or profile_error,
                           field_errors=field_errors or {}, label_max=LABEL_MAX,
                           changed_at=last_profile_change(), in_force=in_force(profile))

    @app.get("/")
    def index():
        return render_page("index")

    @app.get("/trends")
    def trends():
        return render_page("trends")

    @app.get("/events")
    def events():
        return render_page("events")

    @app.get("/limits")
    def limits():
        return render_limits()

    @app.get("/system")
    def system():
        return render_page("system")

    def back(default="index"):
        """The page a form was posted from, if it is one of ours; otherwise `default`."""
        target = request.form.get("next", "")
        return target if target in PAGE_PATHS else url_for(default)

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

        span, bucket = TREND_WINDOWS.get(request.args.get("window", "24h"), (None, None))
        if span is None:
            abort(400)
        series = store.trends(now, span_s=span, bucket_s=bucket)
        trends = {key: {"name": name, "unit": unit, "limit_checked": limit_checked(key),
                        "estimate": key in SYSTEM_METRICS, "buckets": series[key]}
                  for key, (name, unit) in SERIES.items()}
        if profile is not None:
            profile = {**profile, "label": profile.get("label", "")}
        return jsonify(status=status, profile=profile, profile_error=profile_error, trends=trends,
                       events=events, events_has_more=more, health=system_health(status, now),
                       timing=effective_timing(status), online=tunnel_state(), now=now)

    if online:
        def render_signin(error=None, code=200):
            target = request.values.get("next", "")
            return render_template("signin.html", error=error,
                                   next=target if target in PAGE_PATHS else "/"), code

        @app.get("/signin")
        def signin():
            if signed_in():
                return redirect(url_for("index"), code=303)
            return render_signin()

        @app.post("/signin")
        def signin_post():
            # CF-Connecting-IP is only a rate-limit key, never a reason to trust a request.
            client = request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"
            wait = limiter.wait_s(client)
            if wait:
                minutes = max(1, math.ceil(wait / 60))
                return render_signin(f"Too many failed sign-ins. Try again in {minutes} min.", 429)
            if not check_password(secret, request.form.get("password", "")):
                limiter.failed(client)
                store.add_event("online_signin_failed", "Online sign-in failed")
                return render_signin("The password is not correct.", 401)
            limiter.succeeded(client)
            session.clear()
            session.permanent = True
            session["signed_in_at"] = time.time()
            session["csrf"] = new_csrf_token()
            store.add_event("online_signed_in", "Signed in online")
            target = request.form.get("next", "")
            return redirect(target if target in PAGE_PATHS else url_for("index"), code=303)

        @app.post("/signout")
        def signout():
            session.clear()
            store.add_event("online_signed_out", "Signed out online")
            return redirect(url_for("index"), code=303)

    @app.post("/profile")
    def profile():
        try:
            store.save_profile(parse_profile_form(request.form))
        except ProfileFormError as error:
            return render_limits(str(error), request.form, error.fields), 400
        except ValueError as error:
            return render_limits(str(error), request.form), 400
        except OSError:
            return render_limits("Could not save the patient profile.", request.form), 503
        return redirect(url_for("limits"), code=303)

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
        return redirect(back(), code=303)

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
        return redirect(back(), code=303)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    create_app(args.db or (DEMO_DB if args.demo else DEFAULT_DB), demo=args.demo).run(host="127.0.0.1")
