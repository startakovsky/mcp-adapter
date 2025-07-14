# MCP Adapter Tests - Context for Claude Code

This directory contains a comprehensive test suite for MCP Adapter, built with pytest and uv. The test infrastructure includes 8 dedicated test files covering security, OAuth flows, service reliability, and session management scenarios.

## Quick Start

```bash
# Navigate to tests directory
cd tests

# Run all tests
uv run pytest

# Run specific test files
uv run pytest test_connectivity.py
uv run pytest test_gateway.py  
uv run pytest test_mcp_servers.py

# Run with specific options
uv run pytest -k "connectivity"  # Only connectivity tests
uv run pytest -x                 # Stop on first failure
uv run pytest --tb=long         # Detailed failure info
```

## Test Architecture

### Testing Philosophy

MCP Adapter follows a layered testing approach:
- **Gateway tests** focus on discovery, routing, and proxying between services
- **Individual server tests** focus on tool implementations and business logic
- **Connectivity tests** verify basic HTTP functionality

### Test Categories

1. **`test_connectivity.py`** - Basic HTTP connectivity tests
   - Health endpoints, info endpoints, dashboard access
   - OAuth discovery for Claude Code compatibility
   - **Should always pass** when services are running

2. **`test_gateway.py`** - Gateway functionality tests
   - Gateway connectivity to backend servers
   - Tool discovery and aggregation from multiple servers
   - Tool proxying and routing to correct backend
   - Error handling for backend failures

3. **`test_mcp_servers.py`** - Gateway MCP protocol compliance tests
   - MCP protocol testing at the gateway level
   - Tool listing aggregation from all servers
   - Error handling for invalid MCP requests

4. **Comprehensive test coverage** - 8 additional test files:
   - **Security**: Injection prevention, file validation, path traversal protection
   - **OAuth flows**: Complete authorization flow validation
   - **Service reliability**: Failure scenarios, timeout handling, load balancing
   - **Session management**: Lifecycle, concurrency, expiration handling
   - **Unit tests**: Core logic for gateway and LaTeX server components

5. **Server-specific tests** - Individual tool implementation tests
   - `hello-world/test_hello_world.py` - Hello World server tools
   - `latex-server/test_latex_server.py` - LaTeX server tools
   - Each server tests its own tool implementations in isolation

### Expected Results

**Gateway tests** (in `tests/` directory):
- ✅ **Connectivity tests**: All HTTP endpoints should be accessible
- ✅ **Gateway functionality**: Tool discovery, proxying, error handling
- ✅ **Security & OAuth**: Comprehensive security validation and authentication flows
- ✅ **Reliability & Sessions**: Failure handling and session management
- ⚠️ **MCP protocol tests**: May fail if session management is not properly configured

**Server tests** (in individual server directories):
- ✅ **Hello World tools**: greet, add_numbers, get_timestamp
- ⚠️ **LaTeX tools**: May require LaTeX installation (pdflatex) for compilation tests

**Test execution priorities:**
1. Run gateway tests to verify service integration
2. Run individual server tests to verify tool implementations
3. Both test suites are independent and can run separately

## Configuration

### Dependencies (pyproject.toml)
- **Python**: 3.12 (required)
- **pytest**: 8.4.* (latest)
- **httpx**: 0.28.* (latest)
- **pytest-asyncio**: 1.0.* (latest)
- **aiofiles**: 23.2.* (for file server testing)

### Pytest Configuration
- **asyncio_mode**: auto (handles async tests automatically)
- **Default flags**: verbose output, short traceback format
- **Test discovery**: Automatic (follows pytest conventions)

## Test Environment

### Prerequisites
1. **Docker running**: `docker info` should work
2. **Services running**: `docker-compose up -d` from project root
3. **Ports available**: 8080 (gateway), 8001 (hello-world)

### Service URLs
- **Gateway**: http://localhost:8080
- **Hello World**: http://localhost:8001

## Understanding Test Failures

### FastMCP Unit Test Patterns
**CRITICAL**: Functions decorated with `@mcp.tool` become FunctionTool objects, not direct callables.

**Common Unit Test Error**:
```
TypeError: 'FunctionTool' object is not callable
```

**Fix**: Access the underlying function via tool registry:
```python
# Wrong
result = await server.compile_latex(request)

# Correct  
compile_tool = server.mcp.tools["compile_latex"]
result = await compile_tool.func(request)
```

**Tool Registry Access Pattern**:
- `server.mcp.tools["tool_name"]` - Gets the FunctionTool object
- `tool.func(args)` - Calls the underlying async function
- Non-decorated helpers can be called directly: `server.sanitize_filename()`

### MCP Protocol Failures (Expected)
All MCP tool calls return `400 Bad Request` with "Missing session ID" error. This indicates:

1. **FastMCP requires session management** for tool calls
2. **HTTP endpoints work fine** (health, info, dashboard)
3. **This is the root cause** of `/mcp` connection issues in Claude Code

### Debugging Failed Tests
```bash
# Run only passing tests to verify connectivity
uv run pytest test_connectivity.py

# Run specific failing test with details
uv run pytest test_gateway.py::TestMCPToolCalls::test_mcp_tool_call_greet -v --tb=long

# See all test output without truncation
uv run pytest -s
```

## Development Workflow

### Testing During Feature Development

**CRITICAL**: When building features with Claude Code, do not be overconfident about tests passing after changes. Test early and often.

**Testing Best Practices**:
1. **Test Before Changes**: Run baseline tests to confirm clean state
2. **Test During Development**: Run relevant test subsets frequently as you build
3. **Test After Each Major Change**: Don't wait until the end to discover issues
4. **Test Edge Cases**: Consider what might break and test those scenarios
5. **Test Integration Points**: When modifying multiple components, test interactions

**Example Testing Workflow**:
```bash
# Before starting feature work
cd /Users/steven/code/mcp-adapter/tests && uv run pytest test_connectivity.py

# After making gateway changes
cd /Users/steven/code/mcp-adapter/tests && uv run pytest test_gateway.py

# After adding new endpoints or session management
cd /Users/steven/code/mcp-adapter/tests && uv run pytest test_session_management.py

# After completion - full test suite
cd /Users/steven/code/mcp-adapter/tests && uv run pytest
```

**Why This Matters**:
- Complex features often break existing functionality in unexpected ways
- Early detection saves significant debugging time
- Integration issues are easier to fix when caught immediately
- Test failures guide implementation decisions and reveal edge cases
- Confidence in changes comes from proven test coverage, not assumptions

### Testing New Services

When a new service is added to the project, it requires two layers of testing:

1.  **Server-Specific Tests (In-depth)**:
    - In the new service's directory (e.g., `new-service/`), create a `test_new_service.py` file.
    - These tests should be comprehensive, validating all tool implementations and business logic for the service *in isolation*.
    - They should make requests directly to the service's own URL (e.g., `http://localhost:800X`), not through the gateway.
    - The `hello-world/test_hello_world.py` file provides a good example to follow.

2.  **Gateway Integration Tests (Minimal)**:
    - In `tests/test_mcp_servers.py`, add minimal checks to ensure the new service is integrated correctly with the gateway.
    - **Tool Discovery**: In `TestGatewayMCPProtocol.test_gateway_mcp_tools_list`, add an assertion to verify that tools from your new service (e.g., prefixed with `new_service_`) are present in the aggregated tool list.
    - **Tool Proxying**: Add a simple test case similar to `TestGatewayToolProxy.test_gateway_proxy_greet` that calls one of your new tools *through the gateway* and validates a successful response. This confirms the gateway is routing requests correctly.

This layered approach ensures that individual services are robust on their own, while the gateway tests remain lightweight and focused on integration, preventing duplication of test logic.

### Running Tests During Development

**Gateway tests (from tests/ directory):**
```bash
cd tests

# Quick connectivity check
uv run pytest test_connectivity.py

# Gateway functionality
uv run pytest test_gateway.py

# Full gateway test suite
uv run pytest
```

**Individual server tests:**
```bash
# Hello World server tests
cd hello-world
uv run pytest test_hello_world.py

# LaTeX server tests  
cd latex-server
uv run pytest test_latex_server.py
```

**Complete test suite:**
```bash
# From project root
cd tests && uv run pytest && cd ../hello-world && uv run pytest && cd ../latex-server && uv run pytest
```

## File Structure

```
tests/
├── CLAUDE.md              # This file - context for Claude Code
├── README.md              # Simple user-facing documentation  
├── pyproject.toml         # Dependencies and pytest configuration
├── test_connectivity.py   # Basic HTTP connectivity tests
├── test_gateway.py        # Gateway functionality tests
├── test_mcp_servers.py    # Gateway MCP protocol tests
├── test_mcp_initialization.py # MCP session initialization tests
├── mcp_session_helper.py  # Helper utilities for MCP testing
└── uv.lock               # Dependency lock file (auto-generated)

hello-world/
└── test_hello_world.py    # Hello World server tool tests

latex-server/
└── test_latex_server.py   # LaTeX server tool tests
```

## Troubleshooting

### Common Issues

1. **Services not running**: Ensure `docker-compose up -d` was run from project root
2. **Port conflicts**: Check if ports 8080/8001 are available
3. **All tests fail**: Docker services may not be accessible

### Service Status Check
```bash
# Check Docker services
docker-compose ps

# Check service health
curl http://localhost:8080/health
curl http://localhost:8001/health

# View service logs
docker-compose logs gateway
docker-compose logs hello-world
```

### Test Debugging
```bash
# Run with Python debugger on failure
uv run pytest --pdb

# Run specific test class
uv run pytest test_connectivity.py::TestBasicConnectivity

# Get detailed HTTP request/response info
uv run pytest -s -v test_connectivity.py
```

## Integration with Claude Code

These tests help identify why Claude Code's `/mcp` command fails to connect:

1. **Connectivity tests pass** → Services are accessible
2. **MCP protocol tests fail** → Session management issue
3. **Next step**: Implement proper session handling in FastMCP servers

The test failures provide precise debugging information for fixing the MCP connection issues.

## Claude Code Working Directory Best Practices

**CRITICAL**: Claude Code must always be aware of current working directory when using file operations.

### Common Directory Mistake Pattern
```
❌ WRONG: Use Glob tool from /Users/steven/code/mcp-adapter/tests
    Glob pattern: ".github/workflows/*.yml"
    Result: No files found (wrong relative path)

✅ CORRECT: Check working directory first
    Current dir: /Users/steven/code/mcp-adapter/tests  
    Glob pattern: "../.github/workflows/*.yml"
    Result: Found CI files
```

### Required Directory Awareness Workflow
1. **Always establish context first**: Use `pwd`, `LS`, or check working directory
2. **Use proper relative paths**: Account for subdirectories (e.g., `../` to go up from tests/)
3. **When in doubt, use absolute paths**: `/Users/steven/code/mcp-adapter/.github/workflows/`
4. **Test patterns with small examples**: Verify path logic before using complex operations

### Directory Context Patterns
```bash
# When in tests/ directory:
../                           # Project root
../.github/workflows/        # CI configuration  
../file-server/             # File server code
../latex-server/templates/  # LaTeX templates

# When in project root:
.github/workflows/          # CI configuration
file-server/               # File server code
tests/                     # Test directory
```

**Lesson**: Directory context mistakes lead to "file not found" errors that waste time and confuse debugging. Always verify location before file operations.

## CI/CD Pipeline Architecture

### Current Workflow Issues

**Problem with Current Design**: The pipeline detects changes first, then sets up Docker, but this creates inefficiency and complexity.

**Current Flow**:
```
1. detect-changes → Analyze what changed (code vs docker)
2. setup-docker → Build/pull images (only if changes detected)  
3. unit-tests → Depends on setup-docker completion
4. integration-tests → Depends on setup-docker completion
```

**Issue**: Jobs wait for change detection and Docker setup even when we could start with cached images.

### Improved Workflow Design

**Better Approach**: Start with image availability, then optimize based on what's needed.

**Optimal Flow**:
```
1. lint-and-security → Fast feedback (no Docker needed)
2. check-images → Quick GHCR image availability check
3. build-images → Only if images missing or code changed
4. unit-tests → Run with available images
5. integration-tests → Run with available images
```

### Pipeline Trigger Logic

**Current Triggers**:
```yaml
on:
  push:
    branches: [ main, develop ]  # Only main/develop pushes
  pull_request:
    branches: [ main ]           # PRs to main trigger pipeline
```

**Expected Behavior**:
- ✅ **Pull Request Creation**: Triggers full pipeline
- ✅ **Push to main/develop**: Triggers full pipeline  
- ❌ **Feature branch pushes**: No trigger (by design)

### Image Management Strategy

**GHCR Image Lifecycle**:
```bash
# First PR run: Images don't exist
📦 Images missing from GHCR → Build and push all images

# Subsequent runs: Images exist
✅ All images exist in GHCR → Pull cached images (fast)

# Code changes: Rebuild needed  
🔨 Code changed → Build and push updated images
```

**Current Issue**: Even with cached images, pipeline waits for "detect-changes" job completion.

### Optimization Recommendations

**1. Parallel Job Structure**:
```yaml
jobs:
  lint-and-security:     # Fast feedback
  check-image-cache:     # Quick GHCR check
  
  # Run in parallel after cache check
  unit-tests:
    needs: [check-image-cache]
  integration-tests: 
    needs: [check-image-cache]
  build-if-needed:       # Only if cache miss
    needs: [check-image-cache]
```

**2. Smart Caching**:
- Use GHCR as primary cache
- Fall back to building only when necessary
- Parallel test execution with cached images

**3. Remove Change Detection**:
- Always check image availability first
- Build incrementally based on actual needs
- Faster feedback for common scenarios

### Unit Test Dependencies

**Current Problem**: Unit tests are labeled "no Docker required" but actually need Docker services.

**Analysis**:
```python
# unit/test_gateway_core.py
import gateway  # Imports real gateway module
await gateway.get_backend_session(server_url)  # Needs Docker services
```

**These are actually integration tests** because they:
- Import real modules with external dependencies
- Make HTTP calls to Docker services
- Test full service interaction

**Solutions**:
1. **True Unit Tests**: Mock all external dependencies
2. **Rename to Integration**: Move to integration/ and update descriptions
3. **Hybrid Approach**: Split pure logic tests from service interaction tests

### Performance Optimization

**Current**: ~5+ minutes for first run (detect → setup → test)
**Optimized**: ~2-3 minutes (cache check → parallel test)

**Key Improvements**:
- Eliminate unnecessary job dependencies
- Parallel execution where possible  
- Smarter image caching strategy
- Faster feedback for common scenarios