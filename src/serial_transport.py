"""Nonblocking serial reads, bounded writes, reconnect attempts and newline framing."""

# pyserial 3.5 on Linux: write_timeout=0 spins forever when the output buffer is
# full (EAGAIN is retried), and None blocks. A short positive timeout bounds a send.
SERIAL_WRITE_TIMEOUT_S = 0.02


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

    return serial.Serial(port, baudrate=baud, timeout=0, write_timeout=SERIAL_WRITE_TIMEOUT_S)


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
        self.last_send_error = None
        self.resync = False

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

    def send(self, line: str) -> bool:
        """Write one command line; return False on any failure. Never raises.

        The connection's write timeout bounds the time spent here. A short
        write or a timeout may leave a fragment on the line, so the next
        command starts with a newline that ends the fragment. A failure does
        not close the port; the next read detects a lost device.
        """
        if self.connection is None:
            self.last_send_error = "Serial port not connected."
            return False
        data = (b"\n" if self.resync else b"") + line.encode("ascii")
        try:
            written = self.connection.write(data)
        except Exception as error:  # noqa: BLE001 - the alarm path must not stop monitoring
            self.last_send_error = str(error) or type(error).__name__
            self.resync = True
            return False
        if written is not None and written != len(data):
            self.last_send_error = f"Short write: {written} of {len(data)} bytes."
            self.resync = True
            return False
        self.last_send_error = None
        self.resync = False
        return True

    def close(self):
        """Clear partial transport data, preserving monitoring state elsewhere."""
        connection, self.connection = self.connection, None
        self.framer = LineFramer()
        self.resync = False
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
