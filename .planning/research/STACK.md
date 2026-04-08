# STACK.md: Delta-Q CANopen Reprogramming Tool Stack Research

## Research Context
- Project: Delta-Q CANopen Reprogramming Tool
- Scope: Implementing SDO-based firmware reprogramming for Delta-Q TerraCharge chargers
- Target: Revision 3.1.0 and later firmware

## Recommended Stack

### Core Library
**Library:** python-can 4.3.0+
**Rationale:** Most widely used CAN library in Python ecosystem, provides abstraction over different CAN interfaces (SocketCAN, PCAN, Kvaser, etc.), actively maintained, well-documented, and implements CANopen-specific protocols via additional modules.
**Confidence:** High

### CAN Interface Options
**Primary:** SocketCAN (Linux kernel built-in)
**Rationale:** Zero-cost, high-performance, kernel-level implementation, works with most USB-to-CAN adapters via slcan, no additional drivers needed on Linux systems.
**Confidence:** High

**Secondary:** python-can native interfaces for:
- PEAK-System (pcan)
- Kvaser (kvaser)
- CANKing (cantact)
**Rationale:** Provides cross-platform support when SocketCAN not available (Windows/macOS), though may require vendor SDKs/drivers.
**Confidence:** Medium

### Communication Protocol Implementation
**Approach:** Direct SDO implementation using python-can
**Rationale:** The CANopen SDO protocol is well-defined in CiA 301, implementing it directly gives full control over timing, retries, and error handling required for the reprogramming sequence. Using a full CANopen stack would add unnecessary complexity.
**Confidence:** High

### Supporting Libraries
1. **pycrc** (for CRC calculations if needed)
   **Rationale:** Standardized CRC implementations, though we may implement our own for simplicity
   **Confidence:** Medium

2. **python-dotenv** (for configuration)
   **Rationale:** Clean separation of configuration from code, supports .env files for different environments
   **Confidence:** High

3. **click** or **typer** (for CLI)
   **Rationale:** Professional command-line interface with minimal boilerplate
   **Confidence:** Medium

### Development & Testing
**Framework:** pytest 7.0+
**Rationale:** Industry standard, excellent fixture system for mocking CAN bus, good reporting
**Confidence:** High

**Mocking:** unittest.mock (built-in) or pytest-mock
**Rationale:** Essential for testing CAN operations without hardware
**Confidence:** High

### What NOT to Use
- **Full CANopen stacks** (like CANopenNode or Microchip CANopen): Overkill for this specific reprogramming task, adds significant complexity for minimal benefit
- **Real-time operating systems:** Not needed as this is a host-based tool, not embedded firmware
- **Proprietary Windows-only CAN libraries:** Would limit cross-platform compatibility
- **Outdated python-can versions (<3.0):** Missing important features and bug fixes

### Version Justification
All recommendations target current stable releases (as of Q1 2025) that have:
- Active maintenance and security updates
- Compatibility with Python 3.8+
- Good documentation and community support
- Proven track record in similar projects

### Implementation Notes
The stack is deliberately minimalistic to reduce complexity and failure points. The core functionality requires:
1. CAN bus communication (python-can)
2. Precise timing control for SDO exchanges (time.sleep with precision)
3. Byte manipulation for constructing/dissecting CAN frames
4. Basic file I/O for firmware loading
5. Error handling and retry logic per Delta-Q specifications

This approach keeps dependencies low while maintaining full control over the reprogramming sequence timing and error handling requirements.