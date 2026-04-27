"""SDO utility functions for CO_PCAN_DEMO modes 1 and 2."""

import canopen


def parse_sdo_index(s: str) -> int:
    """Parse an SDO index string: decimal (8022), x1f56, or 0x1f56."""
    s = s.strip()
    if s.lower().startswith('0x'):
        return int(s, 16)
    if s.lower().startswith('x'):
        return int(s[1:], 16)
    return int(s)


def sdo_read(node: canopen.RemoteNode, index: int, sub_index: int) -> bytes:
    return bytes(node.sdo.upload(index, sub_index))


def sdo_write(node: canopen.RemoteNode, index: int, sub_index: int, data: bytes) -> None:
    node.sdo.download(index, sub_index, data)
