#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "pytest==8.4.*",
#     "pytest-asyncio==1.0.*",
#     "httpx==0.28.*",
#     "fastmcp>=2.10",
# ]
# ///
"""
Integration test fixtures and utilities
"""

import pytest
import httpx
import tempfile
from pathlib import Path
from typing import Dict, Any, AsyncGenerator
import json
import asyncio
import sys
import os

# Add the tests directory to the path so we can import test_utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unit.test_utils import (
    get_test_filename, 
    cleanup_test_files, 
    ensure_test_directories,
    TEST_FILE_PREFIX
)

# Test configuration
GATEWAY_URL = "http://localhost:8080"
LATEX_SERVER_URL = "http://localhost:8002"

@pytest.fixture
def sample_latex_document() -> str:
    """Sample LaTeX document for testing"""
    return r"""
\documentclass{article}
\usepackage{amsmath}
\begin{document}
\title{Integration Test Document}
\author{Test Suite}
\date{\today}
\maketitle

\section{Introduction}
This is a test document for integration testing.

\section{Mathematics}
Here's a formula: $E = mc^2$

\begin{equation}
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
\end{equation}

\section{Lists}
\begin{itemize}
\item First item
\item Second item
\item Third item
\end{itemize}

\end{document}
"""

@pytest.fixture
def invalid_latex_document() -> str:
    """Invalid LaTeX document for error testing"""
    return r"""
\documentclass{article}
\begin{document}
\title{Broken Document}
\invalid_command{this will fail}
\missing_brace{unclosed
\end{document}
"""

@pytest.fixture
def large_latex_document() -> str:
    """Large LaTeX document for size testing"""
    content = r"""
\documentclass{article}
\begin{document}
\title{Large Document}
\author{Test Suite}
\maketitle

"""
    # Add many paragraphs
    for i in range(1000):
        content += f"This is paragraph {i}. " + "Lorem ipsum dolor sit amet. " * 10 + "\n\n"
    
    content += r"\end{document}"
    return content

@pytest.fixture
async def mcp_session() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client with MCP session initialization"""
    timeout = httpx.Timeout(20.0, connect=10.0)  # More generous timeouts for stability
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)  # Better connection pooling
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        yield client

@pytest.fixture
def temp_tex_file(sample_latex_document: str) -> Path:
    """Create temporary .tex file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.tex', delete=False) as f:
        f.write(sample_latex_document)
        return Path(f.name)

@pytest.fixture(autouse=True)
def cleanup_test_files_fixture():
    """Automatically clean up test files before and after each test"""
    # Ensure test directories exist
    ensure_test_directories()
    
    # Clean up before test
    cleanup_test_files()
    
    yield
    
    # Clean up after test
    cleanup_test_files()

@pytest.fixture
def test_filename():
    """Fixture to generate test filenames with proper prefix, descriptor, and identifier"""
    def _get_test_filename(base_name: str, extension: str = "", descriptor: str = "") -> str:
        return get_test_filename(base_name, extension, descriptor)
    return _get_test_filename

class MCPToolHelper:
    """Helper class for MCP tool calls with proper session management"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = None
        self.client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        # Optimized timeout and connection settings for concurrent operations
        timeout = httpx.Timeout(20.0, connect=10.0)  # More generous timeouts for concurrent operations
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)  # Increased connection pool
        self.client = httpx.AsyncClient(timeout=timeout, limits=limits)
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize MCP session with proper handshake"""
        if not self.client:
            raise RuntimeError("Client not initialized")
            
        # Step 1: Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "integration-test-client",
                    "version": "0.3.0"
                },
                "capabilities": {}
            }
        }
        
        response = await self.client.post(
            f"{self.base_url}/mcp/",
            json=init_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Initialize failed: {response.status_code} - {response.text}")
        
        # Extract session ID from response headers
        self.session_id = response.headers.get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError(f"No session ID returned from initialize. Headers: {dict(response.headers)}")
        
        # Parse SSE response
        init_result = self._parse_sse_response(response.text)
        
        # Step 2: Send initialized notification
        initialized_request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        notify_response = await self.client.post(
            f"{self.base_url}/mcp/",
            json=initialized_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self.session_id
            }
        )
        
        if notify_response.status_code not in [200, 202]:
            raise RuntimeError(f"Initialized notification failed: {notify_response.status_code}")
        
        return init_result
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call MCP tool and return parsed result"""
        if not self.client or not self.session_id:
            raise RuntimeError("Session not initialized")
        
        if arguments is None:
            arguments = {}
            
        request = {
            "jsonrpc": "2.0",
            "id": f"test_{tool_name}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = await self.client.post(
            f"{self.base_url}/mcp/",
            json=request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self.session_id
            }
        )
        
        if response.status_code == 200:
            return self._parse_sse_response(response.text)
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    
    def _parse_sse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse MCP response from SSE format"""
        lines = response_text.strip().split('\n')
        
        # Find the data line
        data_line = None
        for line in lines:
            if line.startswith('data: '):
                data_line = line[6:]  # Remove 'data: ' prefix
                break
        
        if not data_line:
            return {"success": False, "error": f"No data line found in SSE response: {response_text}"}
        
        try:
            data = json.loads(data_line)
            if "result" in data:
                result = data["result"]
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if content and isinstance(content, list):
                        text = content[0].get("text", "{}")
                        # Try to parse as JSON, but if it fails, treat as plain text
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            # If parsing fails, it's a plain text response (possibly an error)
                            if result.get("isError"):
                                return {"success": False, "error": text}
                            else:
                                return {"success": True, "message": text}
                return result
            elif "error" in data:
                return {"success": False, "error": data["error"]}
            else:
                return data
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON in SSE data: {data_line}"}
        
        return {"success": False, "error": "Failed to parse response"}

@pytest.fixture
async def gateway_helper():
    """Helper for gateway tool calls with proper MCP session"""
    async with MCPToolHelper(GATEWAY_URL) as helper:
        yield helper

@pytest.fixture
async def latex_helper():
    """Helper for direct LaTeX server tool calls with proper MCP session"""
    async with MCPToolHelper(LATEX_SERVER_URL) as helper:
        yield helper

async def debug_list_tools():
    """Utility to print all tools available via MCPToolHelper session."""
    async with MCPToolHelper(GATEWAY_URL) as helper:
        # List tools via MCP protocol
        request = {
            "jsonrpc": "2.0",
            "id": "tools-list-debug",
            "method": "tools/list",
            "params": {}
        }
        response = await helper.client.post(
            f"{helper.base_url}/mcp/",
            json=request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": helper.session_id
            }
        )
        print("Status:", response.status_code)
        print("Response:", response.text)

if __name__ == "__main__":
    asyncio.run(debug_list_tools())