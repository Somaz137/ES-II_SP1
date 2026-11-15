"""Generate serial records for a hardware-free dashboard demonstration."""
import json
import re

COMMAND = re.compile(r"ALARM,([012])")


class SimulatedTransport:
    """Simulated board. alarm="echo" replies to ALARM commands at the next poll,
    "silent" accepts them without reply, "fail" refuses every write."""

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
        return True

    def poll(self, now):
        replies, self.replies = self.replies, []
        if self.started_at is None:
            self.started_at = self.next_at = now
        if now < self.next_at:
            return replies
        self.next_at = now + 3
        elapsed = now - self.started_at
        temperature = 24 if elapsed % 90 < 18 or elapsed % 90 >= 60 else 31
        return replies + [
            json.dumps(dict(type="reading", temp_c=temperature, humidity_pct=48,
                            pressure_hpa=1008, gas_ohms=12000)),
            json.dumps(dict(type="dust", sensor_mv=920 + round(elapsed) % 180)),
        ]

    def close(self):
        pass
