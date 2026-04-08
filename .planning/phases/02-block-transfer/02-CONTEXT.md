# Phase 2: Block Transfer - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement SDO block download protocol for firmware transfer per CiA 301/302 and Delta-Q specifications. This phase delivers the firmware download capability after authentication is complete.

</domain>

<decisions>
## Implementation Decisions

### Transfer Mode
- SDO Block Download (recommended)
- More efficient for large firmware files
- Per Delta-Q specification

### CRC Handling
- Include CRC validation (recommended)
- Verify data integrity during/after transfer
- Required per Delta-Q spec

### Progress Reporting
- Console output (recommended)
- Show percentage and bytes transferred
- Update every block/sub-block

### Error Recovery
- Resume from last successful block (recommended)
- Need to track last successful block position
- Alternative: restart or abort

</decisions>

<specifics>
## Specific Ideas

- Use canopen library's block transfer capabilities if available
- Follow Delta-Q's block size (127 segments = 889 bytes default)
- Handle 15-second erase time on first block
- Subsequent blocks should be faster (~hundreds of ms)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- src/auth.py: Uses canopen library (can reuse same pattern)
- tests/test_hardware.py: Hardware tests with canopen

### Established Patterns
- Using python-can + canopen for SDO operations
- Authentication complete - block download builds on that

### Integration Points
- Depends on Phase 1 (Authentication)
- Uses canopen.SdoClient for firmware upload

</code_context>

<deferred>
## Deferred Ideas

- Multiple firmware version support - Phase 3+
- Configuration file for firmware specs - Phase 3+

</deferred>

---

*Phase: 02-block-transfer*
*Context gathered: 2026-04-08*