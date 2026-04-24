---
name: canopen Network(bus) requires explicit connect() call
description: canopen.Network(bus) sets self.bus but does not create the Notifier — SDO responses are silently dropped without calling connect()
type: feedback
---

`canopen.Network(bus)` in canopen 2.4.x sets `self.bus = bus` in `__init__` but does NOT create the `can.Notifier`. Without the Notifier, incoming CAN messages are never dispatched to listeners, so all SDO uploads/downloads time out with "No SDO response received" even though the bus is physically working.

**Why:** `Network.__init__` only sets the bus attribute; `Network.connect()` is what creates the Notifier. When `connect()` is called after `Network(bus)`, it skips bus creation (because `self.bus is not None`) and only creates the Notifier.

**How to apply:** Always call `network.connect()` after `canopen.Network(bus)`:
```python
self.network = canopen.Network(bus)
self.network.connect()  # creates Notifier without creating a new bus
```
This pattern is used in both `src/auth.py` and `src/block_download.py`.
