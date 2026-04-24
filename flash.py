#!/usr/bin/env python3
"""Flash firmware to Delta-Q charger via CANopen SDO block download."""

import argparse
import sys
import can
from src.block_download import download_firmware, BlockDownloadProgress


def progress(p: BlockDownloadProgress):
    bar_width = 40
    filled = int(bar_width * p.percentage / 100)
    bar = "#" * filled + "-" * (bar_width - filled)
    print(f"\r[{bar}] {p.percentage:5.1f}%  {p.bytes_transferred}/{p.total_bytes} B", end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Flash firmware to Delta-Q charger")
    parser.add_argument("firmware", help="Path to firmware binary (e.g. CO_Config.bin)")
    parser.add_argument("--channel", default="can0", help="CAN channel (default: can0; e.g. PCAN_USBBUS1 for PCAN)")
    parser.add_argument("--interface-type", default=None, help="python-can backend: socketcan, pcan, kvaser, virtual, … Reads ~/.canrc or CAN_INTERFACE env var if omitted.")
    parser.add_argument("--bitrate", type=int, default=None, help="CAN bus bitrate in bps (e.g. 125000). Passed through to the interface driver.")
    parser.add_argument("--node-id", type=lambda x: int(x, 0), default=0x0A, help="CANopen node ID (default: 0x0A)")
    parser.add_argument("--timeout", type=float, default=5.0, help="SDO response timeout in seconds (default: 5.0)")
    parser.add_argument("--secret", type=lambda x: int(x, 0), default=None, help="Customer secret for auth (optional)")
    args = parser.parse_args()

    print(f"Channel   : {args.channel}")
    print(f"Interface : {args.interface_type or '(from config)'}")
    print(f"Bitrate   : {args.bitrate or '(from config)'}")
    print(f"Node ID   : 0x{args.node_id:02X}")
    print(f"Firmware  : {args.firmware}")
    print(f"Timeout   : {args.timeout}s")
    print()

    bus_kwargs = {}
    if args.bitrate is not None:
        bus_kwargs['bitrate'] = args.bitrate
    bus = can.Bus(channel=args.channel, interface=args.interface_type, **bus_kwargs)
    try:
        info = download_firmware(
            bus=bus,
            node_id=args.node_id,
            firmware_path=args.firmware,
            customer_secret=args.secret,
            progress_callback=progress,
            timeout=args.timeout,
        )
        print()
        crc_str = f", DQT CRC=0x{info.dqt_crc:08X}" if info.dqt_crc is not None else ""
        print(f"Done — {info.file_size} bytes, CRC32=0x{info.crc32:08X}{crc_str}")
    except Exception as e:
        print(f"\nFailed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
