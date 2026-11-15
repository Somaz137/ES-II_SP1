"""Generate serial records for a hardware-free dashboard demonstration."""
import json


class SimulatedTransport:
    connected = True
    last_error = None

    def __init__(self):
        self.started_at = None
        self.next_at = None

    def poll(self, now):
        if self.started_at is None:
            self.started_at = self.next_at = now
        if now < self.next_at:
            return []
        self.next_at = now + 3
        elapsed = now - self.started_at
        temperature = 24 if elapsed % 90 < 18 or elapsed % 90 >= 60 else 31
        return [
            json.dumps(dict(type="reading", temp_c=temperature, humidity_pct=48,
                            pressure_hpa=1008, gas_ohms=12000)),
            json.dumps(dict(type="dust", sensor_mv=920 + round(elapsed) % 180)),
        ]

    def close(self):
        pass
