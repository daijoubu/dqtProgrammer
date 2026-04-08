# Phase 1: Authentication - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement SDO authentication sequence with seed/key exchange per CiA 301/302 and Delta-Q specifications. This phase delivers the authentication module that other phases will depend on.

</domain>

<decisions>
## Implementation Decisions

### Timeout Strategy
- Seed request timeout: 1-2 seconds (Short)
- Key response timeout: 1-2 seconds (Short)
- Rationale: Quick response expected from charger on local CAN network

### Failure Handling
- Primary strategy: Fail Fast
- On authentication failure: Move to next charger (if batch processing)
- Log failure details for debugging
- Do not attempt recovery during authentication

### Retry Policy
- Maximum attempts before lockout: 3
- Rationale: Matches Delta-Q specification (3 failures triggers 30-second lockout)
- No custom retry logic - respect the charger's lockout mechanism

### Secret Management
- Storage: Config file (JSON or YAML)
- Location: Project config directory, not committed to version control
- Must be excluded via .gitignore
- Config file format should support multiple charger configurations

</decisions>

<specifics>
## Specific Ideas

- Config file should support defining multiple charger targets with different secrets
- Clear error messages when authentication fails (not just "failed" but specific reason)
- Logging should capture: timestamp, charger ID, failure reason, retry count

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- python-can library: For CAN bus communication
- No existing authentication patterns in this project (greenfield)

### Established Patterns
- Using python-can for CAN interface abstraction
- Follow CiA 301/302 SDO protocol specifications

### Integration Points
- Authentication module will be used by block download phase
- Config file format should be extensible for future parameters

</code_context>

<deferred>
## Deferred Ideas

- GUI for secret management - Phase 4 (out of scope for now)
- Environment variable fallback - noted for future consideration

</deferred>

---

*Phase: 01-authentication*
*Context gathered: 2026-04-08*