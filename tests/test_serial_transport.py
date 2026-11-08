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
