"""SDO Protocol helpers for CANopen communication."""

import can
from typing import Optional, Tuple, List
from dataclasses import dataclass
from enum import IntEnum


class SDOCommand(IntEnum):
    """SDO Command Specifier values."""
    UPLOAD_INITIATE = 0x40
    UPLOAD_INITIATE_EXPEDITED = 0x43
    UPLOAD_SEGMENT = 0x60
    DOWNLOAD_INITIATE = 0x23
    DOWNLOAD_INITIATE_EXPEDITED = 0x2B
    DOWNLOAD_SEGMENT = 0x00
    ABORT = 0x80


# CANopen Object Indices
class ObjectIndex:
    """Standard CANopen object indices."""
    PROGRAM_DATA = 0x1F50
    PROGRAM_CONTROL = 0x1F51
    PROGRAM_CRC = 0x1F56
    FLASH_STATUS = 0x1F57
    
    # Authentication objects
    AUTH_SEED = 0x2400
    AUTH_KEY = 0x2400


@dataclass
class SDORequest:
    """SDO Request message builder."""
    command: int
    index: int
    subindex: int
    data: bytes = b''
    
    def to_message(self, node_id: int) -> can.Message:
        """Convert to CAN message."""
        # Build data: command, index (little-endian), subindex, data (up to 4 bytes)
        msg_data = [
            self.command,
            self.index & 0xFF,
            (self.index >> 8) & 0xFF,
            self.subindex,
        ]
        
        # Pad data to 8 bytes
        msg_data.extend(self.data[:4])
        while len(msg_data) < 8:
            msg_data.append(0x00)
        
        return can.Message(
            arbitration_id=0x600 + node_id,  # Client->Server COB-ID
            data=msg_data,
            is_extended_id=False
        )


@dataclass
class SDOResponse:
    """SDO Response message parser."""
    command: int
    index: int
    subindex: int
    data: bytes
    
    @property
    def is_abort(self) -> bool:
        """Check if this is an abort transfer."""
        return self.command == 0x80
    
    @property
    def abort_code(self) -> Optional[int]:
        """Get abort code if this is an abort."""
        if self.is_abort and len(self.data) >= 4:
            return int.from_bytes(self.data[:4], 'little')
        return None
    
    @property
    def is_expedited(self) -> bool:
        """Check if expedited transfer (data in response)."""
        return self.command in (0x43, 0x47, 0x4B, 0x4F)
    
    @property
    def expedited_data(self) -> Optional[bytes]:
        """Get expedited data if applicable."""
        if self.is_expedited and len(self.data) >= 4:
            return self.data[:4]
        return None


def parse_sdo_response(msg: can.Message) -> SDOResponse:
    """Parse incoming SDO response message."""
    if len(msg.data) < 4:
        raise ValueError("SDO response too short")
    
    command = msg.data[0]
    index = msg.data[1] | (msg.data[2] << 8)
    subindex = msg.data[3]
    data = msg.data[4:] if len(msg.data) > 4 else b''
    
    return SDOResponse(command=command, index=index, subindex=subindex, data=data)


def build_upload_request(index: int, subindex: int, node_id: int) -> can.Message:
    """Build SDO Upload Initiate Request."""
    request = SDORequest(
        command=SDOCommand.UPLOAD_INITIATE,
        index=index,
        subindex=subindex
    )
    return request.to_message(node_id)


def build_download_request(index: int, subindex: int, data: bytes, node_id: int) -> can.Message:
    """Build SDO Download Initiate Request."""
    if len(data) > 4:
        data = data[:4]
    
    command = 0x23 + ((4 - len(data)) << 2)
    
    request = SDORequest(
        command=command,
        index=index,
        subindex=subindex,
        data=data
    )
    return request.to_message(node_id)


def build_program_control_command(command: int, node_id: int) -> can.Message:
    """Build Program Control command (0x1F51:01).
    
    Args:
        command: 0x00 = Stop, 0x03 = Clear
    """
    return build_download_request(0x1F51, 0x01, bytes([command]), node_id)


def build_block_download_initiate(
    data_size: int,
    supports_crc: bool,
    node_id: int
) -> can.Message:
    """Build SDO Block Download Initiate (0x1F50:01).
    
    Args:
        data_size: Total size of data to download
        supports_crc: Whether client supports CRC
    """
    # Byte 0: command specifier (0xC6 = initiate, client supports CRC)
    cmd = 0xC6 if supports_crc else 0xC0
    
    data = bytes([
        data_size & 0xFF,
        (data_size >> 8) & 0xFF,
        (data_size >> 16) & 0xFF,
        (data_size >> 24) & 0xFF
    ])
    
    request = SDORequest(
        command=cmd,
        index=ObjectIndex.PROGRAM_DATA,
        subindex=0x01,
        data=data
    )
    return request.to_message(node_id)


def parse_block_download_response(msg: can.Message) -> Tuple[int, bool]:
    """Parse SDO Block Download Initiate Response.
    
    Returns:
        Tuple of (sub_block_size, crc_supported)
    """
    response = parse_sdo_response(msg)
    
    if response.is_abort:
        raise RuntimeError(f"Block download abort: 0x{response.abort_code:08X}")
    
    # Response format: 0xA4, index, subindex, sub-block size, ...
    sub_block_size = response.data[4] if len(response.data) > 4 else 0x7F
    crc_supported = (response.data[4] & 0x01) != 0 if len(response.data) > 4 else False
    
    return sub_block_size, crc_supported


def parse_flash_status(msg: can.Message) -> dict:
    """Parse Flash Programming Status (0x1F57:01).
    
    Returns:
        Dict with status bits decoded
    """
    response = parse_sdo_response(msg)
    
    if len(response.data) < 4:
        return {"raw": 0, "error": "Invalid response"}
    
    status = int.from_bytes(response.data[:4], 'little')
    
    return {
        "raw": status,
        "in_progress": bool(status & 0x01),
        "error_code": (status >> 1) & 0x7F,
        "dqt_error": (status >> 16) & 0xFFFFFFFF,
    }
