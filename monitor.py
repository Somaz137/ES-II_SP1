#!/usr/bin/env python3
"""Thin local terminal monitor. No services, camera, dashboard or notifications."""

import argparse
import json
from pathlib import Path
import time

from config_loader import load_alert_settings
from monitoring_loop import run_monitor
from runtime_settings import load_runtime_settings
from serial_transport import SerialTransport
from status_output import status_record


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Explicit ESP32 serial device")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--alerts", type=Path, default=root / "config/alerts.yaml")
    parser.add_argument("--runtime", type=Path, default=root / "config/runtime.yaml")
    args = parser.parse_args()
    if args.baud <= 0:
        parser.error("--baud must be positive")
    alerts = load_alert_settings(args.alerts)
    runtime = load_runtime_settings(args.runtime)
    mono_origin, utc_origin = time.monotonic(), time.time()
    transport = SerialTransport(args.port, args.baud, runtime["serial_retry_interval_s"])

    def publish(state, now, connection):
        print(json.dumps(status_record(
            state, now, connection, monotonic_origin=mono_origin, utc_origin=utc_origin
        ), allow_nan=False), flush=True)

    try:
        run_monitor(transport, alerts, runtime, publish)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
