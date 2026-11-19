"""Deferred Linux tests: byte framing and reconnect without actual devices."""

from serial_transport import LineFramer, SerialTransport


class Port:
    def __init__(self, *chunks):
        self.chunks = iter(chunks)
        self.closed = False

    def read(self, size):
        value = next(self.chunks, b"")
        if isinstance(value, Exception):
            raise value
        return value

    def close(self):
        self.closed = True


def test_split_multiple_lines_crlf_and_empty_timeout():
    framer = LineFramer()
    assert framer.feed(b'{"type":') == []
    assert framer.feed(b"") == []
    assert framer.feed(b'"error"}\r\nhello\n\n') == ['{"type":"error"}', "hello"]


def test_oversized_record_discards_its_tail_until_newline():
    framer = LineFramer(max_line_bytes=4)
    assert framer.feed(b"abcde") == []
    assert len(framer.pending) == 0
    assert framer.feed(b"ok\nok\n") == ["ok"]


def test_invalid_utf8_discards_entire_line_and_recovers():
    assert LineFramer().feed(b"bad\xff\ngood\n") == ["good"]


def test_open_failure_retry_interval_and_connection_recovery():
    calls = []
    port = Port(b"hello\n")

    def opener(name, baud):
        calls.append((name, baud))
        if len(calls) == 1:
            raise OSError("unplugged")
        return port

    transport = SerialTransport("chosen", 115200, 5, opener)
    assert transport.poll(0) == []
    assert transport.last_error == "unplugged"
    assert transport.poll(4.99) == []
    assert len(calls) == 1
    assert transport.poll(5) == ["hello"]
    assert transport.connected
    assert transport.last_error is None
    transport.close()
    assert port.closed


def test_disconnect_discards_partial_record_before_reconnect():
    first = Port(b"partial", OSError("removed"))
    second = Port(b"tail\n")
    ports = iter([first, second])
    transport = SerialTransport("chosen", 115200, 5, lambda *_: next(ports))
    assert transport.poll(0) == []
    assert transport.poll(1) == []
    assert first.closed and not transport.connected
    assert transport.poll(6) == ["tail"]


class WritePort(Port):
    """A connection whose write returns a count or raises a given error."""

    def __init__(self, *results):
        super().__init__()
        self.results = list(results)
        self.written = []

    def write(self, data):
        self.written.append(data)
        result = self.results.pop(0) if self.results else len(data)
        if isinstance(result, Exception):
            raise result
        return result


def connected(port):
    transport = SerialTransport("chosen", 115200, 5, lambda name, baud: port)
    transport.poll(0)
    assert transport.connected
    return transport


def test_send_writes_the_whole_line():
    port = WritePort()
    transport = connected(port)
    assert transport.send("ALARM,2\n") is True
    assert port.written == [b"ALARM,2\n"] and transport.last_send_error is None


def test_send_without_a_port_fails_without_opening_one():
    opened = []
    transport = SerialTransport("chosen", 115200, 5, lambda name, baud: opened.append(1))
    assert transport.send("ALARM,1\n") is False
    assert transport.last_send_error == "Serial port not connected."
    assert opened == []


def test_write_timeout_and_os_errors_are_returned_not_raised():
    from serial import SerialTimeoutException

    port = WritePort(SerialTimeoutException("Write timeout"), OSError("gone"), RuntimeError("bug"))
    transport = connected(port)
    assert transport.send("ALARM,2\n") is False
    assert transport.last_send_error == "Write timeout"
    assert transport.send("ALARM,2\n") is False
    assert transport.last_send_error == "gone"
    assert transport.send("ALARM,2\n") is False
    assert transport.last_send_error == "bug"
    assert transport.connected and transport.last_error is None


def test_short_write_fails_and_next_command_ends_the_fragment():
    port = WritePort(3)
    transport = connected(port)
    assert transport.send("ALARM,2\n") is False
    assert "3 of 8" in transport.last_send_error
    assert transport.send("ALARM,2\n") is True
    assert port.written[-1] == b"\nALARM,2\n"
    assert transport.send("ALARM,2\n") is True
    assert port.written[-1] == b"ALARM,2\n"


def test_reconnect_clears_the_resync_prefix():
    port = WritePort(OSError("timeout"))
    transport = connected(port)
    assert transport.send("ALARM,1\n") is False
    transport.close()
    transport.poll(10)
    assert transport.send("ALARM,1\n") is True
    assert port.written[-1] == b"ALARM,1\n"


def test_full_output_buffer_cannot_block_send():
    """Real pyserial on a pseudo-terminal whose reader never reads."""
    import os
    import pty
    import time

    from serial_transport import SERIAL_WRITE_TIMEOUT_S, open_serial_port

    master, slave = pty.openpty()
    try:
        transport = SerialTransport(os.ttyname(slave), 115200, 5, open_serial_port)
        transport.poll(0)
        assert transport.connected
        slowest = 0.0
        started = time.monotonic()
        while time.monotonic() - started < 10:
            before = time.monotonic()
            ok = transport.send("ALARM,2\n")
            slowest = max(slowest, time.monotonic() - before)
            if not ok:
                break
        assert not ok, "the pseudo-terminal buffer never filled"
        assert transport.last_send_error
        assert slowest < SERIAL_WRITE_TIMEOUT_S + 0.2
        before = time.monotonic()
        assert transport.send("ALARM,2\n") is False
        assert time.monotonic() - before < SERIAL_WRITE_TIMEOUT_S + 0.2
        transport.close()
    finally:
        os.close(master)
        os.close(slave)
