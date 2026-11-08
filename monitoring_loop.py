"""Connect bounded serial polling to pure routing and periodic fault checks."""

import time

from message_router import process_serial_line
from monitoring_state import create_monitoring_state, evaluate_monitoring_faults


def run_monitor(
    transport, alert_settings, runtime_settings, publish,
    *, clock=time.monotonic, sleep=time.sleep, should_stop=lambda: False,
):
    """Run until stopped; publish startup and changes without opening a camera.

    Times are host monotonic receipt times, not sensor acquisition times.
    Reconnection never creates a new fault/reading state. The publisher
    must be fast: a blocking consumer delays this single-threaded loop.
    Always close the transport, including on KeyboardInterrupt/errors.
    """
    started = clock()
    state = create_monitoring_state(
        started, alert_settings["communication_timeout_s"],
        alert_settings["sensor_error_timeout_s"],
    )
    interval = runtime_settings["fault_check_interval_s"]
    next_check = started + interval
    try:
        publish(state, started, transport)
        while not should_stop():
            previous = state
            old_transport = (transport.connected, transport.last_error)
            lines = transport.poll(clock())
            for line in lines:
                state = process_serial_line(state, line, clock())
            now = clock()
            if now >= next_check:
                state = evaluate_monitoring_faults(state, now)
                # Skip missed ticks instead of replaying old timestamps.
                next_check += (int((now - next_check) // interval) + 1) * interval
            if state != previous or old_transport != (transport.connected, transport.last_error):
                publish(state, now, transport)
            sleep(runtime_settings["serial_poll_interval_s"])
        return state
    finally:
        transport.close()
