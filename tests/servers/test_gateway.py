"""
Gateway connectivity tests
"""

import pytest
import httpx

from mcp_session_helper import MCPSession, extract_tool_result_content
import asyncio
from typing import Dict, Any

# Test configuration
GATEWAY_URL = "http://localhost:8080"
HELLO_WORLD_URL = "http://localhost:8001"


class TestGatewayConnectivity:
    """Test basic gateway connectivity"""

    @pytest.mark.asyncio
    async def test_gateway_health(self):
        """Test gateway health endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data
            assert "servers" in data
            assert "tools" in data

    @pytest.mark.asyncio
    async def test_gateway_info(self):
        """Test gateway info endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/info")
            assert response.status_code == 200
            
            data = response.json()
            assert data["name"] == "MCP Adapter"
            assert "version" in data
            assert "connected_servers" in data
            assert "available_tools" in data
            assert isinstance(data["available_tools"], list)

    @pytest.mark.asyncio
    async def test_gateway_dashboard(self):
        """Test gateway dashboard endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/dashboard")
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_oauth_discovery(self):
        """Test OAuth discovery endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/.well-known/oauth-authorization-server")
            assert response.status_code == 200
            
            data = response.json()
            assert "issuer" in data
            assert "authorization_endpoint" in data
            assert "token_endpoint" in data

    @pytest.mark.asyncio
    async def test_mcp_root_endpoint_authentication_required(self):
        """Test that MCP requests to root endpoint require authentication"""
        async with httpx.AsyncClient() as client:
            # Send a basic MCP initialize request to root endpoint without auth
            mcp_request = {
                "jsonrpc": "2.0",
                "id": "test-initialize",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "clientInfo": {
                        "name": "test-client",
                        "version": "0.3.0"
                    },
                    "capabilities": {}
                }
            }
            
            response = await client.post(
                f"{GATEWAY_URL}/",
                json=mcp_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream"
                }
            )
            
            # Should require authentication
            assert response.status_code == 401
            
            # Should be JSON error response
            error_data = response.json()
            assert error_data["error"]["code"] == -32001
            assert "OAuth token required" in error_data["error"]["message"]
            assert error_data["error"]["data"]["auth_required"] is True


class TestGatewayBackendConnectivity:
    """Test gateway's connectivity to backend servers"""

    @pytest.mark.asyncio
    async def test_gateway_discovers_backend_servers(self):
        """Test gateway can discover and connect to backend servers"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert "servers" in data
            assert "tools" in data
            
            # Should have discovered backend servers (count format)
            assert data["servers"] > 0
            assert data["tools"] > 0

    @pytest.mark.asyncio
    async def test_gateway_aggregates_server_info(self):
        """Test gateway aggregates info from all backend servers"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/info")
            assert response.status_code == 200
            
            data = response.json()
            assert data["name"] == "MCP Adapter"
            assert "connected_servers" in data
            assert "available_tools" in data
            
            # Should have tools from multiple servers
            tools = data["available_tools"]
            assert any(tool.startswith("hello_") for tool in tools)
            assert any(tool.startswith("latex_") for tool in tools)


class TestGatewayHTTPToolProxy:
    """Test gateway tool proxying functionality via HTTP"""

    @pytest.mark.asyncio
    async def test_gateway_tool_discovery(self):
        """Test gateway discovers and lists tools from backend servers"""
        async with MCPSession(GATEWAY_URL) as session:
            tools_result = await session.list_tools()
            
            assert "result" in tools_result
            assert "tools" in tools_result["result"]
            tools = tools_result["result"]["tools"]
            
            # Should have prefixed tools from hello-world server
            tool_names = [tool["name"] for tool in tools]
            expected_hello_tools = ["hello_greet", "hello_add_numbers", "hello_get_timestamp"]
            assert all(tool in tool_names for tool in expected_hello_tools)
            
            # Should have some tools from multiple servers
            # Note: Exact latex tools may vary based on server availability
            assert len(tool_names) >= 3  # At minimum hello server tools
            print(f"Available tools: {tool_names}")  # Debug output

    @pytest.mark.asyncio
    async def test_gateway_tool_proxy_routing(self):
        """Test gateway properly routes tool calls to correct backend server"""
        async with MCPSession(GATEWAY_URL) as session:
            # Test routing to hello-world server
            tool_result = await session.call_tool(
                "hello_greet", 
                {"name": "Gateway", "greeting": "Hi"}, 
                "gateway-proxy-test"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "Hi, Gateway!" in content
            assert tool_result["id"] == "gateway-proxy-test"

    @pytest.mark.asyncio
    async def test_gateway_handles_backend_errors(self):
        """Test gateway handles backend server errors gracefully"""
        async with MCPSession(GATEWAY_URL) as session:
            # Try to call a non-existent tool
            response = await session.raw_request(
                "tools/call",
                {"name": "nonexistent_tool", "arguments": {}},
                "error-test"
            )
            
            assert response.status_code == 200
            data = session._parse_sse_response(response.text)
            
            # Should get either an error response or a tool result with error
            assert "error" in data or ("result" in data and data["result"].get("isError"))
            assert data["id"] == "error-test"


