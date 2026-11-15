"""The alarm path through the session and the monitor loop, with simulated I/O."""

import json

import pytest

from simulated_input import SimulatedTransport


def test_simulated_transport_echoes_alarm_commands_at_the_next_poll():
    transport = SimulatedTransport()
    transport.poll(0)
    assert transport.send("ALARM,2\n") is True
    assert transport.poll(0.05) == ['{"type": "alarm", "state": 2}']
    assert transport.poll(0.1) == []
    assert transport.send("\nALARM,1\n") is True
    assert transport.send("ALARM,7\n") is True
    assert transport.poll(0.15) == ['{"type": "alarm", "state": 1}']


def test_simulated_transport_can_stay_silent_or_fail():
    silent, failing = SimulatedTransport(alarm="silent"), SimulatedTransport(alarm="fail")
    assert silent.send("ALARM,2\n") is True and silent.poll(0)[-1].startswith('{"type": "dust"')
    assert failing.send("ALARM,2\n") is False
    assert failing.last_send_error == "Simulated write failure."
    with pytest.raises(ValueError):
        SimulatedTransport(alarm="other")
