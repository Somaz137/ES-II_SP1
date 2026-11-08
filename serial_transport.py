"""Nonblocking serial reads, reconnect attempts and bounded newline framing."""


class LineFramer:
    """Retain partial lines. Discard oversized/invalid UTF-8 records entirely."""

    def __init__(self, max_line_bytes: int = 4096):
        self.limit = max_line_bytes
        self.pending = bytearray()
        self.discarding = False

    def feed(self, chunk: bytes) -> list[str]:
        lines = []
        for byte in chunk:
            if byte == 10:
                if not self.discarding:
                    try:
                        line = self.pending.decode("utf-8").strip()
                    except UnicodeDecodeError:
                        line = ""
                    if line:
                        lines.append(line)
                self.pending.clear()
                self.discarding = False
            elif not self.discarding:
                self.pending.append(byte)
                if len(self.pending) > self.limit:
                    self.pending.clear()
                    self.discarding = True
        return lines


def open_serial_port(port: str, baud: int):
    """Use the existing pinned pyserial. Opening may reset some ESP32 boards."""
    import serial

    return serial.Serial(port, baudrate=baud, timeout=0)


class SerialTransport:
    """One selected port; reconnect does not establish recognized ESP contact."""

    def __init__(self, port, baud, retry_interval_s, opener=open_serial_port):
        self.port = port
        self.baud = baud
        self.retry_interval_s = retry_interval_s
        self.opener = opener
        self.connection = None
        self.next_retry_at = 0.0
        self.framer = LineFramer()
        self.last_error = None

    @property
    def connected(self):
        return self.connection is not None

    def poll(self, now: float) -> list[str]:
        """At most one 4096-byte read per poll, so noise cannot starve ticks.

        The serial factory must return a nonblocking connection. pyserial's
        SerialException derives from OSError. Programming errors propagate.
        """
        if self.connection is None and now < self.next_retry_at:
            return []
        try:
            if self.connection is None:
                self.connection = self.opener(self.port, self.baud)
                self.last_error = None
            chunk = self.connection.read(4096)
        except OSError as error:
            self.close()
            self.last_error = str(error)
            self.next_retry_at = now + self.retry_interval_s
            return []
        return self.framer.feed(chunk)

    def close(self):
        """Clear partial transport data, preserving monitoring state elsewhere."""
        connection, self.connection = self.connection, None
        self.framer = LineFramer()
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
