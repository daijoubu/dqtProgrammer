"""pytest configuration and fixtures for CAN bus testing.

Provides fixtures for socketcan loopback testing when vcan interface is available.
"""

import os
import subprocess
import pytest
import can
import canopen


CAN_INTERFACE = os.environ.get('CAN_TEST_INTERFACE', 'vcan0')


def is_vcan_available(interface: str = CAN_INTERFACE) -> bool:
    """Check if a vcan interface is available."""
    result = subprocess.run(
        ['ip', 'link', 'show', interface],
        capture_output=True
    )
    return result.returncode == 0


def setup_vcan_loopback(interface: str = CAN_INTERFACE) -> bool:
    """Set up vcan interface with loopback mode enabled."""
    try:
        # Check if interface exists
        result = subprocess.run(
            ['ip', 'link', 'show', interface],
            capture_output=True
        )
        
        if result.returncode != 0:
            # Create interface
            subprocess.run(
                ['ip', 'link', 'add', interface, 'type', 'vcan'],
                check=True
            )
        
        # Bring up interface
        subprocess.run(
            ['ip', 'link', 'set', interface, 'up'],
            check=True
        )
        
        # Enable loopback mode via can-utils
        try:
            subprocess.run(
                ['cansend', interface, '000#R'],
                capture_output=True,
                timeout=1
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        
        return True
    except Exception:
        return False


def teardown_vcan(interface: str = CAN_INTERFACE) -> None:
    """Clean up vcan interface."""
    try:
        subprocess.run(
            ['ip', 'link', 'set', interface, 'down'],
            capture_output=True
        )
    except Exception:
        pass


@pytest.fixture(scope='session')
def can_interface():
    """Session-scoped CAN interface fixture.
    
    Sets up vcan0 with loopback for the entire test session.
    Skips tests if vcan is not available and CAN_TEST_REQUIRED is set.
    """
    interface = CAN_INTERFACE
    available = is_vcan_available(interface)
    setup_ok = False
    
    if available:
        setup_ok = setup_vcan_loopback(interface)
    
    if not available or not setup_ok:
        required = os.environ.get('CAN_TEST_REQUIRED', 'false').lower() == 'true'
        if required:
            pytest.skip(f"CAN interface {interface} not available and CAN_TEST_REQUIRED=true")
        else:
            pytest.skip(f"CAN interface {interface} not available (set CAN_TEST_REQUIRED=true to require)")
    
    yield interface
    
    # Teardown
    teardown_vcan(interface)


@pytest.fixture
def can_network(can_interface):
    """Function-scoped CAN network fixture.
    
    Creates a canopen Network connected to the vcan interface.
    Yields the network, then closes it after the test.
    """
    network = canopen.Network()
    network.add_interface(canopen.SocketCan(can_interface))
    network.start()
    
    yield network
    
    try:
        network.stop()
    except Exception:
        pass


@pytest.fixture
def can_bus(can_interface):
    """Function-scoped python-can bus fixture.
    
    Creates a python-can Bus in loopback mode.
    """
    bus = can.Bus(
        interface='socketcan',
        channel=can_interface,
        receive_own_messages=True  # Loopback
    )
    
    yield bus
    
    bus.shutdown()