"""Firmware loading and validation module for Delta-Q CANopen reprogramming.

Handles loading firmware binary files, calculating sizes for SDO headers,
and computing CRC for firmware integrity verification.
"""

import os
import struct
from typing import Optional, Tuple
from dataclasses import dataclass


class FirmwareError(Exception):
    """Firmware loading/validation error."""
    pass


@dataclass
class FirmwareInfo:
    """Firmware file metadata."""
    file_path: str
    file_size: int
    crc32: int
    version: Optional[str] = None
    model: Optional[str] = None


class FirmwareLoader:
    """Loads and validates Delta-Q firmware files."""
    
    # Delta-Q firmware file header magic and expected structure
    FILE_HEADER_MAGIC = 0x44415600  # 'DAV\0'
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB max firmware size
    
    def __init__(self):
        """Initialize firmware loader."""
        self._firmware_data: Optional[bytes] = None
        self._firmware_info: Optional[FirmwareInfo] = None
    
    def load(self, file_path: str) -> FirmwareInfo:
        """
        Load and validate a firmware file.
        
        Args:
            file_path: Path to firmware binary file
            
        Returns:
            FirmwareInfo with file metadata
            
        Raises:
            FirmwareError: If file is invalid or corrupted
        """
        if not os.path.exists(file_path):
            raise FirmwareError(f"Firmware file not found: {file_path}")
        
        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise FirmwareError("Firmware file is empty")
        if file_size > self.MAX_FILE_SIZE:
            raise FirmwareError(f"Firmware file too large: {file_size} bytes (max {self.MAX_FILE_SIZE})")
        
        # Read firmware data
        with open(file_path, 'rb') as f:
            self._firmware_data = f.read()
        
        # Calculate CRC32
        crc32 = self._calculate_crc32(self._firmware_data)
        
        # Try to extract version from header (if present)
        version = self._extract_version()
        model = self._extract_model()
        
        self._firmware_info = FirmwareInfo(
            file_path=file_path,
            file_size=file_size,
            crc32=crc32,
            version=version,
            model=model
        )
        
        return self._firmware_info
    
    def _calculate_crc32(self, data: bytes) -> int:
        """
        Calculate CRC-32 (Ethernet/Zip) of data.
        
        Uses standard CRC-32 polynomial (0xEDB88320).
        
        Args:
            data: Binary data to checksum
            
        Returns:
            32-bit CRC value
        """
        crc = 0xFFFFFFFF
        
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xEDB88320
                else:
                    crc >>= 1
        
        return crc ^ 0xFFFFFFFF
    
    def _extract_version(self) -> Optional[str]:
        """Extract firmware version from header if present."""
        if self._firmware_data is None or len(self._firmware_data) < 16:
            return None
        
        # Try to find version string at offset 8 (common location)
        try:
            # Look for null-terminated ASCII string
            version_start = 8
            version_end = self._firmware_data.find(b'\x00', version_start)
            if version_end > version_start and version_end - version_start < 32:
                version_bytes = self._firmware_data[version_start:version_end]
                if version_bytes and all(32 <= b < 127 for b in version_bytes):
                    return version_bytes.decode('ascii')
        except Exception:
            pass
        
        return None
    
    def _extract_model(self) -> Optional[str]:
        """Extract model identifier from header if present."""
        if self._firmware_data is None or len(self._firmware_data) < 32:
            return None
        
        # Try to find model string at offset 0 (common location)
        try:
            model_start = 0
            model_end = self._firmware_data.find(b'\x00', model_start)
            if model_end > model_start and model_end - model_start < 32:
                model_bytes = self._firmware_data[model_start:model_end]
                if model_bytes and all(32 <= b < 127 for b in model_bytes):
                    return model_bytes.decode('ascii')
        except Exception:
            pass
        
        return None
    
    @property
    def data(self) -> bytes:
        """Get raw firmware data."""
        if self._firmware_data is None:
            raise FirmwareError("No firmware loaded")
        return self._firmware_data
    
    @property
    def info(self) -> Optional[FirmwareInfo]:
        """Get firmware info if loaded."""
        return self._firmware_info
    
    def get_sdo_size_info(self) -> Tuple[int, int]:
        """
        Get size information for SDO initiate message.
        
        Returns:
            Tuple of (data_size, padding_bytes)
            - data_size: Total bytes to transfer
            - padding_bytes: Bytes needed to align to 4-byte boundary
        """
        if self._firmware_data is None:
            raise FirmwareError("No firmware loaded")
        
        data_size = len(self._firmware_data)
        padding_bytes = (4 - (data_size % 4)) % 4
        
        return data_size, padding_bytes


def load_firmware(file_path: str) -> Tuple[bytes, FirmwareInfo]:
    """
    Convenience function to load firmware file.
    
    Args:
        file_path: Path to firmware binary
        
    Returns:
        Tuple of (firmware_data, firmware_info)
    """
    loader = FirmwareLoader()
    info = loader.load(file_path)
    return loader.data, info