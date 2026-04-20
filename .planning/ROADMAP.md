# Roadmap: Delta-Q CANopen Reprogramming Tool

## Overview
Phased approach to implementation based on priority and complexity from the requirements analysis.

## Phase Structure
| Phase | Goal | Requirements | Success Criteria | Estimated Duration |
|-------|------|--------------|------------------|-------------------|
| Phase 1: Authentication | Implement SDO authentication sequence | AUTH-01, AUTH-02 | Successful key exchange validated | 1-2 weeks |
| Phase 2: Block Transfer | Implement full SDO block download protocol | BLOCK-01, BLOCK-02, BLOCK-03 | Successful firmware transfer verified | 2-3 weeks |
| Phase 3: Error Handling | Implement robust error recovery system | ERR-01, ERR-02 | Successful retry logic demonstrated | 1-2 weeks |
| Phase 4: Testing Framework | Build test infrastructure | TEST-01, TEST-02 | Automated tests passing | Ongoing |

## Resource Allocation
<details>
<summary>Phase 1</summary>
<ul>
    <li>1 CAN Protocol Engineer</li>
    <li>1 Test Engineer</li>
</ul>
</details>

## Timeline
```mermaid
graph TD
A[Start] --> B[Phase 1: Authentication (Weeks 1-3)]
B --> C[Phase 2: Block Transfer (Weeks 4-7)]
C --> D[Phase 3: Error Handling (Weeks 8-10)]
D --> E[Phase 4: Testing (Weeks 11-14)]
```

## Verification Strategy
1. Phase 1: Lab bench testing with CAN bus analyzer
2. Phase 2: Real charger interaction tests
3. Phase 3: Automated fault injection testing
4. Phase 4: Regression testing with different firmware versions

## Risk Assessment
**High Risks:**
- Timing synchronization in SDO transfers
- CAN bus message corruption detection
**Mitigation:**
- Implement CRC validation checks
- Add message sequence logging

## Dependency Tracking
- Sync between firmware validation and authentication implementation
- Block download development dependent on CANopen protocol implementation

## Approval Status
<details>
<summary>Roadmap Review</summary>
  <table>
    <tr><th>Requirement Group</th><th>Approved</th></tr>
    <tr><td>Authentication</td><td>Security compliance check pending</td></tr>
    <tr><td>Block Transfer</td><td>Approved by firmware team</td></tr>
    <tr><td>Error Handling</td><td>Pending initial review</td></tr>
    <tr><td>Testing Framework</td><td>Approved by QA team</td></tr>
  </table>
</details>

### Phase 5: Support Zip files

**Goal:** Add ZIP archive support to firmware loading, enabling extraction of .bin files from ZIP archives
**Requirements**: FIRM-01, FIRM-02
**Depends on:** Phase 2 (Block Transfer)
**Plans:** 1 plan

Plans:
- [x] 05-01-PLAN.md — Add ZIP extraction support to FirmwareLoader

---
*Last updated: 2026-04-10*