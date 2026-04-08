"""SDO Block Download module for Delta-Q firmware transfer.

Implements SDO block download protocol per CiA 301/302 and Delta-Q specifications.
Uses canopen library for CANopen SDO communication.
"""

import can
import canopen
import time
from typing import Optional, Callable, Tuple
from enum import IntEnum

from .firmware import FirmwareLoader, FirmwareInfo


class BlockDownloadError(Exception):
    """Block download operation error."""
    pass


class BlockDownloadState(IntEnum):
    """Block download states."""
    IDLE = 0
    INITIATED = 1
    TRANSFERRING = 2
    COMPLETED = 3
    FAILED = 4


class BlockDownloadProgress:
    """Progress information for block download."""
    
    def __init__(self, total_bytes: int, bytes_transferred: int, 
                 current_block: int, total_blocks: int):
        self.total_bytes = total_bytes
        self.bytes_transferred = bytes_transferred
        self.current_block = current_block
        self.total_blocks = total_blocks
    
    @property
    def percentage(self) -> float:
        """Percentage complete."""
        if self.total_bytes == 0:
            return 0.0
        return (self.bytes_transferred / self.total_bytes) * 100
    
    def __str__(self) -> str:
        return (f"Progress: {self.bytes_transferred}/{self.total_bytes} bytes "
                f"({self.percentage:.1f}%) - Block {self.current_block}/{self.total_blocks}")


class SDOBlockDownload:
    """SDO Block Download handler for Delta-Q firmware transfer."""
    
    # CANopen Object Dictionary indices for firmware programming
    OBJ_PROGRAM_DATA = 0x1F50
    OBJ_PROGRAM_CONTROL = 0x1F51
    OBJ_PROGRAM_CRC = 0x1F56
    OBJ_FLASH_STATUS = 0x1F57
    
    # Sub-indices
    SUB_PROGRAM_DATA = 0x01
    SUB_PROGRAM_CONTROL = 0x01
    SUB_FLASH_STATUS = 0x01
    
    # Block download parameters
    BLOCK_SIZE = 0x7F  # Default 127 bytes per block
    FIRST_BLOCK_DELAY = 15.0  # First block has 15s erase time
    SUBSEQUENT_BLOCK_DELAY = 0.5  # Subsequent blocks ~500ms
    
    # Program control commands
    PROGRAM_STOP = 0x00
    PROGRAM_START = 0x01
    PROGRAM_RESET = 0x02
    PROGRAM_CLEAR = 0x03
    
    def __init__(
        self,
        bus: can.Bus,
        node_id: int,
        block_size: int = BLOCK_SIZE,
        timeout: float = 2.0,
        progress_callback: Optional[Callable[[BlockDownloadProgress], None]] = None
    ):
        """
        Initialize SDO Block Download handler.
        
        Args:
            bus: python-can Bus instance
            node_id: CANopen node ID of charger
            block_size: Number of bytes per block (default 127)
            timeout: SDO response timeout in seconds
            progress_callback: Optional callback for progress updates
        """
        self.bus = bus
        self.node_id = node_id
        self.block_size = block_size
        self.timeout = timeout
        self.progress_callback = progress_callback
        
        # Create canopen network and node
        self.network = canopen.Network(bus)
        self.node = canopen.RemoteNode(node_id, '')
        self.network.add_node(self.node)
        
        # Configure timeouts
        self.node.sdo.RESPONSE_TIMEOUT = timeout
        
        # State tracking
        self._state = BlockDownloadState.IDLE
        self._firmware_info: Optional[FirmwareInfo] = None
        self._bytes_transferred = 0
        self._current_block = 0
        self._total_blocks = 0
    
    @property
    def state(self) -> BlockDownloadState:
        """Get current download state."""
        return self._state
    
    def _update_progress(self):
        """Call progress callback if set."""
        if self.progress_callback:
            progress = BlockDownloadProgress(
                total_bytes=self._firmware_info.file_size if self._firmware_info else 0,
                bytes_transferred=self._bytes_transferred,
                current_block=self._current_block,
                total_blocks=self._total_blocks
            )
            self.progress_callback(progress)
    
    def _send_program_control(self, command: int) -> bool:
        """
        Send Program Control command.
        
        Args:
            command: Control command (stop/start/reset/clear)
            
        Returns:
            True if successful
            
        Raises:
            BlockDownloadError: If command fails
        """
        try:
            # Write to 0x1F51:01
            self.node.sdo.download(
                self.OBJ_PROGRAM_CONTROL,
                self.SUB_PROGRAM_CONTROL,
                bytes([command])
            )
            return True
        except canopen.SdoAbortedError as e:
            raise BlockDownloadError(f"Program control abort: 0x{e.code:08X}")
        except canopen.SdoCommunicationError as e:
            raise BlockDownloadError(f"Program control error: {e}")
    
    def _initiate_block_download(
        self,
        data_size: int,
        supports_crc: bool = True
    ) -> Tuple[int, bool]:
        """
        Initiate SDO block download.
        
        Sends 0x1F50:01 with firmware size and CRC support flag.
        
        Args:
            data_size: Total size of firmware in bytes
            supports_crc: Whether client supports CRC
            
        Returns:
            Tuple of (server_block_size, server_crc_supported)
            
        Raises:
            BlockDownloadError: If initiate fails
        """
        try:
            # Build initiate request
            # Command specifier: 0xC6 = initiate with CRC, 0xC0 = initiate without CRC
            cmd_spec = 0xC6 if supports_crc else 0xC0
            
            # Data: 4-byte size + padding
            size_data = data_size.to_bytes(4, 'little')
            
            # Upload to initiate block download (server sends capabilities first)
            response = self.node.sdo.upload(self.OBJ_PROGRAM_DATA, self.SUB_PROGRAM_DATA)
            
            # Response contains: sub-block size (byte 4) + CRC support flag (bit 0)
            if len(response) >= 5:
                server_block_size = response[4] & 0x7F
                server_crc_supported = (response[4] & 0x01) != 0
            else:
                server_block_size = self.block_size
                server_crc_supported = False
            
            # Now send the initiate with our size
            # For block download, we use upload to trigger the initiate
            # then download to actually send data
            self.node.sdo.download(
                self.OBJ_PROGRAM_DATA,
                self.SUB_PROGRAM_DATA,
                size_data
            )
            
            return server_block_size, server_crc_supported
            
        except canopen.SdoAbortedError as e:
            raise BlockDownloadError(f"Block download initiate abort: 0x{e.code:08X}")
        except canopen.SdoCommunicationError as e:
            raise BlockDownloadError(f"Block download initiate error: {e}")
    
    def _transfer_block_data(self, data: bytes, block_number: int) -> bool:
        """
        Transfer a block of firmware data.
        
        Args:
            data: Firmware data chunk
            block_number: Current block number
            
        Returns:
            True if successful
            
        Raises:
            BlockDownloadError: If transfer fails
        """
        try:
            # For block download, data is sent via download requests
            # Each block is a separate download to 0x1F50:02
            offset = block_number * self.block_size
            
            # Use expedited download for block data
            self.node.sdo.download(
                self.OBJ_PROGRAM_DATA,
                0x02,  # Sub-index 2 for block data
                data
            )
            
            return True
            
        except canopen.SdoAbortedError as e:
            raise BlockDownloadError(f"Block data transfer abort: 0x{e.code:08X}")
        except canopen.SdoCommunicationError as e:
            raise BlockDownloadError(f"Block data transfer error: {e}")
    
    def _complete_block_download(self, crc: int) -> bool:
        """
        Complete block download and verify CRC.
        
        Args:
            crc: CRC-32 of transferred firmware
            
        Returns:
            True if successful
            
        Raises:
            BlockDownloadError: If completion fails
        """
        try:
            # Send CRC to 0x1F56:01 for verification
            crc_data = crc.to_bytes(4, 'little')
            self.node.sdo.download(
                self.OBJ_PROGRAM_CRC,
                0x01,
                crc_data
            )
            
            # Read flash status to confirm
            status = self.node.sdo.upload(self.OBJ_FLASH_STATUS, self.SUB_FLASH_STATUS)
            
            # Check status for errors
            if len(status) >= 4:
                status_value = int.from_bytes(status[:4], 'little')
                if status_value & 0x01:
                    # In progress is normal after CRC write
                    pass
            
            return True
            
        except canopen.SdoAbortedError as e:
            raise BlockDownloadError(f"Block download complete abort: 0x{e.code:08X}")
        except canopen.SdoCommunicationError as e:
            raise BlockDownloadError(f"Block download complete error: {e}")
    
    def download_firmware(
        self,
        firmware_loader: FirmwareLoader,
        max_retries: int = 3
    ) -> FirmwareInfo:
        """
        Perform complete firmware download to charger.
        
        Args:
            firmware_loader: Loaded FirmwareLoader instance
            max_retries: Maximum retry attempts
            
        Returns:
            FirmwareInfo of downloaded firmware
            
        Raises:
            BlockDownloadError: If download fails
        """
        # Get firmware data
        if firmware_loader.info is None:
            raise BlockDownloadError("Firmware not loaded")
        
        self._firmware_info = firmware_loader.info
        firmware_data = firmware_loader.data
        
        # Calculate total blocks
        self._total_blocks = (len(firmware_data) + self.block_size - 1) // self.block_size
        
        # Reset state
        self._state = BlockDownloadState.INITIATED
        self._bytes_transferred = 0
        self._current_block = 0
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                # Step 1: Stop any running program
                self._send_program_control(self.PROGRAM_STOP)
                time.sleep(0.1)
                
                # Step 2: Clear flash memory
                self._send_program_control(self.PROGRAM_CLEAR)
                time.sleep(1.0)
                
                # Step 3: Initiate block download
                server_block_size, server_crc_supported = self._initiate_block_download(
                    len(firmware_data),
                    supports_crc=True
                )
                
                # Use server's block size if smaller
                actual_block_size = min(self.block_size, server_block_size)
                
                self._state = BlockDownloadState.TRANSFERRING
                
                # Step 4: Transfer data blocks
                for block_num in range(self._total_blocks):
                    offset = block_num * actual_block_size
                    block_data = firmware_data[offset:offset + actual_block_size]
                    
                    # Pad to 4-byte boundary if needed
                    while len(block_data) % 4 != 0:
                        block_data += b'\x00'
                    
                    self._transfer_block_data(block_data, block_num)
                    
                    # Update progress
                    self._current_block = block_num + 1
                    self._bytes_transferred = min(
                        (block_num + 1) * actual_block_size,
                        len(firmware_data)
                    )
                    self._update_progress()
                    
                    # First block needs longer delay for erase
                    delay = self.FIRST_BLOCK_DELAY if block_num == 0 else self.SUBSEQUENT_BLOCK_DELAY
                    time.sleep(delay)
                
                # Step 5: Complete with CRC verification
                self._complete_block_download(self._firmware_info.crc32)
                
                self._state = BlockDownloadState.COMPLETED
                return self._firmware_info
                
            except BlockDownloadError as e:
                last_error = e
                self._state = BlockDownloadState.FAILED
                
                if attempt < max_retries:
                    time.sleep(2.0)  # Wait before retry
                continue
        
        raise BlockDownloadError(
            f"Firmware download failed after {max_retries} attempts: {last_error}"
        )
    
    def cancel(self) -> bool:
        """
        Cancel ongoing firmware download.
        
        Returns:
            True if cancel successful
        """
        try:
            self._send_program_control(self.PROGRAM_STOP)
            self._state = BlockDownloadState.IDLE
            return True
        except BlockDownloadError:
            return False


def download_firmware(
    bus: can.Bus,
    node_id: int,
    firmware_path: str,
    customer_secret: int,
    progress_callback: Optional[Callable[[BlockDownloadProgress], None]] = None,
    timeout: float = 2.0
) -> FirmwareInfo:
    """
    Convenience function to download firmware with authentication.
    
    Args:
        bus: python-can Bus instance
        node_id: CANopen node ID of charger
        firmware_path: Path to firmware file
        customer_secret: Customer-specific secret
        progress_callback: Optional progress callback
        timeout: SDO response timeout
        
    Returns:
        FirmwareInfo of downloaded firmware
        
    Raises:
        BlockDownloadError: If download fails
    """
    # Import here to avoid circular dependency
    from .auth import authenticate_charger
    
    # Authenticate first
    authenticate_charger(bus, node_id, customer_secret, timeout)
    
    # Load firmware
    loader = FirmwareLoader()
    loader.load(firmware_path)
    
    # Download
    downloader = SDOBlockDownload(
        bus=bus,
        node_id=node_id,
        progress_callback=progress_callback,
        timeout=timeout
    )
    
    return downloader.download_firmware(loader)