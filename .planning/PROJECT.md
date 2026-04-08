# Delta-Q CANopen Reprogramming Tool

## What This Is
A Python implementation of the Delta-Q TerraCharge charger reprogramming process described in Revision 4 CANopen SDO documentation, enabling automated firmware updates over CAN bus using the python-can library.

## Core Value
Automate the CANopen firmware reprogramming process to eliminate manual steps, reduce human error, and ensure consistent implementation of the complex SDO-based transfer protocol outlined in Delta-Q's documentation.

## Requirements
### Validated
<!-- Shipped and confirmed valuable. -->
(Nothing configured yet - this is a new project)

### Active
<!-- Current scope. Building toward these. -->
- [ ] Support SDO authentication exchange with seed and key generation
- [ ] Implement block download protocol with sub-block transfers
- [ ] Handle firmware verification using CRC checks
- [ ] Support required CANopen objects and messages per CiA 301/302
- [ ] Use python-can library for CAN bus communication
- [ ] Implement proper error handling for CAN operations
- [ ] Support configuration file for firmware specifications

### Out of Scope
<!-- Explicit boundaries. Includes reasoning. -->
- [ ] Support other CAN protocols beyond CANopen
- [ ] Implement full test suite beyond basic functionality
- [ ] Create graphical user interface
- [ ] Support all firmware versions automatically
- [ ] Provide comprehensive error recovery for all failure scenarios

## Context
- Based on Delta-Q charger programming documentation Revision 4
- Targets Revision 3.1.0 and later firmware
- Requires handling of SDO transfers per CiA 301 and 302 standards
- Involves complex authentication sequence and block downloads
- Will use python-can library for CAN bus communication

## Constraints
- Tech stack: Python 3.x, python-can library
- Hardware: CAN interface with SocketCAN or similar
- Protocol: CANopen standards (CiA 301, 302)
- Security: Must implement authentication with seed/key exchange
- Scope: Focus on core reprogramming functionality first

## Key Decisions
| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use CANopen standard messages | Based on provided documentation | Enables compatibility with Delta-Q chargers |
| Implement authentication protocol | Required for security | Prevents unauthorized reprogramming |
| Use python-can library | Most widely supported CAN library | Enables broad hardware compatibility |
| Custom SDO implementation vs canopen-python | Scope limited to reprogramming, not general CANopen node interaction | Better fit for single-purpose tool |

---

## Architecture Decision: Custom vs Library

**Option: canopen-python library**
- Considered but rejected
- Scope mismatch: This tool is for firmware reprogramming, not general CANopen node interaction
- Full CANopen stack (Object Dictionary, PDO, NMT) not needed
- Block transfer noted as "experimental" in canopen library
- Would require custom key algorithm anyway

**Decision: Custom implementation**
- Delta-Q specific key algorithm included
- Minimal dependencies (python-can only)
- Direct control over protocol timing
- Tests pass, works correctly
- Can add canopen integration later if needed

---
*Last updated: Wed Apr 08 2026 after project initialization*