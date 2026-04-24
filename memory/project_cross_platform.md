---
name: Cross-platform python-can config plan
description: Future phase will replace hardcoded socketcan interface with python-can .ini file support for Windows compatibility
type: project
---

A future phase will make the CO_PCAN_DEMO CLI cross-platform by adopting python-can's `.ini` / config-file interface (`can.Bus(config_file=...)` or the auto-discovered `python_can.conf`). This will allow Windows users to configure PCAN-USB or other adapters without SocketCAN.

**Why:** Windows does not have SocketCAN; the `-iface` CLI extension is a temporary shim until config-file support lands.

**How to apply:** The `-iface` option in `co_pcan_demo.py` is intentionally optional with a fallback to `can0`. When implementing the config-file phase, replace `get_iface(args)` / `can.Bus(interface='socketcan', channel=iface)` with a factory that reads a config file first, then falls back to the explicit `-iface` arg, then `can0`.
