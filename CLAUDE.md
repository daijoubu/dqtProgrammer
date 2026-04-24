# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

`dqtProgrammer` flashes firmware to Delta-Q battery chargers over CAN bus using the CANopen SDO block download protocol. The entry point is `flash.py`.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Flash via slcan adapter (e.g. CANable/PCAN serial)
python flash.py path/to/CO_Config.bin --channel /dev/ttyACM0 --interface-type slcan --bitrate 125000

# Flash via SocketCAN (Linux)
python flash.py path/to/CO_Config.bin --channel can0 --interface-type socketcan

# Flash via PCAN (Windows/Linux)
python flash.py path/to/CO_Config.bin --channel PCAN_USBBUS1 --interface-type pcan --bitrate 125000

# --interface-type and --bitrate can be omitted if set in ~/.canrc or CAN_INTERFACE env var
# Flash with optional customer auth secret
python flash.py path/to/CO_Config.bin --channel /dev/ttyACM0 --interface-type slcan --bitrate 125000 --secret 0x1234

# Run all unit tests (no hardware required — uses python-can virtual interface)
pytest tests/test_block_download.py tests/test_auth.py tests/test_can_integration.py -v

# Run a single test
pytest tests/test_block_download.py::TestFirmwareLoader::test_crc32_known_value -v

# Run mock charger for manual testing on vcan0 (separate terminal)
python mock_charger.py

## Architecture

```
flash.py                  ← CLI entry point
src/
  firmware.py             ← FirmwareLoader: load .bin, CRC32, parse crc_s.txt
  block_download.py       ← SDOBlockDownload + download_firmware() convenience fn
  auth.py                 ← SDOAuthentication: seed/key exchange at 0x2400
  sdo.py                  ← Thin wrappers around canopen SDO upload/download
tests/
  conftest.py             ← pytest fixtures: can_bus, can_network (virtual interface, cross-platform)
  test_block_download.py  ← Unit tests (mocked canopen)
  test_can_integration.py ← Integration tests (python-can virtual interface)
mock_charger.py           ← Standalone mock SDO server for manual testing
```

### Flash sequence (in `SDOBlockDownload.download_firmware`)

1. Write `STOP` (0x00) → `0x1F51:01`, wait for charger to confirm stopped
2. Write `CLEAR` (0x03) → `0x1F51:01` (erases flash)
3. Block-download firmware binary → `0x1F50:01`
4. Wait for charger to reboot (polls `0x1F56:01`, up to 30 s)
5. Read DQT CRC from `0x1F56:01` and compare against `crc_s.txt` `overallCRC` value

### Hardware quirks

- **First block ACK timeout is 60 s** (`FIRST_BLOCK_DELAY`): flash erase takes many seconds.
- **1.5 ms inter-frame gap minimum** (`PAUSE_BEFORE_SEND = 0.0015`): the charger's CAN buffer holds ~22 segments (~154 bytes); 0 ms fails, 1 ms is risky due to Linux scheduler jitter, 1.5 ms is the validated floor (~2m19s for 375 KB), 5 ms is safe.
- **Block size = 127 (0x7F)** segments per ACK cycle.
- **Default node ID = 0x0A**, default interface = `can0`.

### Authentication

Authentication is optional — the charger allows reprogramming without it. When `--secret` is passed, `auth.py` reads a seed from `0x2400:01`, computes a key using the Delta-Q NAND/XOR algorithm, and writes it to `0x2400:02`. Max 3 attempts before charger lockout.

### Firmware files

`FirmwareLoader` expects a raw `.bin` file (max 2 MB). If a `crc_s.txt` file sits alongside the `.bin`, it parses the `overallCRC(...)` line as the expected post-flash CRC. The actual charger CRC is read back after reboot and compared.

## Key CANopen object indices

| Object    | Sub | Purpose              |
|-----------|-----|----------------------|
| `0x1F50`  | 01  | Program data (firmware binary) |
| `0x1F51`  | 01  | Program control (stop/start/reset/clear) |
| `0x1F56`  | 01  | Program CRC (read-back after flash) |
| `0x1F57`  | 01  | Flash status |
| `0x2400`  | 01  | Auth seed (read) |
| `0x2400`  | 02  | Auth key (write) |
