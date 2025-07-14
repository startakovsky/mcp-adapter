#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "httpx==0.28.*",
# ]
# ///
"""
Debug script to test file upload and see what filename is actually saved
"""

import asyncio
import httpx
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unit.test_utils import get_test_filename

class MCPToolHelper:
    """Helper class for MCP tool calls with proper session management"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = None
        self.client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        timeout = httpx.Timeout(20.0, connect=10.0)
        limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
        self.client = httpx.AsyncClient(timeout=timeout, limits=limits)
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def initialize(self):
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
                    "name": "debug-client",
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
    
    async def call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        """Call MCP tool and return parsed result"""
        if not self.client or not self.session_id:
            raise RuntimeError("Session not initialized")
        
        if arguments is None:
            arguments = {}
            
        request = {
            "jsonrpc": "2.0",
            "id": f"debug_{tool_name}",
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
    
    def _parse_sse_response(self, response_text: str) -> dict:
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
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
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

async def test_upload():
    """Test file upload and check what filename is saved"""
    
    # Generate a test filename
    test_filename = get_test_filename("debug_test", "tex", "upload")
    print(f"Generated filename: {test_filename}")
    
    # Test content
    content = r"""
\documentclass{article}
\begin{document}
Debug test document
\end{document}
"""
    
    # Test 1: Upload through gateway
    print("\n=== Testing through Gateway ===")
    async with MCPToolHelper("http://localhost:8080") as helper:
        result = await helper.call_tool(
            "latex_upload_latex_file",
            {
                "content": content,
                "filename": test_filename
            }
        )
        
        print(f"Gateway upload result: {json.dumps(result, indent=2)}")
        
        if result.get("success"):
            print(f"Uploaded filename: {result.get('filename')}")
            print(f"File ID: {result.get('file_id')}")
    
    # Test 2: Upload directly to LaTeX server
    print("\n=== Testing directly to LaTeX Server ===")
    async with MCPToolHelper("http://localhost:8002") as helper:
        result = await helper.call_tool(
            "upload_latex_file",
            {
                "content": content,
                "filename": test_filename
            }
        )
        
        print(f"Direct upload result: {json.dumps(result, indent=2)}")
        
        if result.get("success"):
            print(f"Uploaded filename: {result.get('filename')}")
            print(f"File ID: {result.get('file_id')}")
    
    # Check what's actually in the uploads directory
    print("\n=== Files in uploads directory ===")
    import os
    from pathlib import Path
    
    uploads_dir = Path("../latex-server/uploads")
    if uploads_dir.exists():
        files = list(uploads_dir.glob("*.tex"))
        print(f"Files in uploads directory:")
        for file in files:
            print(f"  - {file.name}")
    else:
        print("Uploads directory does not exist")

if __name__ == "__main__":
    asyncio.run(test_upload()) 