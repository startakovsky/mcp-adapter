"""
MCP Session Helper Functions

Provides utilities for managing MCP sessions and parsing responses in tests.
"""

import json
import httpx
from typing import Dict, Any, Optional, List


class MCPSession:
    """Helper class for managing MCP sessions in tests"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient()
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
                    "name": "mcp-test-client",
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
            raise RuntimeError("No session ID returned from initialize")
        
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
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None, request_id: str = None) -> Dict[str, Any]:
        """Call a tool with proper session management"""
        if not self.client or not self.session_id:
            raise RuntimeError("Session not initialized")
        
        if arguments is None:
            arguments = {}
        
        if request_id is None:
            request_id = f"call-{tool_name}-{id(arguments)}"
        
        tool_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = await self.client.post(
            f"{self.base_url}/mcp/",
            json=tool_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self.session_id
            }
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Tool call failed: {response.status_code} - {response.text}")
        
        return self._parse_sse_response(response.text)
    
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools"""
        if not self.client or not self.session_id:
            raise RuntimeError("Session not initialized")
        
        tools_request = {
            "jsonrpc": "2.0",
            "id": "tools-list",
            "method": "tools/list",
            "params": {}
        }
        
        response = await self.client.post(
            f"{self.base_url}/mcp/",
            json=tools_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self.session_id
            }
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Tools list failed: {response.status_code} - {response.text}")
        
        return self._parse_sse_response(response.text)
    
    async def raw_request(self, method: str, params: Dict[str, Any] = None, request_id: str = None) -> httpx.Response:
        """Make a raw MCP request and return the response"""
        if not self.client or not self.session_id:
            raise RuntimeError("Session not initialized")
        
        if params is None:
            params = {}
        
        if request_id is None:
            request_id = f"raw-{method}-{id(params)}"
        
        request_data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        return await self.client.post(
            f"{self.base_url}/mcp/",
            json=request_data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self.session_id
            }
        )
    
    def _parse_sse_response(self, sse_text: str) -> Dict[str, Any]:
        """Parse Server-Sent Events response format"""
        lines = sse_text.strip().split('\n')
        
        # Find the data line
        data_line = None
        for line in lines:
            if line.startswith('data: '):
                data_line = line[6:]  # Remove 'data: ' prefix
                break
        
        if not data_line:
            raise ValueError(f"No data line found in SSE response: {sse_text}")
        
        try:
            return json.loads(data_line)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in SSE data: {data_line}") from e


async def create_mcp_session(base_url: str) -> MCPSession:
    """Create and initialize an MCP session"""
    session = MCPSession(base_url)
    await session.initialize()
    return session


def extract_tool_names(tools_result: Dict[str, Any]) -> List[str]:
    """Extract tool names from tools/list result"""
    if "result" not in tools_result:
        return []
    
    result = tools_result["result"]
    if "tools" not in result:
        return []
    
    tools = result["tools"]
    if not isinstance(tools, list):
        return []
    
    return [tool.get("name", "") for tool in tools if isinstance(tool, dict)]


def extract_tool_result_content(tool_result: Dict[str, Any]) -> str:
    """Extract content from tool call result"""
    if "result" not in tool_result:
        return ""
    
    result = tool_result["result"]
    
    # Handle direct string results
    if isinstance(result, str):
        return result
    
    # Handle structured results with content
    if isinstance(result, dict):
        if "content" in result:
            content = result["content"]
            if isinstance(content, list) and len(content) > 0:
                first_content = content[0]
                if isinstance(first_content, dict) and "text" in first_content:
                    return first_content["text"]
            elif isinstance(content, str):
                return content
        
        # Handle direct result values
        if "value" in result:
            return str(result["value"])
    
    return str(result)