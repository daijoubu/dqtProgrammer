#!/usr/bin/env python3
"""CO_PCAN_DEMO compatible CLI for Delta-Q charger CAN operations."""

import argparse
import sys
import can
import canopen

from src.block_download import download_firmware, BlockDownloadProgress
from src.sdo import parse_sdo_index, sdo_read, sdo_write

# Modes not yet implemented — work in progress.
_IN_PROGRESS = {
    3:   "Serial CAN Bridge",
    4:   "Read NVS",
    5:   "Write NVS",
    7:   "Erase NVS",
    10:  "Parallel Programming",
    11:  "Parallel Log Upload",
    12:  "Parallel SDO Read",
    101: "SDO Array Read",
    102: "Parallel Reset",
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="CO_PCAN_DEMO",
        description="CAN device programming and SDO utility",
        allow_abbrev=False,
    )

    # ── Global options ────────────────────────────────────────────────────────
    parser.add_argument("-mode",   type=int,   required=True, metavar="modeNumber",
                        help="Operational mode")
    parser.add_argument("-br",     type=int,   required=True, metavar="baudRate",
                        help="CAN baud rate in kbps (e.g. 125, 250, 500, 1000)")
    parser.add_argument("-nodeId", type=int,   required=True, metavar="chargerNodeId",
                        help="Target charger CANopen node ID")
    parser.add_argument("-tout",   type=float, metavar="seconds",
                        help="Timeout in seconds (required for all modes except 3)")
    parser.add_argument("-charger_COBId",    type=int, metavar="cobId",
                        help="COB-ID for charger SDO requests")
    parser.add_argument("-programmer_COBId", type=int, metavar="cobId",
                        help="COB-ID for programmer SDO responses")


    # ── Mode 0: firmware flash ────────────────────────────────────────────────
    parser.add_argument("-f", metavar="filePath",
                        help="[Mode 0] Path to firmware binary package")
    parser.add_argument("-noAuth", action=argparse.BooleanOptionalAction,
                        help="[Mode 0] no authentication")
    parser.add_argument("-skipUnhideParam", action=argparse.BooleanOptionalAction,
                        help="[Mode 0] Skip Unhide Parameters")
    
    # ── Mode 1: SDO read ──────────────────────────────────────────────────────
    parser.add_argument("-rdIdx",    metavar="index",
                        help="[Mode 1] SDO index (decimal or hex, e.g. 8022 or x1f56)")
    parser.add_argument("-rdSubIdx", type=int, metavar="subIndex",
                        help="[Mode 1] SDO sub-index")
    parser.add_argument("-fout",     metavar="filePath",
                        help="[Mode 1] Optional output file for read value")
    parser.add_argument("-rdSize", type=int,
                        help="[Mode 1] Size of value to read in bytes")

    # ── Mode 2: SDO write ─────────────────────────────────────────────────────
    parser.add_argument("-wrIdx",    metavar="index",
                        help="[Mode 2] SDO index (decimal or hex)")
    parser.add_argument("-wrSubIdx", type=int, metavar="subIndex",
                        help="[Mode 2] SDO sub-index")
    parser.add_argument("-wrVal",    type=int, metavar="value",
                        help="[Mode 2] Integer value to write")

    # ── Mode 3: serial CAN bridge ─────────────────────────────────────────────
    parser.add_argument("-COM",              type=int, metavar="port",
                        help="[Mode 3] Serial port number")
    parser.add_argument("-myNodeId",         type=int, metavar="myId",
                        help="[Mode 3] Local node ID")

    # ── Modes 4 / 5: NVS ─────────────────────────────────────────────────────
    parser.add_argument("-dsId",    type=int, metavar="datasetId",
                        help="[Mode 4/5] Dataset ID")
    parser.add_argument("-dsInpVal", metavar="value",
                        help="[Mode 5] Value to write")

    # ── Channel override — optional extension, not in original spec.
    #    Interface type is always resolved from ~/.canrc or CAN_INTERFACE env var.
    parser.add_argument("-iface", metavar="channel",
                        help="CAN channel (e.g. can0, PCAN_USBBUS1). "
                             "Defaults to the channel in ~/.canrc.")

    return parser.parse_args()


def _require(args: argparse.Namespace, *flags: str, mode_label: str) -> None:
    """Exit with an error if any required flag for a mode is missing."""
    missing = [f for f in flags if getattr(args, f.lstrip("-"), None) is None]
    if missing:
        print(f"Error: mode {mode_label} requires: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


def _make_bus(args: argparse.Namespace) -> can.Bus:
    """Build a python-can Bus, deferring interface type to ~/.canrc."""
    kwargs = {}
    if args.br:
        kwargs["bitrate"] = args.br * 1000
    return can.Bus(channel=args.iface, interface=None, **kwargs)


def _connect_network(args: argparse.Namespace) -> canopen.Network:
    """Build and connect a canopen Network, deferring interface type to ~/.canrc."""
    kwargs = {}
    if args.br:
        kwargs["bitrate"] = args.br * 1000
    network = canopen.Network()
    network.connect(channel=args.iface, interface=None, **kwargs)
    return network


def _progress_bar(p: BlockDownloadProgress) -> None:
    bar_width = 40
    filled = int(bar_width * p.percentage / 100)
    bar = "#" * filled + "-" * (bar_width - filled)
    print(f"\r[{bar}] {p.percentage:5.1f}%  {p.bytes_transferred}/{p.total_bytes} B",
          end="", flush=True)


# ── Mode handlers ─────────────────────────────────────────────────────────────

def _handle_mode_0(args: argparse.Namespace) -> None:
    _require(args, "-f", mode_label="0 (Programming via CAN)")

    print(f"Channel   : {args.iface or '(from config)'}")
    print(f"Bitrate   : {args.br * 1000 if args.br else '(from config)'}")
    print(f"Node ID   : 0x{args.nodeId:02X}")
    print(f"Firmware  : {args.f}")
    print(f"Timeout   : {args.tout}s")
    print()

    bus = _make_bus(args)
    try:
        info = download_firmware(
            bus=bus,
            node_id=args.nodeId,
            firmware_path=args.f,
            progress_callback=_progress_bar,
            timeout=args.tout,
        )
        print()
        crc_str = f", DQT CRC=0x{info.dqt_crc:08X}" if info.dqt_crc is not None else ""
        print(f"Done — {info.file_size} bytes, CRC32=0x{info.crc32:08X}{crc_str}")
    finally:
        bus.shutdown()


def _handle_mode_1(args: argparse.Namespace) -> None:
    _require(args, "-rdIdx", "-rdSubIdx", mode_label="1 (Read SDO)")

    index = parse_sdo_index(args.rdIdx)
    sub_index = args.rdSubIdx

    network = _connect_network(args)
    try:
        node = canopen.RemoteNode(args.nodeId, None)
        network.add_node(node)
        node.sdo.RESPONSE_TIMEOUT = args.tout

        data = sdo_read(node, index, sub_index)

        hex_str = data.hex().upper()
        print(f"0x{index:04X}:{sub_index:02X} = 0x{hex_str}", end="")
        if len(data) <= 8:
            print(f"  ({int.from_bytes(data, 'little')})", end="")
        print()

        if args.fout:
            with open(args.fout, "w") as fh:
                fh.write(f"0x{hex_str}\n")
    finally:
        network.disconnect()


def _handle_mode_2(args: argparse.Namespace) -> None:
    _require(args, "-wrIdx", "-wrSubIdx", "-wrVal", mode_label="2 (Write SDO)")

    index = parse_sdo_index(args.wrIdx)
    sub_index = args.wrSubIdx

    network = _connect_network(args)
    try:
        node = canopen.RemoteNode(args.nodeId, None)
        network.add_node(node)
        node.sdo.RESPONSE_TIMEOUT = args.tout

        val = args.wrVal
        byte_len = max(1, (val.bit_length() + 7) // 8)
        data = val.to_bytes(byte_len, "little")
        sdo_write(node, index, sub_index, data)

        print(f"0x{index:04X}:{sub_index:02X} <- 0x{data.hex().upper()}")
    finally:
        network.disconnect()


# ── Dispatch ──────────────────────────────────────────────────────────────────

def _dispatch(args: argparse.Namespace) -> None:
    if args.mode == 0:
        _handle_mode_0(args)
    elif args.mode == 1:
        _handle_mode_1(args)
    elif args.mode == 2:
        _handle_mode_2(args)
    elif args.mode in _IN_PROGRESS:
        print(f"Mode {args.mode} ({_IN_PROGRESS[args.mode]}) is not yet implemented "
              f"— work in progress.", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"Error: Unsupported mode {args.mode}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = _parse_args()

    if args.mode != 3 and args.tout is None:
        print(f"Error: -tout is required for mode {args.mode}", file=sys.stderr)
        sys.exit(1)

    try:
        _dispatch(args)
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print("Program End -- Task Success")


if __name__ == "__main__":
    main()
