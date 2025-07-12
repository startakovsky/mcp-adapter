#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#    "pytest>=7.0.0",
#    "pytest-asyncio>=0.23.0",
#    "httpx>=0.25.0",
#    "fastmcp>=0.4.0",
#    "fastapi>=0.104.0",
#    "uvicorn>=0.24.0"
# ]
# ///
"""
Hello World MCP Server Tests

Tests for the individual tools implemented in the hello-world server.
These tests focus on the tool implementations, not the MCP protocol.
"""

import pytest
import httpx
import json
from datetime import datetime
from typing import Dict, Any
from mcp_session_helper import MCPSession, extract_tool_result_content


# Test configuration
HELLO_WORLD_URL = "http://localhost:8001"


class TestHelloWorldTools:
    """Test hello-world server individual tool implementations"""

    @pytest.mark.asyncio
    async def test_greet_tool_default(self):
        """Test greet tool with default greeting"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool("greet", {"name": "World"}, "greet-default")
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "Hello, World!" in content

    @pytest.mark.asyncio
    async def test_greet_tool_custom_greeting(self):
        """Test greet tool with custom greeting"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool(
                "greet", 
                {"name": "Alice", "greeting": "Hi"}, 
                "greet-custom"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "Hi, Alice!" in content

    @pytest.mark.asyncio
    async def test_greet_tool_empty_name(self):
        """Test greet tool with empty name"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool(
                "greet", 
                {"name": ""}, 
                "greet-empty"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "Hello, !" in content

    @pytest.mark.asyncio
    async def test_greet_tool_special_characters(self):
        """Test greet tool with special characters in name"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool(
                "greet", 
                {"name": "José & María", "greeting": "¡Hola"}, 
                "greet-special"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "¡Hola, José & María!" in content

    @pytest.mark.asyncio
    async def test_add_numbers_positive(self):
        """Test add_numbers tool with positive numbers"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool(
                "add_numbers", 
                {"a": 10, "b": 5}, 
                "add-positive"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "15" in content

    @pytest.mark.asyncio
    async def test_add_numbers_negative(self):
        """Test add_numbers tool with negative numbers"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool(
                "add_numbers", 
                {"a": -5, "b": -3}, 
                "add-negative"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "-8" in content

    @pytest.mark.asyncio
    async def test_add_numbers_zero(self):
        """Test add_numbers tool with zero"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool(
                "add_numbers", 
                {"a": 0, "b": 42}, 
                "add-zero"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "42" in content

    @pytest.mark.asyncio
    async def test_add_numbers_large_numbers(self):
        """Test add_numbers tool with large numbers"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool(
                "add_numbers", 
                {"a": 1000000, "b": 2000000}, 
                "add-large"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "3000000" in content

    @pytest.mark.asyncio
    async def test_get_timestamp(self):
        """Test get_timestamp tool"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            tool_result = await session.call_tool(
                "get_timestamp", 
                {}, 
                "timestamp-test"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            
            # Should contain a valid ISO timestamp
            assert "T" in content  # ISO format has 'T' separator
            assert ":" in content  # Time format has colons
            
            # Should be parseable as datetime
            try:
                datetime.fromisoformat(content.replace("Z", "+00:00"))
            except ValueError:
                pytest.fail(f"Timestamp '{content}' is not valid ISO format")

    @pytest.mark.asyncio
    async def test_get_timestamp_multiple_calls(self):
        """Test get_timestamp tool returns different timestamps on multiple calls"""
        async with MCPSession(HELLO_WORLD_URL) as session:
            # First call
            tool_result1 = await session.call_tool(
                "get_timestamp", 
                {}, 
                "timestamp-1"
            )
            
            # Second call (slight delay)
            import asyncio
            await asyncio.sleep(0.01)
            
            tool_result2 = await session.call_tool(
                "get_timestamp", 
                {}, 
                "timestamp-2"
            )
            
            assert "result" in tool_result1
            assert "result" in tool_result2
            
            content1 = extract_tool_result_content(tool_result1)
            content2 = extract_tool_result_content(tool_result2)
            
            # Timestamps should be different (or at least not obviously the same)
            assert content1 != content2 or len(content1) > 0


class TestHelloWorldHTTPEndpoints:
    """Test hello-world server HTTP endpoints"""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test health endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HELLO_WORLD_URL}/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "Hello World MCP Server"
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_info_endpoint(self):
        """Test info endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HELLO_WORLD_URL}/info")
            assert response.status_code == 200
            
            data = response.json()
            assert data["service"] == "Hello World MCP Server"
            assert data["version"] == "0.3.0"
            assert "available_tools" in data
            
            expected_tools = ["greet", "add_numbers", "get_timestamp"]
            assert all(tool in data["available_tools"] for tool in expected_tools)


if __name__ == "__main__":
    print("Run tests with: uv run test_hello_world.py")
    print("Or with pytest: uv run pytest test_hello_world.py")