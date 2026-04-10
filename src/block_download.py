"""SDO Block Download module for Delta-Q firmware transfer.

Implements SDO block download protocol per CiA 301/302 and Delta-Q specifications.
Uses canopen library's BlockDownloadStream for proper CiA 301 block transfer.
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
    
    OBJ_PROGRAM_DATA = 0x1F50
    OBJ_PROGRAM_CONTROL = 0x1F51
    OBJ_PROGRAM_CRC = 0x1F56
    OBJ_FLASH_STATUS = 0x1F57
    
    SUB_PROGRAM_DATA = 0x01
    SUB_PROGRAM_CONTROL = 0x01
    SUB_FLASH_STATUS = 0x01
    
    BLOCK_SIZE = 0x7F
    FIRST_BLOCK_DELAY = 15.0
    SUBSEQUENT_BLOCK_DELAY = 0.5
    
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
        self.bus = bus
        self.node_id = node_id
        self.block_size = block_size
        self.timeout = timeout
        self.progress_callback = progress_callback
        
        self.network = canopen.Network()
        self.network.connect(interface='socketcan', channel=bus.channel)
        self.node = canopen.RemoteNode(node_id, None)
        self.network.add_node(self.node)
        
        self.node.sdo.RESPONSE_TIMEOUT = timeout
        
        self._state = BlockDownloadState.IDLE
        self._firmware_info: Optional[FirmwareInfo] = None
        self._bytes_transferred = 0
        self._current_block = 0
        self._total_blocks = 0
    
    @property
    def state(self) -> BlockDownloadState:
        return self._state
    
    def _update_progress(self):
        if self.progress_callback:
            progress = BlockDownloadProgress(
                total_bytes=self._firmware_info.file_size if self._firmware_info else 0,
                bytes_transferred=self._bytes_transferred,
                current_block=self._current_block,
                total_blocks=self._total_blocks
            )
            self.progress_callback(progress)
    
    def _send_program_control(self, command: int) -> bool:
        try:
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
    
    def _wait_for_stopped(self, max_attempts: int = 3) -> bool:
        """Wait for charger to report stopped status."""
        for _ in range(max_attempts):
            try:
                status = self.node.sdo.upload(self.OBJ_PROGRAM_CONTROL, self.SUB_PROGRAM_CONTROL)
                if status and status[0] == self.PROGRAM_STOP:
                    return True
            except canopen.SdoAbortedError:
                pass
            time.sleep(0.5)
        return False
    
    def _initiate_block_download(
        self,
        data_size: int,
        supports_crc: bool = True
    ) -> Tuple[int, bool]:
        """Initiate SDO block download per CiA 301."""
        try:
            response = self.node.sdo.upload(self.OBJ_PROGRAM_DATA, self.SUB_PROGRAM_DATA)
            
            if len(response) >= 5:
                server_block_size = response[4] & 0x7F
                server_crc_supported = (response[4] & 0x01) != 0
            else:
                server_block_size = self.block_size
                server_crc_supported = False
            
            size_data = data_size.to_bytes(4, 'little')
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
        """Transfer a block using canopen's BlockDownloadStream."""
        try:
            stream = canopen.sdo.client.BlockDownloadStream(
                self.node.sdo,
                self.OBJ_PROGRAM_DATA,
                self.SUB_PROGRAM_DATA,
                size=len(data),
                request_crc_support=True
            )
            
            stream.write(data)
            
            return True
            
        except canopen.SdoAbortedError as e:
            raise BlockDownloadError(f"Block data transfer abort: 0x{e.code:08X}")
        except canopen.SdoCommunicationError as e:
            raise BlockDownloadError(f"Block data transfer error: {e}")
        except Exception as e:
            raise BlockDownloadError(f"Block data transfer error: {e}")
    
    def _send_block_download_end(self, crc: Optional[int] = None) -> bool:
        """Send SDO Block Download End per CiA 301."""
        try:
            request = bytearray(8)
            
            if crc is not None:
                cmd = 0xC1 | 0x10
                crc_bytes = crc.to_bytes(4, 'little')
            else:
                cmd = 0xC1
                crc_bytes = bytes(4)
            
            request[0] = cmd
            
            import struct
            struct.pack_into("<I", request, 4, crc if crc is not None else 0)
            
            response = self.node.sdo.request_response(request)
            
            res_cmd = response[0] & 0xE0
            if res_cmd == 0xA0:
                return True
            elif res_cmd == 0x80:
                abort_code = int.from_bytes(response[4:8], 'little')
                raise BlockDownloadError(f"Block download end abort: 0x{abort_code:08X}")
            else:
                raise BlockDownloadError(f"Unexpected block download end response: 0x{response[0]:02X}")
                
        except canopen.SdoAbortedError as e:
            raise BlockDownloadError(f"Block download end abort: 0x{e.code:08X}")
        except canopen.SdoCommunicationError as e:
            raise BlockDownloadError(f"Block download end error: {e}")
    
    def _complete_block_download(self, crc: int) -> bool:
        """Complete block download with Block Download End message."""
        try:
            self._send_block_download_end(crc)
            
            time.sleep(1.0)
            
            status = self.node.sdo.upload(self.OBJ_FLASH_STATUS, self.SUB_FLASH_STATUS)
            
            if len(status) >= 4:
                status_value = int.from_bytes(status[:4], 'little')
                if status_value & 0x01:
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
        if firmware_loader.info is None:
            raise BlockDownloadError("Firmware not loaded")
        
        self._firmware_info = firmware_loader.info
        firmware_data = firmware_loader.data
        
        self._total_blocks = (len(firmware_data) + self.block_size - 1) // self.block_size
        
        self._state = BlockDownloadState.INITIATED
        self._bytes_transferred = 0
        self._current_block = 0
        
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                self._send_program_control(self.PROGRAM_STOP)
                time.sleep(0.1)
                
                if not self._wait_for_stopped():
                    raise BlockDownloadError("Charger did not stop within timeout")
                
                self._send_program_control(self.PROGRAM_CLEAR)
                time.sleep(1.0)
                
                server_block_size, server_crc_supported = self._initiate_block_download(
                    len(firmware_data),
                    supports_crc=True
                )
                
                actual_block_size = min(self.block_size, server_block_size * 7)
                
                self._state = BlockDownloadState.TRANSFERRING
                
                for block_num in range(self._total_blocks):
                    offset = block_num * actual_block_size
                    block_data = firmware_data[offset:offset + actual_block_size]
                    
                    while len(block_data) % 4 != 0:
                        block_data += b'\x00'
                    
                    self._transfer_block_data(block_data, block_num)
                    
                    self._current_block = block_num + 1
                    self._bytes_transferred = min(
                        (block_num + 1) * actual_block_size,
                        len(firmware_data)
                    )
                    self._update_progress()
                    
                    delay = self.FIRST_BLOCK_DELAY if block_num == 0 else self.SUBSEQUENT_BLOCK_DELAY
                    time.sleep(delay)
                
                self._complete_block_download(self._firmware_info.crc32)
                
                self._state = BlockDownloadState.COMPLETED
                return self._firmware_info
                
            except BlockDownloadError as e:
                last_error = e
                self._state = BlockDownloadState.FAILED
                
                if attempt < max_retries:
                    time.sleep(2.0)
                continue
        
        raise BlockDownloadError(
            f"Firmware download failed after {max_retries} attempts: {last_error}"
        )
    
    def cancel(self) -> bool:
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
    from .auth import authenticate_charger
    
    authenticate_charger(bus, node_id, customer_secret, timeout)
    
    loader = FirmwareLoader()
    loader.load(firmware_path)
    
    downloader = SDOBlockDownload(
        bus=bus,
        node_id=node_id,
        progress_callback=progress_callback,
        timeout=timeout
    )
    
    return downloader.download_firmware(loader)