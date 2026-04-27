---

# **CO_PCAN_DEMO Command Line Interface Specification**

## **1. Overview**
`CO_PCAN_DEMO` is a command‑line tool for interacting with CAN‑based devices.  
It supports firmware programming, SDO read/write operations, NVS access, serial bridging, and several parallel operations.

This document defines the full CLI behavior so it can be replicated in Python.

---

## **2. General Command Structure**

### **2.1 Invocation**
```
CO_PCAN_DEMO -mode <modeNumber> -br <baudRate> -nodeId <ChargerNodeId> [additional parameters...]
```

### **2.2 Global Options**

| Option | Required | Type | Description |
|--------|----------|------|-------------|
| `-mode` | Yes | int | Selects the operational mode. |
| `-br` | Yes | int | CAN bus baud rate (e.g., 125, 250, 500, 1000). |
| `-nodeId` | Yes | int | Target charger node ID. |
| `-tout` | Required in all modes except Mode 3 | int | Timeout in seconds. |

### **2.3 General Behavior**
- Exactly **one mode** is executed per invocation.
- Missing required parameters must produce an error.
- Unknown parameters must produce an error.
- On success, the tool prints:

```
Program End -- Task Success
```

---

# **3. Mode Specifications**

Each mode defines additional required or optional parameters.

---

## **Mode 0 — Programming via CAN**

### **Description**
Programs a device using a binary package file.

### **Required Parameters**
| Option | Type | Description |
|--------|------|-------------|
| `-f` | string | Absolute path to the binary package file. |

### **Syntax**
```
CO_PCAN_DEMO -mode 0 -br <baud> -tout <sec> -nodeId <id> -f <path>
```

---

## **Mode 1 — Read SDO**

### **Description**
Reads a single SDO entry. Optionally writes the result to a file.

### **Required Parameters**
| Option | Type | Description |
|--------|------|-------------|
| `-rdIdx` | int or hex string | SDO index (decimal or hex, e.g., `8022` or `x1f56`). |
| `-rdSubIdx` | int | SDO sub‑index. |

### **Optional Parameters**
| Option | Type | Description |
|--------|------|-------------|
| `-fout` | string | Output file path for storing the read value. |

### **Syntax**
```
CO_PCAN_DEMO -mode 1 -br <baud> -tout <sec> -nodeId <id> \
             -rdIdx <index> -rdSubIdx <subIndex> [-fout <file>]
```

---

## **Mode 2 — Write SDO**

### **Description**
Writes a value to an SDO entry.

### **Required Parameters**
| Option | Type | Description |
|--------|------|-------------|
| `-wrIdx` | int or hex string | SDO index. |
| `-wrSubIdx` | int | SDO sub‑index. |
| `-wrVal` | int | Value to write. |

### **Syntax**
```
CO_PCAN_DEMO -mode 2 -br <baud> -tout <sec> -nodeId <id> \
             -wrIdx <index> -wrSubIdx <subIndex> -wrVal <value>
```

---

## **Mode 3 — Serial CAN Bridge**

### **Description**
Starts a serial‑to‑CAN bridge.

### **Required Parameters**
| Option | Type | Description |
|--------|------|-------------|
| `-COM` | int | Serial port number. |
| `-myNodeId` | int | Local node ID. |

### **Optional Parameters**
| Option | Type | Description |
|--------|------|-------------|
| `-charger_COBId` | int | COB‑ID for charger SDO requests. |
| `-programmer_COBId` | int | COB‑ID for programmer SDO responses. |

### **Notes**
- Mode 3 does **not** require `-tout`.

### **Syntax**
```
CO_PCAN_DEMO -mode 3 -br <baud> -nodeId <id> -myNodeId <myId> \
             -COM <port> [-charger_COBId <id>] [-programmer_COBId <id>]
```

---

## **Mode 4 — Read NVS**

### **Description**
Reads a dataset from non‑volatile storage.

### **Required Parameters**
| Option | Type | Description |
|--------|------|-------------|
| `-dsId` | int | Dataset ID. |

### **Syntax**
```
CO_PCAN_DEMO -mode 4 -br <baud> -tout <sec> -nodeId <id> -dsId <datasetId>
```

---

## **Mode 5 — Write NVS**

### **Description**
Writes a dataset value to NVS.

### **Required Parameters**
| Option | Type | Description |
|--------|------|-------------|
| `-dsId` | int | Dataset ID. |
| `-dsInpVal` | string | Value to write (often hex or byte string). |

### **Syntax**
```
CO_PCAN_DEMO -mode 5 -br <baud> -tout <sec> -nodeId <id> \
             -dsId <datasetId> -dsInpVal <value>
```

---

## **Mode 7 — Erase NVS**

### **Description**
Erases NVS content.

### **Syntax**
```
CO_PCAN_DEMO -mode 7 -br <baud> -tout <sec> -nodeId <id>
```

---

# **4. Parallel Operation Modes**

Modes 10, 11, 12, 101, and 102 share the same structure.

### **Common Syntax**
```
CO_PCAN_DEMO -mode <modeNumber> -br <baud> -tout <sec> -nodeId <id>
```

### **Descriptions**
| Mode | Description |
|------|-------------|
| **10** | Parallel Programming |
| **11** | Parallel Log Upload |
| **12** | Parallel SDO Read |
| **101** | SDO Array Read |
| **102** | Parallel Reset |

### **Notes**
- No additional parameters are defined in the provided documentation.
- All require `-tout`.

---

# **5. Error Handling Requirements**

### **5.1 Missing Required Parameters**
- Must produce an error message.
- Must exit with non‑zero status.

### **5.2 Invalid Parameter Values**
Examples:
- Non‑numeric baud rate.
- Missing file path for mode 0.
- Invalid hex format for SDO index.

### **5.3 Unknown Mode**
Error message:
```
Error: Unsupported mode <value>
```

---

# **6. Output Requirements**

### **6.1 Success**
```
Program End -- Task Success
```

### **6.2 Failure**
- Print a descriptive error message.
- Exit non‑zero.

---

# **7. Python Implementation Notes**

### **7.1 Recommended Libraries**
- `argparse` (standard library)
- or `click` (more ergonomic)

### **7.2 Hex Parsing**
`rdIdx` and `wrIdx` may be:
- decimal: `8022`
- hex: `x1f56` or `0x1f56`

Python implementation should:
- Detect hex prefixes (`x`, `0x`)
- Convert using `int(value, 16)`

### **7.3 Mode Dispatch Pattern**
```
if args.mode == 0:
    handle_mode_0(args)
elif args.mode == 1:
    handle_mode_1(args)
...
```

---
