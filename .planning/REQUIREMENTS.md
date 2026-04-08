# Requirements: Delta-Q CANopen Reprogramming Tool

**Defined:** 2026-04-08
**Core Value:** Enable safe and consistent firmware updates for Delta-Q TerraCharge chargers using CANopen SDO protocol

## v1 Requirements (Active Scope)
These requirements define the minimum viable functionality for initial implementation.

### Authentication
- [ ] **AUTH-01**: Implement SDO authentication sequence with seed/key exchange (per CiA 301/302)
- [ ] AUTH-02: Validate key matches charger requirements

### Block Download
- [ ] BLOCK-01: Implement byte-accurate SDO block transfer protocol
- [ ] BLOCK-02: Handle sub-block transfers as per Delta-Q specifications
- [ ] BLOCK-03: Manage CRC calculation and validation during download

### Firmware Handling
- [ ] FIRM-01: Load firmware from specified binary file
- [ ] FIRM-02: Validate firmware image against Delta-Q specifications

### Error Handling
- [ ] ERR-01: Implement retry logic per Delta-Q's fault codes
- [ ] ERR-02: Gracefully handle CAN bus errors

### Testability
- [ ] TEST-01: Implement unit tests for SDO transactions
- [ ] TEST-02: Create integration tests using mock CAN bus

## v2 Requirements (Deferred)
- [ ] SUPP-01: Support multiple firmware versions
- [ ] SUPP-02: Implement configuration file parsing

## Out of Scope
- [ ] Full test suite with hardware-in-loop testing
- [ ] Web API for firmware upload
- [ ] GUI for progress monitoring

## Traceability
| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | Phase 1 | Pending |
| AUTH-02 | Phase 1 | Pending |
| BLOCK-01 | Phase 2 | Complete |
| BLOCK-02 | Phase 2 | Complete |
| BLOCK-03 | Phase 2 | Complete |
| ERR-01 | Phase 2 | Pending |
| TEST-01 | Phase 3 | Pending |

**Coverage:** 6 v1 requirements in scope | 0 unmapped