# Phase 1: Support Zip files - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning
**Source:** Initial phase addition

<domain>
## Phase Boundary

Add support for loading firmware from ZIP archives. The tool should automatically extract the `.bin` file from a ZIP and use it for the reprogramming process.

</domain>

<decisions>
## Implementation Decisions

### Core Functionality
- Load firmware from .zip files in addition to .bin files
- Automatically detect and extract .bin file from ZIP archive
- Handle cases where ZIP contains multiple .bin files (use first or error)
- Preserve existing .bin file loading functionality

### Error Handling
- Clear error messages when ZIP doesn't contain a valid .bin file
- Handle corrupted ZIP files gracefully
- Validate extracted firmware after extraction

### User Interface
- Accept both .bin and .zip paths in the firmware loader
- No change to existing API contracts

</decisions>

<specifics>
## Specific Ideas

- Use Python's `zipfile` module for extraction
- Check for .bin extension (case-insensitive)
- First matching .bin file is used
- Clean up extracted files after transfer (or use temp directory)

</specifics>

<deferred>
## Deferred Ideas

- None - this is a focused feature addition

</deferred>

---

*Phase: 01-support-zip-files*
*Context gathered: 2026-04-10*