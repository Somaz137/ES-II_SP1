#!/usr/bin/env python3
"""Thin local terminal monitor. No services, camera, dashboard or notifications."""

import argparse
import json
from pathlib import Path
import time

from settings import load_alert_settings, load_runtime_settings
from monitoring_loop import run_monitor
from serial_transport import SerialTransport
from status_output import status_record
from dust import estimate_dust


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Explicit ESP32 serial device")
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
            estimate_dust(1, args.dust_baseline_mv, args.dust_sensitivity)
        except ValueError as error:
            parser.error(str(error))
    if args.baud <= 0:
        parser.error("--baud must be positive")
    alerts = load_alert_settings(args.alerts)
    runtime = load_runtime_settings(args.runtime)
    mono_origin, utc_origin = time.monotonic(), time.time()
    transport = SerialTransport(args.port, args.baud, runtime["serial_retry_interval_s"])

    def publish(state, now, connection):
        record = status_record(
            state, now, connection, monotonic_origin=mono_origin, utc_origin=utc_origin
        )
        if calibrated and record["dust"]["sensor_mv"] is not None:
            record["dust"]["estimated_dust_ug_m3"] = estimate_dust(
                record["dust"]["sensor_mv"], args.dust_baseline_mv, args.dust_sensitivity)
            record["dust"]["calibration"] = "user_configured_estimate"
        print(json.dumps(record, allow_nan=False), flush=True)

    try:
        run_monitor(transport, alerts, runtime, publish)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
