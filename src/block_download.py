"""SDO Block Download module for Delta-Q firmware transfer.

Implements SDO block download protocol per CiA 301/302 and Delta-Q specifications.
Uses canopen library's BlockDownloadStream for proper CiA 301 block transfer.
"""

import can
import canopen
import time
from typing import Optional, Callable
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
    FIRST_BLOCK_DELAY = 60.0
    
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

                self._state = BlockDownloadState.TRANSFERRING

                # Flash erase on first block can take many seconds; boost timeout
                # for entire block transfer so we don't abort prematurely.
                # Throttle inter-frame gap: charger buffers ~22 segments (~154 bytes)
                # at 125 kbps; blasting 127 frames back-to-back overruns it.
                self.node.sdo.RESPONSE_TIMEOUT = self.FIRST_BLOCK_DELAY
                self.node.sdo.PAUSE_BEFORE_SEND = 0.005  # 5ms between frames
                chunk_size = self.block_size * 7  # one sub-block = 889 bytes
                _block_start = time.time()
                try:
                    with self.node.sdo.open(
                        self.OBJ_PROGRAM_DATA,
                        self.SUB_PROGRAM_DATA,
                        'wb',
                        size=len(firmware_data),
                        block_transfer=True,
                        request_crc_support=False
                    ) as fp:
                        offset = 0
                        while offset < len(firmware_data):
                            chunk = firmware_data[offset:offset + chunk_size]
                            fp.write(chunk)
                            offset += len(chunk)
                            self._bytes_transferred = offset
                            self._current_block = offset // chunk_size
                            self._update_progress()
                except canopen.SdoCommunicationError as e:
                    elapsed = time.time() - _block_start
                    print(f"[DEBUG] Block transfer timed out after {elapsed:.1f}s waiting for ACK")
                    raise
                finally:
                    self.node.sdo.RESPONSE_TIMEOUT = self.timeout
                    self.node.sdo.PAUSE_BEFORE_SEND = 0.0
                
                self._state = BlockDownloadState.COMPLETED
                return self._firmware_info
                
            except BlockDownloadError as e:
                print(f"[DEBUG] BlockDownloadError: {e}")
                last_error = e
                self._state = BlockDownloadState.FAILED
                
                if attempt < max_retries:
                    time.sleep(2.0)
                continue
            except Exception as e:
                print(f"[DEBUG] Unexpected error: {type(e).__name__}: {e}")
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
    customer_secret: Optional[int] = None,
    progress_callback: Optional[Callable[[BlockDownloadProgress], None]] = None,
    timeout: float = 2.0
) -> FirmwareInfo:
    # Authentication is optional - Delta-Q allows reprogramming without it
    if customer_secret is not None:
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