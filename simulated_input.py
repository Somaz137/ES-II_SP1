"""Generate serial records for a hardware-free dashboard demonstration. Simulation, not hardware."""
import json
import re

COMMAND = re.compile(r"ALARM,([012])")
BSEC_STATE = re.compile(r"BSEC_STATE,([0-9a-fA-F]{2,476})")
# Simulated BSEC library version and a stand-in 238-byte state (not a real Bosch state).
DEMO_BSEC_VERSION = "2.6.1.0"
DEMO_BSEC_STATE = bytes(range(238)).hex()
DEMO_STATE_AFTER_S = 60


class SimulatedTransport:
    """Simulated board. alarm="echo" replies to ALARM commands at the next poll,
    "silent" accepts them without reply, "fail" refuses every write. Like the
    firmware it asks for the BSEC state at start, confirms a BSEC_STATE,<hex>
    reply in echo mode, and sends one state line after DEMO_STATE_AFTER_S."""

    connected = True
    last_error = None

    def __init__(self, alarm="echo"):
        if alarm not in ("echo", "silent", "fail"):
            raise ValueError("alarm must be echo, silent or fail.")
        self.alarm = alarm
        self.started_at = None
        self.next_at = None
        self.replies = []
        self.last_send_error = None
        self.state_sent = False

    def send(self, line):
        if self.alarm == "fail":
            self.last_send_error = "Simulated write failure."
            return False
        self.last_send_error = None
        if self.alarm == "echo":
            # Like the firmware: each complete valid line is applied and confirmed.
            for part in line.split("\n"):
                match = COMMAND.fullmatch(part.strip())
                if match:
                    self.replies.append(json.dumps({"type": "alarm", "state": int(match[1])}))
                elif (state := BSEC_STATE.fullmatch(part.strip())) and len(state[1]) % 2 == 0:
                    # A saved state was sent back: the board restores it and confirms.
                    self.replies.append(json.dumps({"type": "bsec_state_restored", "ok": True}))
        return True

    def poll(self, now):
        replies, self.replies = self.replies, []
        if self.started_at is None:
            # Like the firmware at start: ask the host for the saved BSEC state.
            self.started_at = self.next_at = now
            replies.append(json.dumps({"type": "bsec_state_request",
                                       "bsec_version": DEMO_BSEC_VERSION}))
        if now < self.next_at:
            return replies
        self.next_at = now + 3
        elapsed = now - self.started_at
        temperature = 24 if elapsed % 90 < 18 or elapsed % 90 >= 60 else 31
        # Bosch accuracy: 0 (run-in), then 1, then 3, as after a board start.
        accuracy = 0 if elapsed < 30 else 1 if elapsed < 45 else 3
        cycle = elapsed % 300
        # A scripted air-quality episode and a later dust episode in each 300 s.
        iaq = 182 if 120 <= cycle < 210 else 55 + round(elapsed) % 15
        dust_mv = 1600 if 220 <= cycle < 280 else 920 + round(elapsed) % 180
        if elapsed >= DEMO_STATE_AFTER_S and not self.state_sent:
            # One state line per demo run, as the board sends at accuracy 3.
            self.state_sent = True
            replies.append(json.dumps({"type": "bsec_state", "accuracy": 3,
                                       "bsec_version": DEMO_BSEC_VERSION, "state": DEMO_BSEC_STATE}))
        bsec = dict(stabilization_status=int(elapsed >= 30), run_in_status=int(elapsed >= 30),
                    iaq_accuracy=accuracy, iaq=iaq)
        return replies + [
            json.dumps(dict(type="reading", temp_c=temperature, humidity_pct=48,
                            pressure_hpa=1008, gas_ohms=12000, bsec=bsec)),
            json.dumps(dict(type="dust", sensor_mv=dust_mv)),
        ]

    def close(self):
        pass
