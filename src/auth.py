"""SDO Authentication module for Delta-Q CANopen reprogramming.

Uses canopen-python library for CANopen SDO communication.
"""

import can
import canopen
import time
from typing import Optional


class AuthenticationError(Exception):
    """Authentication failure exception."""
    pass


class SDOAuthentication:
    """Handles SDO authentication sequence with Delta-Q charger using canopen."""
    
    def __init__(self, bus: can.Bus, node_id: int, customer_secret: int, timeout: float = 2.0):
        """
        Initialize authentication handler.
        
        Args:
            bus: python-can Bus instance
            node_id: CANopen node ID of charger
            customer_secret: Customer-specific 16-bit secret
            timeout: Response timeout in seconds
        """
        self.bus = bus
        self.node_id = node_id
        self.customer_secret = customer_secret & 0xFFFF
        self.timeout = timeout
        
        # Use the caller's bus — works with any python-can backend.
        # connect() is called separately because Network(bus) sets self.bus
        # but does not create the Notifier; connect() skips bus creation when
        # self.bus is already set and only creates the Notifier.
        self.network = canopen.Network(bus)
        self.network.connect()
        self.node = canopen.RemoteNode(node_id, None)
        self.network.add_node(self.node)
        
        # Configure timeout
        self.node.sdo.RESPONSE_TIMEOUT = timeout
    
    def _calculate_key(self, seed: int) -> int:
        """
        Calculate key from seed using Delta-Q algorithm.
        
        Translates C implementation to Python:
        - Input: seed (lower 16 bits) + customer_secret
        - Output: 16-bit key
        - Uses NAND and XOR bit operations in a loop
        """
        start = (seed & 0xFFFF) + self.customer_secret
        
        # Calculate number of steps based on bit positions
        bit_15 = (start >> 15) & 1
        bit_7 = (start >> 7) & 1
        bit_4 = (start >> 4) & 1
        bit_0 = start & 1
        
        steps = (bit_15 * 8) + (bit_7 * 4) + (bit_4 * 2) + bit_0 + 1
        
        seed_word = start & 0xFFFF
        
        for _ in range(steps):
            # NAND of bit 7 and bit 2
            bit_7 = (seed_word >> 7) & 1
            bit_2 = (seed_word >> 2) & 1
            nandbit = 0 if (bit_7 & bit_2) else 1
            
            # XOR of bit 6, bit 9, bit 5, bit 0
            bit_6 = (seed_word >> 6) & 1
            bit_9 = (seed_word >> 9) & 1
            bit_5 = (seed_word >> 5) & 1
            bit_0 = seed_word & 1
            xorbit = bit_6 ^ bit_9 ^ bit_5 ^ bit_0
            
            # Shift right and insert new bits
            seed_word = (seed_word >> 1) & 0xFFFF
            if nandbit:
                seed_word |= 0x80
            if xorbit:
                seed_word |= 0x400
        
        return seed_word
    
    def authenticate(self) -> bool:
        """
        Perform full authentication sequence.
        
        Returns:
            True if authentication successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Step 1: Read seed (0x2400:01)
            seed_bytes = self.node.sdo.upload(0x2400, 0x01)
            seed_value = int.from_bytes(seed_bytes, 'little')
            
            # Step 2: Calculate key
            key_value = self._calculate_key(seed_value)
            
            # Step 3: Write key (0x2400:02)
            key_bytes = key_value.to_bytes(2, 'little')
            self.node.sdo.download(0x2400, 0x02, key_bytes)
            
            return True
            
        except canopen.SdoAbortedError as e:
            raise AuthenticationError(f"SDO Abort: 0x{e.code:08X}")
        except canopen.SdoCommunicationError as e:
            raise AuthenticationError(f"Communication error: {e}")


def authenticate_charger(
    bus: can.Bus,
    node_id: int,
    customer_secret: int,
    timeout: float = 2.0,
    max_retries: int = 3
) -> bool:
    """
    Authenticate with Delta-Q charger with retry logic.
    
    Args:
        bus: python-can Bus instance
        node_id: CANopen node ID of charger
        customer_secret: Customer-specific secret
        timeout: Response timeout in seconds
        max_retries: Maximum authentication attempts before lockout
        
    Returns:
        True if authentication successful
        
    Raises:
        AuthenticationError: If authentication fails after all retries
    """
    for attempt in range(1, max_retries + 1):
        auth = SDOAuthentication(bus, node_id, customer_secret, timeout)
        try:
            result = auth.authenticate()
            return result
        except AuthenticationError as e:
            if attempt >= max_retries:
                raise AuthenticationError(
                    f"Authentication failed after {max_retries} attempts: {e}"
                )
            time.sleep(0.5)
        finally:
            # Stop the Notifier without shutting down the caller's bus.
            # python-can 4.4+ raises ValueError if the same bus is registered
            # with two active Notifiers, which happens when block_download creates
            # its own canopen.Network immediately after authentication.
            if auth.network.notifier is not None:
                auth.network.notifier.stop(0.5)
                auth.network.notifier = None

    return False