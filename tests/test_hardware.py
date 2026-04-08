"""Hardware integration tests using canopen-python library.

These tests require:
- SLCan adapter (or compatible CAN adapter)
- Delta-Q charger (ICL, RC, or similar) connected to CAN bus
- 120Ω termination on CAN bus

Hardware setup:
1. Connect CAN adapter to laptop (USB)
2. Connect CAN adapter to Delta-Q charger CAN port (DB9 or CAN pigtail)
3. Ensure 120Ω termination (internal or external)
4. Note the serial port: /dev/ttyACM0, /dev/ttyUSB0, etc.

Compatible Delta-Q chargers:
- ICL (International AC Level)
- RC (Rugged Compact)
- TerraCharge (same reprogramming interface)

Run with: CAN_HW_TEST=1 python -m pytest tests/test_hardware.py -v -s
"""

import pytest
import can
import canopen
import time
import os

from src.auth import AuthenticationError


# Skip all hardware tests if no hardware flag is set
pytestmark = pytest.mark.skipif(
    os.environ.get("CAN_HW_TEST") != "1",
    reason="Hardware tests require CAN_HW_TEST=1 and physical hardware"
)


class TestCanopenConnection:
    """Test canopen library with hardware."""
    
    @pytest.fixture
    def network(self):
        """Create canopen network."""
        bus = can.Bus(
            interface='slcan',
            channel='/dev/ttyACM0',
            bitrate=500000,
            timeout=2.0
        )
        
        net = canopen.Network(bus)
        node = canopen.RemoteNode(10, '')  # Node ID 10
        net.add_node(node)
        
        yield node
        
        net.sync = 0
        bus.shutdown()
    
    def test_network_creation(self, network):
        """Test network and node creation."""
        assert network is not None
        print(f"Node ID: {network.id}")
    
    def test_heartbeat(self, network):
        """Test receiving heartbeat from charger."""
        # Wait for heartbeat
        time.sleep(0.5)
        
        # Check node state
        state = network.state
        print(f"Node state: {state}")


class TestCanopenSDO:
    """Test SDO operations using canopen."""
    
    @pytest.fixture
    def node(self):
        """Create canopen node."""
        bus = can.Bus(
            interface='slcan',
            channel='/dev/ttyACM0',
            bitrate=500000,
            timeout=2.0
        )
        
        net = canopen.Network(bus)
        node = canopen.RemoteNode(10, '')
        net.add_node(node)
        
        yield node
        
        bus.shutdown()
    
    def test_read_device_type(self, node):
        """Read standard device type (0x1000)."""
        try:
            device_type = node.sdo.upload(0x1000, 0)
            print(f"Device type: 0x{device_type.hex()}")
            assert len(device_type) > 0
        except canopen.SdoCommunicationError as e:
            pytest.skip(f"Communication error: {e}")
    
    def test_read_manufacturer(self, node):
        """Read manufacturer (0x1018)."""
        try:
            mfr = node.sdo.upload(0x1018, 1)
            print(f"Manufacturer ID: 0x{mfr.hex()}")
            assert len(mfr) >= 4
        except canopen.SdoCommunicationError as e:
            pytest.skip(f"Communication error: {e}")


class TestCanopenAuthentication:
    """Test authentication using canopen SDO client."""
    
    @pytest.fixture
    def node(self):
        """Create canopen node."""
        bus = can.Bus(
            interface='slcan',
            channel='/dev/ttyACM0',
            bitrate=500000,
            timeout=2.0
        )
        
        net = canopen.Network(bus)
        node = canopen.RemoteNode(10, '')
        net.add_node(node)
        
        yield node
        
        bus.shutdown()
    
    def test_read_seed(self, node):
        """Read authentication seed (0x2400:01)."""
        try:
            seed_bytes = node.sdo.upload(0x2400, 0x01)
            seed_value = int.from_bytes(seed_bytes, 'little')
            print(f"Seed: 0x{seed_value:04X}")
            assert seed_value != 0
        except canopen.SdoAbortedError as e:
            abort_codes = {
                0x06020000: "Object not found",
                0x06040042: "Data type mismatch", 
                0x08000000: "General error",
            }
            msg = abort_codes.get(e.code, f"Unknown: 0x{e.code:08X}")
            pytest.skip(f"Seed read not supported: {msg}")
        except canopen.SdoCommunicationError as e:
            pytest.skip(f"Communication error: {e}")
    
    def test_write_key(self, node):
        """Test writing key (0x2400:02)."""
        try:
            # Read seed first
            seed_bytes = node.sdo.upload(0x2400, 0x01)
            seed_value = int.from_bytes(seed_bytes, 'little')
            
            # Calculate key (need customer secret - check with Delta-Q)
            customer_secret = os.environ.get('CAN_DQT_SECRET', '0x1234')
            secret = int(customer_secret, 0) if customer_secret.startswith('0x') else int(customer_secret)
            key_value = calculate_key(seed_value, secret)
            
            # Write key
            key_bytes = key_value.to_bytes(2, 'little')
            node.sdo.download(0x2400, 0x02, key_bytes)
            
            print(f"Key written: 0x{key_value:04X}")
            
        except canopen.SdoAbortedError as e:
            pytest.skip(f"Key write failed: 0x{e.code:08X}")
        except canopen.SdoCommunicationError as e:
            pytest.skip(f"Communication error: {e}")


class TestCanopenProgramControl:
    """Test program control via canopen."""
    
    @pytest.fixture
    def node(self):
        bus = can.Bus(
            interface='slcan',
            channel='/dev/ttyACM0',
            bitrate=500000,
            timeout=2.0
        )
        net = canopen.Network(bus)
        node = canopen.RemoteNode(10, '')
        net.add_node(node)
        yield node
        bus.shutdown()
    
    def test_read_program_control(self, node):
        """Read program control status (0x1F51:01)."""
        try:
            status = node.sdo.upload(0x1F51, 0x01)
            status_val = status[0] if len(status) > 0 else 0
            print(f"Program control: 0x{status_val:02X}")
        except canopen.SdoAbortedError as e:
            pytest.skip(f"Not supported: 0x{e.code:08X}")
    
    def test_write_program_control_stop(self, node):
        """Write stop command (0x00)."""
        try:
            node.sdo.download(0x1F51, 0x01, b'\x00')
            print("Stop command sent")
            time.sleep(0.5)
            
            # Read status
            status = node.sdo.upload(0x1F51, 0x01)
            print(f"Status after stop: 0x{status[0]:02X}")
        except canopen.SdoAbortedError as e:
            pytest.skip(f"Stop not supported: 0x{e.code:08X}")


class TestCanopenFlashStatus:
    """Test flash status reading."""
    
    @pytest.fixture
    def node(self):
        bus = can.Bus(
            interface='slcan', 
            channel='/dev/ttyACM0',
            bitrate=500000,
            timeout=2.0
        )
        net = canopen.Network(bus)
        node = canopen.RemoteNode(10, '')
        net.add_node(node)
        yield node
        bus.shutdown()
    
    def test_read_flash_status(self, node):
        """Read flash status (0x1F57:01)."""
        try:
            status = node.sdo.upload(0x1F57, 0x01)
            status_val = int.from_bytes(status[:4], 'little')
            
            in_progress = status_val & 0x01
            error_code = (status_val >> 1) & 0x7F
            
            print(f"Flash status: 0x{status_val:08X}")
            print(f"  In progress: {in_progress}")
            print(f"  Error code: {error_code}")
            
        except canopen.SdoAbortedError as e:
            pytest.skip(f"Flash status not supported: 0x{e.code:08X}")


# Helper function - matches the one in src/auth.py
def calculate_key(seed: int, customer_secret: int) -> int:
    """Calculate key from seed using Delta-Q algorithm."""
    start = (seed & 0xFFFF) + (customer_secret & 0xFFFF)
    
    bit_15 = (start >> 15) & 1
    bit_7 = (start >> 7) & 1
    bit_4 = (start >> 4) & 1
    bit_0 = start & 1
    
    steps = (bit_15 * 8) + (bit_7 * 4) + (bit_4 * 2) + bit_0 + 1
    
    seed_word = start & 0xFFFF
    
    for _ in range(steps):
        bit_7 = (seed_word >> 7) & 1
        bit_2 = (seed_word >> 2) & 1
        nandbit = 0 if (bit_7 & bit_2) else 1
        
        bit_6 = (seed_word >> 6) & 1
        bit_9 = (seed_word >> 9) & 1
        bit_5 = (seed_word >> 5) & 1
        bit_0 = seed_word & 1
        xorbit = bit_6 ^ bit_9 ^ bit_5 ^ bit_0
        
        seed_word = (seed_word >> 1) & 0xFFFF
        if nandbit:
            seed_word |= 0x80
        if xorbit:
            seed_word |= 0x400
    
    return seed_word


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])