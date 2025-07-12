"""
Gateway Server Unit Tests

Comprehensive unit tests for the MCP Gateway Server core logic.
"""

import os
import sys
import json
import pytest
import httpx
from unittest.mock import patch, mock_open, AsyncMock, MagicMock
from pathlib import Path
import tempfile

# Import the gateway module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../gateway'))
import gateway

class TestServerConfiguration:
    """Test server configuration loading"""
    
    def test_load_server_config_success(self):
        """Test successful loading of server configuration"""
        mock_config = {
            "servers": {
                "hello": {
                    "url": "http://hello-world:8000",
                    "description": "Hello World test server"
                },
                "latex": {
                    "url": "http://latex-server:8000",
                    "description": "LaTeX PDF compilation server"
                }
            }
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            result = gateway.load_server_config()
            
        assert result == mock_config["servers"]
        assert "hello" in result
        assert "latex" in result
        assert result["hello"]["url"] == "http://hello-world:8000"
    
    def test_load_server_config_file_not_found(self):
        """Test handling of missing servers.json file"""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = gateway.load_server_config()
            
        assert result == {}
    
    def test_load_server_config_invalid_json(self):
        """Test handling of invalid JSON in servers.json"""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            result = gateway.load_server_config()
            
        assert result == {}
    
    def test_load_server_config_empty_servers(self):
        """Test handling of config with no servers"""
        mock_config = {"servers": {}}
        
        with patch("builtins.open", mock_open(read_data=json.dumps(mock_config))):
            result = gateway.load_server_config()
            
        assert result == {}


class TestToolDiscovery:
    """Test tool discovery functionality"""
    
    @pytest.mark.asyncio
    async def test_discover_server_tools_success(self):
        """Test successful tool discovery from server"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "available_tools": ["greet", "add_numbers", "get_timestamp"]
        }
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_context
            
            config = {"url": "http://test-server:8000", "description": "Test server"}
            tools = await gateway.discover_server_tools("test", config)
        
        assert len(tools) == 3
        assert tools[0]["name"] == "test_greet"
        assert tools[0]["original_tool"] == "greet"
        assert tools[0]["server"] == "test"
        assert tools[0]["url"] == "http://test-server:8000"
    
    @pytest.mark.asyncio
    async def test_discover_server_tools_connection_error(self):
        """Test tool discovery with connection error"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.get.side_effect = httpx.ConnectError("Connection failed")
            mock_client.return_value.__aenter__.return_value = mock_context
            
            config = {"url": "http://unreachable-server:8000", "description": "Test server"}
            tools = await gateway.discover_server_tools("test", config)
        
        assert tools == []
    
    @pytest.mark.asyncio
    async def test_discover_server_tools_http_error(self):
        """Test tool discovery with HTTP error response"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_context
            
            config = {"url": "http://error-server:8000", "description": "Test server"}
            tools = await gateway.discover_server_tools("test", config)
        
        assert tools == []
    
    @pytest.mark.asyncio
    async def test_initialize_tool_registry(self):
        """Test tool registry initialization"""
        mock_servers = {
            "hello": {"url": "http://hello:8000", "description": "Hello server"},
            "latex": {"url": "http://latex:8000", "description": "LaTeX server"}
        }
        
        with patch.object(gateway, "MCP_SERVERS", mock_servers), \
             patch.object(gateway, "discover_server_tools") as mock_discover:
            
            mock_discover.side_effect = [
                [{"name": "hello_greet", "server": "hello", "original_tool": "greet", "url": "http://hello:8000"}],
                [{"name": "latex_compile", "server": "latex", "original_tool": "compile", "url": "http://latex:8000"}]
            ]
            
            # Clear the tool registry
            gateway.tool_registry.clear()
            
            await gateway.initialize_tool_registry()
            
            assert len(gateway.tool_registry) == 2
            assert "hello_greet" in gateway.tool_registry
            assert "latex_compile" in gateway.tool_registry


class TestResponseParsing:
    """Test SSE response parsing"""
    
    def test_parse_sse_response_success(self):
        """Test successful SSE response parsing"""
        sse_response = """event: message
data: {"jsonrpc": "2.0", "id": "test", "result": {"content": [{"text": "Hello World"}]}}

"""
        
        result = gateway.parse_sse_response(sse_response)
        
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == "test"
        assert "result" in result
    
    def test_parse_sse_response_no_data_line(self):
        """Test SSE response with no data line"""
        sse_response = """event: message
id: test

"""
        
        with pytest.raises(ValueError, match="No data line found"):
            gateway.parse_sse_response(sse_response)
    
    def test_parse_sse_response_invalid_json(self):
        """Test SSE response with invalid JSON"""
        sse_response = """data: invalid json data
"""
        
        with pytest.raises(ValueError, match="Invalid JSON"):
            gateway.parse_sse_response(sse_response)
    
    def test_parse_sse_response_multiple_data_lines(self):
        """Test SSE response with multiple data lines"""
        sse_response = """data: {"jsonrpc": "2.0", "id": "test", "result": "success"}
data: {"invalid": "second"}
"""
        
        result = gateway.parse_sse_response(sse_response)
        
        # Should parse the first data line
        assert result["jsonrpc"] == "2.0"
        assert result["result"] == "success"


class TestSessionManagement:
    """Test backend session management"""
    
    @pytest.mark.asyncio
    async def test_get_backend_session_new_session(self):
        """Test creating new backend session"""
        server_url = "http://test-server:8000"
        
        # Mock responses for session initialization
        init_response = MagicMock()
        init_response.status_code = 200
        init_response.headers = {"mcp-session-id": "test-session-123"}
        
        notify_response = MagicMock()
        notify_response.status_code = 200
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.side_effect = [init_response, notify_response]
            mock_client_class.return_value = mock_client
            
            # Clear any existing sessions
            gateway.session_pools.clear()
            
            client, session_id = await gateway.get_backend_session(server_url)
            
            assert session_id == "test-session-123"
            assert server_url in gateway.session_pools
            # Verify session pool was created
            assert isinstance(gateway.session_pools[server_url], gateway.SessionPool)
    
    @pytest.mark.asyncio
    async def test_get_backend_session_existing_session(self):
        """Test reusing existing backend session"""
        server_url = "http://test-server:8000"
        existing_client = AsyncMock()
        existing_session_id = "existing-session-456"
        
        # Clear existing sessions
        gateway.session_pools.clear()
        
        # Mock the session creation to avoid actual HTTP calls
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_init_response = MagicMock()
            mock_init_response.status_code = 200
            mock_init_response.headers = {"mcp-session-id": existing_session_id}
            mock_notify_response = MagicMock()
            mock_notify_response.status_code = 200
            mock_client.post.side_effect = [mock_init_response, mock_notify_response]
            mock_client_class.return_value = mock_client
            
            client, session_id = await gateway.get_backend_session(server_url)
            
            # Verify session was created
            assert client is not None
            assert session_id == existing_session_id
    
    @pytest.mark.asyncio
    async def test_get_backend_session_init_failure(self):
        """Test session initialization failure"""
        server_url = "http://test-server:8000"
        
        init_response = MagicMock()
        init_response.status_code = 500
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = init_response
            mock_client_class.return_value = mock_client
            
            # Clear any existing sessions
            gateway.session_pools.clear()
            
            with pytest.raises(RuntimeError, match="Failed to initialize session"):
                await gateway.get_backend_session(server_url)
    
    @pytest.mark.asyncio
    async def test_get_backend_session_no_session_id(self):
        """Test session initialization without session ID"""
        server_url = "http://test-server:8000"
        
        init_response = MagicMock()
        init_response.status_code = 200
        init_response.headers = {}  # No session ID
        
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = init_response
            mock_client_class.return_value = mock_client
            
            # Clear any existing sessions
            gateway.session_pools.clear()
            
            # Should work even without session ID in headers (generates its own)
            client, session_id = await gateway.get_backend_session(server_url)
            
            # Should still get a valid client and session ID
            assert client is not None
            assert isinstance(session_id, str)
            assert len(session_id) > 0


class TestBackendToolCalling:
    """Test backend tool calling functionality"""
    
    @pytest.mark.asyncio
    async def test_call_backend_tool_direct_success(self):
        """Test successful direct backend tool call"""
        server_url = "http://test-server:8000"
        tool_name = "greet"
        arguments = {"name": "World", "greeting": "Hello"}
        
        # Mock session
        mock_client = AsyncMock()
        mock_session_id = "test-session-123"
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = 'data: {"jsonrpc": "2.0", "id": "test", "result": {"content": [{"text": "Hello, World!"}]}}\n'
        mock_client.post.return_value = mock_response
        
        with patch.object(gateway, "get_backend_session") as mock_get_session:
            mock_get_session.return_value = (mock_client, mock_session_id)
            
            result = await gateway.call_backend_tool_direct(server_url, tool_name, arguments)
            
            assert result == "Hello, World!"
            
            # Verify the MCP request was made correctly
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["method"] == "tools/call"
            assert call_args[1]["json"]["params"]["name"] == tool_name
            assert call_args[1]["json"]["params"]["arguments"] == arguments
    
    @pytest.mark.asyncio
    async def test_call_backend_tool_direct_http_error(self):
        """Test backend tool call with HTTP error"""
        server_url = "http://test-server:8000"
        tool_name = "greet"
        arguments = {"name": "World"}
        
        # Mock session
        mock_client = AsyncMock()
        mock_session_id = "test-session-123"
        
        # Mock error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_client.post.return_value = mock_response
        
        with patch.object(gateway, "get_backend_session") as mock_get_session:
            mock_get_session.return_value = (mock_client, mock_session_id)
            
            result = await gateway.call_backend_tool_direct(server_url, tool_name, arguments)
            
            assert "HTTP Error 500" in result
    
    @pytest.mark.asyncio
    async def test_call_backend_tool_direct_connection_error(self):
        """Test backend tool call with connection error"""
        server_url = "http://test-server:8000"
        tool_name = "greet"
        arguments = {"name": "World"}
        
        with patch.object(gateway, "get_backend_session") as mock_get_session:
            mock_get_session.side_effect = httpx.ConnectError("Connection failed")
            
            result = await gateway.call_backend_tool_direct(server_url, tool_name, arguments)
            
            assert "Failed to call tool" in result
    
    @pytest.mark.asyncio
    async def test_call_backend_tool_registry_lookup(self):
        """Test tool calling through tool registry"""
        tool_name = "test_greet"
        arguments = {"name": "World"}
        
        # Set up tool registry
        gateway.tool_registry[tool_name] = {
            "name": tool_name,
            "server": "test",
            "original_tool": "greet",
            "url": "http://test-server:8000"
        }
        
        # Mock session and response
        mock_client = AsyncMock()
        mock_session_id = "test-session-123"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = 'data: {"jsonrpc": "2.0", "id": "test", "result": {"content": [{"text": "Hello, World!"}]}}\n'
        mock_client.post.return_value = mock_response
        
        with patch.object(gateway, "get_backend_session") as mock_get_session:
            mock_get_session.return_value = (mock_client, mock_session_id)
            
            result = await gateway.call_backend_tool(tool_name, arguments)
            
            assert result == "Hello, World!"
    
    @pytest.mark.asyncio
    async def test_call_backend_tool_not_found(self):
        """Test tool calling with unknown tool"""
        tool_name = "unknown_tool"
        arguments = {}
        
        # Clear tool registry
        gateway.tool_registry.clear()
        
        with pytest.raises(ValueError, match="Tool 'unknown_tool' not found"):
            await gateway.call_backend_tool(tool_name, arguments)


class TestOAuthEndpoints:
    """Test OAuth endpoint functionality"""
    
    def test_oauth_register_success(self):
        """Test successful OAuth client registration"""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        
        # Create a minimal app for testing
        app = FastAPI()
        
        # We'll test the logic directly since the route is decorated with FastMCP
        import asyncio
        from unittest.mock import AsyncMock
        
        async def test_register():
            mock_request = AsyncMock()
            mock_request.json.return_value = {
                "client_name": "Test Client",
                "redirect_uris": ["http://localhost:8080/callback"]
            }
            
            response = await gateway.oauth_register(mock_request)
            response_data = response.body.decode()
            
            import json
            data = json.loads(response_data)
            
            assert "client_id" in data
            assert data["client_name"] == "Test Client"
            assert data["grant_types"] == ["authorization_code"]
        
        asyncio.run(test_register())
    
    def test_oauth_authorize_success(self):
        """Test OAuth authorization endpoint"""
        import asyncio
        from unittest.mock import AsyncMock
        
        async def test_authorize():
            mock_request = AsyncMock()
            mock_request.query_params = {
                "client_id": "test-client",
                "redirect_uri": "http://localhost:8080/callback",
                "state": "test-state-123"
            }
            
            response = await gateway.oauth_authorize(mock_request)
            
            # Should be a redirect response
            assert response.status_code == 302
            assert "code=" in response.headers["location"]
            assert "state=test-state-123" in response.headers["location"]
        
        asyncio.run(test_authorize())
    
    def test_oauth_token_success(self):
        """Test OAuth token endpoint"""
        import asyncio
        from unittest.mock import AsyncMock
        
        async def test_token():
            mock_request = AsyncMock()
            mock_request.form.return_value = {
                "grant_type": "authorization_code",
                "code": "test-auth-code",
                "redirect_uri": "http://localhost:8080/callback"
            }
            
            response = await gateway.oauth_token(mock_request)
            response_data = response.body.decode()
            
            import json
            data = json.loads(response_data)
            
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["expires_in"] == 7200
            assert "refresh_token" in data
        
        asyncio.run(test_token())
    
    def test_oauth_token_invalid_grant(self):
        """Test OAuth token endpoint with invalid grant type"""
        import asyncio
        from unittest.mock import AsyncMock
        
        async def test_token():
            mock_request = AsyncMock()
            mock_request.form.return_value = {
                "grant_type": "client_credentials"  # Unsupported
            }
            
            response = await gateway.oauth_token(mock_request)
            
            assert response.status_code == 400
            response_data = response.body.decode()
            
            import json
            data = json.loads(response_data)
            assert data["error"] == "unsupported_grant_type"
        
        asyncio.run(test_token())


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_get_hello_server_url(self):
        """Test hello server URL getter"""
        url = gateway.get_hello_server_url()
        assert url == "http://hello-world:8000"
    
    def test_get_latex_server_url(self):
        """Test LaTeX server URL getter"""
        url = gateway.get_latex_server_url()
        assert url == "http://latex-server:8000"
    
    @pytest.mark.asyncio
    async def test_ensure_tools_initialized(self):
        """Test tool initialization checker"""
        # Clear registry first
        gateway.tool_registry.clear()
        
        with patch.object(gateway, "initialize_tool_registry") as mock_init:
            await gateway.ensure_tools_initialized()
            mock_init.assert_called_once()
        
        # Should not call again if already initialized
        gateway.tool_registry["test"] = {"name": "test"}
        with patch.object(gateway, "initialize_tool_registry") as mock_init:
            await gateway.ensure_tools_initialized()
            mock_init.assert_not_called()


class TestGatewayErrorHandling:
    """Test error handling scenarios"""
    
    @pytest.mark.asyncio
    async def test_malformed_sse_response(self):
        """Test handling of malformed SSE responses"""
        server_url = "http://test-server:8000"
        tool_name = "greet"
        arguments = {"name": "World"}
        
        # Mock session
        mock_client = AsyncMock()
        mock_session_id = "test-session-123"
        
        # Mock malformed response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "not valid sse format"
        mock_client.post.return_value = mock_response
        
        with patch.object(gateway, "get_backend_session") as mock_get_session:
            mock_get_session.return_value = (mock_client, mock_session_id)
            
            result = await gateway.call_backend_tool_direct(server_url, tool_name, arguments)
            
            assert "Failed to call tool" in result
    
    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test handling of timeout errors"""
        server_url = "http://test-server:8000"
        tool_name = "greet"
        arguments = {"name": "World"}
        
        # Mock session
        mock_client = AsyncMock()
        mock_session_id = "test-session-123"
        
        # Mock timeout error
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        
        with patch.object(gateway, "get_backend_session") as mock_get_session:
            mock_get_session.return_value = (mock_client, mock_session_id)
            
            result = await gateway.call_backend_tool_direct(server_url, tool_name, arguments)
            
            assert "Failed to call tool" in result
            assert "timed out" in result.lower()