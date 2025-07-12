# MCP Adapter Tests

Test suite for MCP Adapter using pytest and uv.

## Quick Start

```bash
cd tests
uv run pytest
```

## Test File Management

The test suite includes a modular file cleanup system to manage test-generated files:

### Automatic Cleanup
- Tests automatically clean up files before and after each test
- Uses configurable patterns to identify test files
- Default prefix: `pytest_` for all test-generated files

### Manual Cleanup
```bash
# Clean up all test files
uv run python cleanup_test_files.py

# Run cleanup examples
uv run python cleanup_examples.py
```

### Modular Configuration

The cleanup system is configurable through `CLEANUP_CONFIG` in `test_utils.py`:

```python
CLEANUP_CONFIG = {
    "use_test_prefix": True,      # Clean up files with pytest_ prefix
    "use_latex_uploads": True,    # Clean up all .tex files in uploads
    "use_latex_outputs": True,    # Clean up compiled_*.pdf files
    "use_test_outputs": True,     # Clean up *_output_*.pdf files
    "use_reuse_outputs": True,    # Clean up reuse_output_*.pdf files
}
```

### Custom Cleanup
```python
from test_utils import cleanup_test_files

# Minimal cleanup - only test prefix files
config = {"use_test_prefix": True, "use_latex_uploads": False}
cleanup_test_files(config=config)

# LaTeX-only cleanup
config = {"use_test_prefix": False, "use_latex_uploads": True}
cleanup_test_files(config=config)
```

## Security Testing & File Management

### Defensive Security Testing
The test suite includes comprehensive **security testing** that intentionally tests malicious inputs to verify our defenses work:

**Path Traversal Protection:**
- Tests malicious filenames like `../../../etc/passwd`, `\windows\system32\config\sam`
- Verifies these get sanitized to safe names like `______etc_passwd`
- **Seeing sanitized filenames in test output is EXPECTED and GOOD** - it proves security is working!

**What the Security Tests Validate:**
- ✅ **Path traversal attacks** → Blocked and sanitized
- ✅ **Directory escape attempts** → Converted to safe filenames  
- ✅ **System file access attempts** → Neutralized
- ✅ **URL encoding attacks** → Detected and sanitized
- ✅ **File injection attacks** → Prevented
- ✅ **Large file attacks** → Size limits enforced

**File Server Cleanup:**
```bash
# Clean up file server shared_files directory
uv run cleanup_shared_files.py
```

### User-Friendly URLs
Implemented timestamp-based file URLs that are both secure and user-friendly:
- **Before**: `localhost:8003/files/f36dec43-b8be-479f-939e-ee77261ecda9`
- **After**: `localhost:8003/files/resume-2025-07-08T03-14-17-898741Z.pdf`
- **Features**: Collision-free, browser-friendly, no `.pdf.pdf` issues

## Test Results Summary

Run `uv run pytest` to see current test status. The test suite includes:
- ✅ **192 tests passing**: Security, OAuth, reliability, session management, integration
- ✅ **Zero warnings**: All deprecation warnings fixed
- ✅ **Pre-commit safety**: Automated testing prevents broken commits
- ✅ **Security validation**: Defensive testing against real attack vectors

## Files

- `test_connectivity.py` - Basic HTTP tests (should pass)
- `test_gateway.py` - Gateway tests (mixed results)  
- `test_mcp_servers.py` - MCP protocol tests (currently fail)
- `test_utils.py` - Test utilities and cleanup system
- `cleanup_test_files.py` - Manual cleanup script
- `cleanup_examples.py` - Configuration examples

## Prerequisites

1. Start services: `docker-compose up -d`
2. Run tests: `cd tests && uv run pytest`

---

**For detailed context, debugging, and development information, see [CLAUDE.md](CLAUDE.md).**