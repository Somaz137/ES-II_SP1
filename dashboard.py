"""Serve the local room dashboard from SQLite without owning sensor inputs."""
import argparse
from pathlib import Path
import time

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

from room_store import DEFAULT_DB, DEMO_DB, METRICS, RoomStore


def create_app(path=DEFAULT_DB, *, demo=False):
    app = Flask(__name__)
    store = RoomStore(path)
    charts = {**METRICS, "dust_mv": ("Dust signal", "mV")}

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

    @app.get("/")
    def index():
        return render_template("room.html", charts=charts, metrics=METRICS, demo=demo,
                               profile=store.read("profile") or {"limits": {}, "hold_s": ""})

    @app.get("/api/room")
    def room_data():
        metric = request.args.get("metric", "temp_c")
        if metric not in charts:
            abort(404)
        now = time.time()
        return jsonify(status=store.read("status"), events=store.events(),
                       trend=store.history(metric, now), now=now)

    @app.post("/profile")
    def profile():
        try:
            limits = {}
            for metric in METRICS:
                low = request.form.get(metric + "_low", "").strip()
                high = request.form.get(metric + "_high", "").strip()
                if low or high:
                    limits[metric] = [float(low), float(high)]
            store.save_profile({"limits": limits, "hold_s": float(request.form.get("hold_s", ""))})
        except ValueError as error:
            return render_template("room.html", charts=charts, metrics=METRICS, demo=demo,
                                   profile=store.read("profile") or {"limits": {}, "hold_s": ""},
                                   error=str(error)), 400
        return redirect(url_for("index"), code=303)

    @app.post("/acknowledge")
    def acknowledge():
        status = store.read("status") or {}
        token = request.form.get("alert_id")
        if (not token or token != status.get("communication_alert_id")
                or status["communication_timed_out"] or time.time()-status["updated_at"] > 15):
            abort(409)
        store.write("communication_ack", token)
        return redirect(url_for("index"), code=303)

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    create_app(args.db or (DEMO_DB if args.demo else DEFAULT_DB), demo=args.demo).run(host="127.0.0.1")
