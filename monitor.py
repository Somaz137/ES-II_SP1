#!/usr/bin/env python3
"""Run the serial monitor or a hardware-free demonstration."""

import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import time
from uuid import uuid4

from room_store import DEFAULT_DB, DEMO_DB, RoomStore
from room_session import RoomSession
from simulated_input import SimulatedTransport
from occupancy import CameraOccupancy
from monitoring_state import acknowledge_monitoring_communication
from monitoring_loop import run_monitor
from serial_transport import SerialTransport
from status_output import status_record
from dust import estimate_dust
from settings import RUNTIME_DEFAULTS


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--port", help="Explicit ESP32 serial device")
    source.add_argument("--demo", action="store_true", help="Simulated sensor and occupancy data")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--camera", type=int, help="OpenCV camera device index")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--alerts", type=Path, default=root / "config/alerts.yaml")
    parser.add_argument("--runtime", type=Path, default=root / "config/runtime.yaml")
    parser.add_argument("--dust-baseline-mv", type=float)
    parser.add_argument("--dust-sensitivity", type=float,
                        help="Sensitivity in mV per mg/m3; use with measured baseline")
    args = parser.parse_args()
    calibrated = args.dust_baseline_mv is not None and args.dust_sensitivity is not None
    if (args.dust_baseline_mv is None) != (args.dust_sensitivity is None):
        parser.error("Supply both dust calibration parameters or neither.")
    if calibrated:
        try:
            estimate_dust(5500, args.dust_baseline_mv, args.dust_sensitivity)
        except ValueError as error:
            parser.error(str(error))
    if args.camera is not None and (args.demo or args.camera < 0):
        parser.error("Choose a nonnegative camera index in serial mode.")
    if args.camera is not None:
        try:
            import cv2
        except ImportError:
            parser.error("Camera mode needs the project's pinned OpenCV package.")
    if args.baud <= 0:
        parser.error("--baud must be positive")
    if args.demo:
        alerts = {"communication_timeout_s": 120, "sensor_error_timeout_s": 120}
        runtime = {"fault_check_interval_s": 5, "serial_poll_interval_s": 0.05, **RUNTIME_DEFAULTS}
        transport = SimulatedTransport()
    else:
        from settings import load_alert_settings, load_runtime_settings
        alerts = load_alert_settings(args.alerts)
        runtime = load_runtime_settings(args.runtime)
        transport = SerialTransport(args.port, args.baud, runtime["serial_retry_interval_s"])
    store = RoomStore(args.db or (DEMO_DB if args.demo else DEFAULT_DB))
    timing = {key: runtime[key] for key in RUNTIME_DEFAULTS}
    timing["fault_check_interval_s"] = runtime["fault_check_interval_s"]
    session = RoomSession(store, demo=args.demo, timing=timing)
    if args.demo and not store.profile_path.exists() and store.load_profile() is None:
        store.save_profile({"limits": {"temp_c": [20, 27]}, "hold_s": 9})
    mono_origin, utc_origin = time.monotonic(), time.time()

    camera = CameraOccupancy(args.camera, runtime["camera_interval_s"]) if args.camera is not None else None
    last_ack = store.read("communication_ack")
    displayed_alert = None

    def apply_controls(state, now):
        nonlocal last_ack
        request = store.read("communication_ack")
        if request != last_ack:
            last_ack = request
            if request == displayed_alert and state.communication.alert_active and not state.communication.timed_out:
                session.note_acknowledgment()
                return acknowledge_monitoring_communication(state, now)
        return state

    def publish(state, now, connection):
        nonlocal displayed_alert
        record = status_record(
            state, now, connection, monotonic_origin=mono_origin, utc_origin=utc_origin
        )
        if calibrated and record["dust"]["sensor_mv"] is not None:
            record["dust"]["estimated_dust_ug_m3"] = estimate_dust(
                record["dust"]["sensor_mv"], args.dust_baseline_mv, args.dust_sensitivity)
            record["dust"]["calibration"] = "user_configured_estimate"
        if state.communication.alert_active:
            if displayed_alert is None:
                displayed_alert = uuid4().hex
        else:
            displayed_alert = None
        record["communication_alert_id"] = displayed_alert
        occupancy = "occupied" if args.demo else camera.current(now) if camera else "unknown"
        record["occupancy_source"] = "simulated" if args.demo else "camera" if camera else "none"
        record["occupancy_observation_age_s"] = camera.observation_age(now) if camera else None
        session.update(record, now, time.time(), occupancy)
        print(json.dumps(record, allow_nan=False), flush=True)

    try:
        with camera if camera else nullcontext():
            run_monitor(transport, alerts, runtime, publish, apply_controls=apply_controls)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
