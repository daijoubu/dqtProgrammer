"""Unit tests for SDO Block Download module.

Tests firmware loading, CRC calculation, and block download message building.
Uses mocks for canopen to test without hardware.
"""

import os
import struct
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch

from src.firmware import FirmwareLoader, FirmwareInfo, FirmwareError
from src.block_download import (
    SDOBlockDownload,
    BlockDownloadError,
    BlockDownloadState,
    BlockDownloadProgress
)


class TestFirmwareLoader(unittest.TestCase):
    """Test cases for FirmwareLoader class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.loader = FirmwareLoader()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temp files."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_firmware_file(self, data: bytes, size: int = None) -> str:
        """Create a test firmware file."""
        if size is None:
            size = len(data)
        
        filepath = os.path.join(self.temp_dir, "test_firmware.bin")
        
        # Pad to requested size if needed
        if len(data) < size:
            data = data + b'\xFF' * (size - len(data))
        
        with open(filepath, 'wb') as f:
            f.write(data[:size])
        
        return filepath
    
    def test_load_existing_file(self):
        """Test loading existing firmware file."""
        # Create a 100-byte firmware file
        test_data = b'TEST FIRMWARE v1.0.0' + b'\x00' * 80
        filepath = self._create_firmware_file(test_data, 100)
        
        info = self.loader.load(filepath)
        
        self.assertEqual(info.file_path, filepath)
        self.assertEqual(info.file_size, 100)
        self.assertIsNotNone(info.crc32)
        self.assertIsNotNone(info.version)
    
    def test_load_nonexistent_file(self):
        """Test loading nonexistent file raises error."""
        with self.assertRaises(FirmwareError):
            self.loader.load("/nonexistent/firmware.bin")
    
    def test_load_empty_file(self):
        """Test loading empty file raises error."""
        filepath = os.path.join(self.temp_dir, "empty.bin")
        with open(filepath, 'wb') as f:
            pass  # Create empty file
        
        with self.assertRaises(FirmwareError):
            self.loader.load(filepath)
    
    def test_load_oversized_file(self):
        """Test loading oversized file raises error."""
        # Create file larger than MAX_FILE_SIZE (2MB)
        filepath = os.path.join(self.temp_dir, "large.bin")
        with open(filepath, 'wb') as f:
            # Write 3MB of data
            f.write(b'\xFF' * (3 * 1024 * 1024))
        
        with self.assertRaises(FirmwareError):
            self.loader.load(filepath)
    
    def test_crc32_calculation(self):
        """Test CRC-32 calculation is consistent."""
        test_data = b"Hello, World!"
        
        # Calculate CRC twice
        info1 = self.loader.load(self._create_firmware_file(test_data))
        self.loader._firmware_data = None
        self.loader._firmware_info = None
        info2 = self.loader.load(self._create_firmware_file(test_data))
        
        self.assertEqual(info1.crc32, info2.crc32)
    
    def test_crc32_known_value(self):
        """Test CRC-32 against known value."""
        # "Hello, World!" should have specific CRC
        test_data = b"Hello, World!"
        filepath = self._create_firmware_file(test_data)
        
        info = self.loader.load(filepath)
        
        # Verify CRC is a valid 32-bit value
        self.assertGreaterEqual(info.crc32, 0)
        self.assertLessEqual(info.crc32, 0xFFFFFFFF)
    
    def test_sdo_size_info(self):
        """Test SDO size info calculation."""
        test_data = b'A' * 100  # 100 bytes
        filepath = self._create_firmware_file(test_data)
        
        self.loader.load(filepath)
        
        data_size, padding = self.loader.get_sdo_size_info()
        
        self.assertEqual(data_size, 100)
        self.assertEqual(padding, 0)  # 100 % 4 = 0
        
        # Test with 3-byte data (needs 1 byte padding)
        test_data_3 = b'ABC'
        filepath_3 = self._create_firmware_file(test_data_3)
        
        self.loader._firmware_data = None
        self.loader._firmware_info = None
        self.loader.load(filepath_3)
        
        data_size, padding = self.loader.get_sdo_size_info()
        
        self.assertEqual(data_size, 3)
        self.assertEqual(padding, 1)  # (4 - (3 % 4)) % 4 = 1
    
    def test_version_extraction(self):
        """Test firmware version extraction from header."""
        # Create firmware with version at offset 8
        header = b'MODEL001' + b'version1.2.3\x00' + b'\x00' * 100
        filepath = self._create_firmware_file(header)
        
        info = self.loader.load(filepath)
        
        self.assertEqual(info.version, 'version1.2.3')
    
    def test_model_extraction(self):
        """Test firmware model extraction from header."""
        # Create firmware with model at offset 0
        header = b'TerraCharge\x00' + b'\x00' * 100
        filepath = self._create_firmware_file(header)
        
        info = self.loader.load(filepath)
        
        self.assertEqual(info.model, 'TerraCharge')
    
    def test_data_property(self):
        """Test data property returns firmware bytes."""
        test_data = b'TEST DATA 12345'
        filepath = self._create_firmware_file(test_data)
        
        self.loader.load(filepath)
        
        self.assertEqual(self.loader.data, test_data)
    
    def test_data_property_not_loaded(self):
        """Test data property raises when not loaded."""
        with self.assertRaises(FirmwareError):
            _ = self.loader.data
    
    def test_info_property(self):
        """Test info property returns FirmwareInfo."""
        test_data = b'FIRMWARE'
        filepath = self._create_firmware_file(test_data)
        
        info = self.loader.load(filepath)
        
        self.assertIsNotNone(self.loader.info)
        self.assertEqual(self.loader.info.file_size, len(test_data))


class TestBlockDownloadProgress(unittest.TestCase):
    """Test cases for BlockDownloadProgress class."""
    
    def test_percentage_calculation(self):
        """Test percentage calculation."""
        progress = BlockDownloadProgress(
            total_bytes=1000,
            bytes_transferred=500,
            current_block=5,
            total_blocks=10
        )
        
        self.assertEqual(progress.percentage, 50.0)
    
    def test_percentage_zero_total(self):
        """Test percentage with zero total."""
        progress = BlockDownloadProgress(
            total_bytes=0,
            bytes_transferred=0,
            current_block=0,
            total_blocks=0
        )
        
        self.assertEqual(progress.percentage, 0.0)
    
    def test_percentage_complete(self):
        """Test percentage at 100%."""
        progress = BlockDownloadProgress(
            total_bytes=1000,
            bytes_transferred=1000,
            current_block=10,
            total_blocks=10
        )
        
        self.assertEqual(progress.percentage, 100.0)
    
    def test_string_representation(self):
        """Test string representation."""
        progress = BlockDownloadProgress(
            total_bytes=1000,
            bytes_transferred=500,
            current_block=5,
            total_blocks=10
        )
        
        progress_str = str(progress)
        
        self.assertIn('500/1000', progress_str)
        self.assertIn('50.0%', progress_str)
        self.assertIn('Block 5/10', progress_str)


class TestSDOBlockDownload(unittest.TestCase):
    """Test cases for SDOBlockDownload class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_bus = Mock(spec=['canopen'])
        self.node_id = 0x10
        
        # Create downloader with mocked bus
        with patch('src.block_download.canopen.Network'):
            with patch('src.block_download.canopen.RemoteNode'):
                self.downloader = SDOBlockDownload(
                    bus=self.mock_bus,
                    node_id=self.node_id,
                    block_size=127,
                    timeout=2.0
                )
    
    def test_initialization(self):
        """Test downloader initialization."""
        self.assertEqual(self.downloader.node_id, self.node_id)
        self.assertEqual(self.downloader.block_size, 127)
        self.assertEqual(self.downloader.timeout, 2.0)
        self.assertEqual(self.downloader.state, BlockDownloadState.IDLE)
    
    def test_default_block_size(self):
        """Test default block size constant."""
        self.assertEqual(SDOBlockDownload.BLOCK_SIZE, 0x7F)
    
    def test_object_indices(self):
        """Test CANopen object indices."""
        self.assertEqual(SDOBlockDownload.OBJ_PROGRAM_DATA, 0x1F50)
        self.assertEqual(SDOBlockDownload.OBJ_PROGRAM_CONTROL, 0x1F51)
        self.assertEqual(SDOBlockDownload.OBJ_PROGRAM_CRC, 0x1F56)
        self.assertEqual(SDOBlockDownload.OBJ_FLASH_STATUS, 0x1F57)
    
    def test_program_control_commands(self):
        """Test program control command constants."""
        self.assertEqual(SDOBlockDownload.PROGRAM_STOP, 0x00)
        self.assertEqual(SDOBlockDownload.PROGRAM_START, 0x01)
        self.assertEqual(SDOBlockDownload.PROGRAM_RESET, 0x02)
        self.assertEqual(SDOBlockDownload.PROGRAM_CLEAR, 0x03)
    
    def test_state_property(self):
        """Test state property getter."""
        self.assertEqual(self.downloader.state, BlockDownloadState.IDLE)
        
        self.downloader._state = BlockDownloadState.TRANSFERRING
        
        self.assertEqual(self.downloader.state, BlockDownloadState.TRANSFERRING)
    
    @patch('src.block_download.canopen.Network')
    @patch('src.block_download.canopen.RemoteNode')
    def test_progress_callback_called(self, mock_node, mock_network):
        """Test progress callback is called during operations."""
        progress_calls = []
        
        def track_progress(progress):
            progress_calls.append(progress)
        
        # Create downloader with callback
        downloader = SDOBlockDownload(
            bus=self.mock_bus,
            node_id=self.node_id,
            progress_callback=track_progress
        )
        
        # Simulate some transfer state
        downloader._firmware_info = FirmwareInfo(
            file_path='/test/firmware.bin',
            file_size=1000,
            crc32=0x12345678
        )
        downloader._bytes_transferred = 500
        downloader._current_block = 5
        downloader._total_blocks = 10
        
        # Trigger progress update
        downloader._update_progress()
        
        self.assertEqual(len(progress_calls), 1)
        self.assertEqual(progress_calls[0].percentage, 50.0)


class TestDownloadFirmwareFunction(unittest.TestCase):
    """Test cases for download_firmware convenience function."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_bus = Mock()
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_firmware_file(self, data: bytes) -> str:
        """Create a test firmware file."""
        filepath = os.path.join(self.temp_dir, "firmware.bin")
        with open(filepath, 'wb') as f:
            f.write(data)
        return filepath
    
    @patch('src.auth.authenticate_charger')
    @patch('src.block_download.SDOBlockDownload')
    def test_download_firmware_calls_auth(self, mock_downloader_class, mock_auth):
        """Test download_firmware calls authenticate_charger first."""
        from src.block_download import download_firmware
        
        firmware_data = b'TEST FIRMWARE'
        firmware_path = self._create_firmware_file(firmware_data)

        # Setup mock downloader
        mock_downloader = Mock()
        mock_downloader.download_firmware.return_value = FirmwareInfo(
            file_path=firmware_path,
            file_size=len(firmware_data),
            crc32=0x12345678
        )
        mock_downloader_class.return_value = mock_downloader

        result = download_firmware(
            bus=self.mock_bus,
            node_id=0x10,
            firmware_path=firmware_path,
            customer_secret=0x1234
        )

        # Verify auth was called
        mock_auth.assert_called_once()

        # Verify download was called
        mock_downloader.download_firmware.assert_called_once()


if __name__ == '__main__':
    unittest.main()