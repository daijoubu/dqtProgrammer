"""pytest configuration and fixtures for CAN bus testing.

Uses python-can's virtual interface by default — works on all platforms with no
kernel modules. Set CAN_TEST_INTERFACE to a real channel (e.g. can0) and
CAN_INTERFACE to socketcan/pcan/etc. to run against hardware.
"""

import os
import pytest
import can
import canopen


CAN_INTERFACE = os.environ.get('CAN_TEST_INTERFACE', 'test_channel')


@pytest.fixture(scope='session')
def can_interface():
    yield CAN_INTERFACE


@pytest.fixture
def can_bus(can_interface):
    bus = can.Bus(
        interface='virtual',
        channel=can_interface,
        receive_own_messages=True,
    )
    yield bus
    bus.shutdown()


@pytest.fixture
def can_network(can_interface):
    network = canopen.Network()
    network.connect(interface='virtual', channel=can_interface)
    yield network
    try:
        network.disconnect()
    except Exception:
        pass
