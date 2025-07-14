"""
Basic connectivity tests - these should always pass when services are running
"""

import pytest
import httpx
from typing import Dict, Any

# Test configuration
GATEWAY_URL = "http://localhost:8080"
HELLO_WORLD_URL = "http://localhost:8001"
LATEX_SERVER_URL = "http://localhost:8002"


class TestBasicConnectivity:
    """Test basic HTTP connectivity without MCP protocol"""

    @pytest.mark.asyncio
    async def test_gateway_health(self):
        """Test gateway health endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_gateway_info(self):
        """Test gateway info endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/info")
            assert response.status_code == 200
            
            data = response.json()
            assert data["name"] == "MCP Adapter"
            assert "available_tools" in data

    @pytest.mark.asyncio
    async def test_gateway_dashboard(self):
        """Test gateway dashboard is accessible"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/dashboard")
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_hello_world_health(self):
        """Test hello-world health endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HELLO_WORLD_URL}/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "Hello World MCP Server"

    @pytest.mark.asyncio
    async def test_hello_world_info(self):
        """Test hello-world info endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HELLO_WORLD_URL}/info")
            assert response.status_code == 200
            
            data = response.json()
            assert data["service"] == "Hello World MCP Server"
            assert "available_tools" in data
            expected_tools = ["greet", "add_numbers", "get_timestamp"]
            assert all(tool in data["available_tools"] for tool in expected_tools)

    @pytest.mark.asyncio
    async def test_oauth_discovery(self):
        """Test OAuth discovery endpoint for Claude Code compatibility"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GATEWAY_URL}/.well-known/oauth-authorization-server")
            assert response.status_code == 200
            
            data = response.json()
            assert "issuer" in data
            assert "authorization_endpoint" in data
            assert "token_endpoint" in data

    @pytest.mark.asyncio
    async def test_services_are_accessible(self):
        """Test that both services respond to basic requests"""
        async with httpx.AsyncClient() as client:
            # Test gateway responds
            gateway_response = await client.get(f"{GATEWAY_URL}/health", timeout=5.0)
            assert gateway_response.status_code == 200
            
            # Test hello-world responds
            hello_response = await client.get(f"{HELLO_WORLD_URL}/health", timeout=5.0)
            assert hello_response.status_code == 200
            
            # Test latex-server responds
            latex_response = await client.get(f"{LATEX_SERVER_URL}/health", timeout=5.0)
            assert latex_response.status_code == 200
            
            # Verify they're different services
            gateway_data = gateway_response.json()
            hello_data = hello_response.json()
            latex_data = latex_response.json()
            assert gateway_data != hello_data
            assert latex_data["service"] == "LaTeX MCP Server"

    @pytest.mark.asyncio
    async def test_latex_server_health(self):
        """Test LaTeX server health endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{LATEX_SERVER_URL}/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "LaTeX MCP Server"
            assert "compiler" in data

    @pytest.mark.asyncio
    async def test_latex_server_info(self):
        """Test LaTeX server info endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{LATEX_SERVER_URL}/info")
            assert response.status_code == 200
            
            data = response.json()
            assert data["service"] == "LaTeX MCP Server"
            assert "available_tools" in data
            expected_tools = ["upload_latex_file", "compile_latex_by_id", "compile_from_template", "list_templates"]
            assert all(tool in data["available_tools"] for tool in expected_tools)


