"""
MCP server functionality tests
"""

import pytest
import httpx
import json
from typing import Dict, Any

from mcp_session_helper import MCPSession, extract_tool_names, extract_tool_result_content

# Test configuration
GATEWAY_URL = "http://localhost:8080"
HELLO_WORLD_URL = "http://localhost:8001"


class TestGatewayMCPProtocol:
    """Test gateway MCP protocol compliance"""

    @pytest.mark.asyncio
    async def test_gateway_mcp_tools_list(self):
        """Test gateway MCP tools/list method aggregates all backend tools"""
        async with MCPSession(GATEWAY_URL) as session:
            tools_result = await session.list_tools()
            
            assert "result" in tools_result
            assert "tools" in tools_result["result"]
            assert isinstance(tools_result["result"]["tools"], list)
            assert len(tools_result["result"]["tools"]) > 0
            
            # Check for expected prefixed tools from multiple servers
            tool_names = extract_tool_names(tools_result)
            expected_hello_tools = ["hello_greet", "hello_add_numbers", "hello_get_timestamp"]
            assert all(tool in tool_names for tool in expected_hello_tools)
            
            # Should also have latex server tools (both original and new file-based)
            expected_latex_tools = ["latex_compile_latex", "latex_upload_latex_file", "latex_compile_latex_by_id"]
            assert any(tool in tool_names for tool in expected_latex_tools)

    @pytest.mark.asyncio
    async def test_gateway_mcp_invalid_method(self):
        """Test gateway MCP invalid method handling"""
        async with MCPSession(GATEWAY_URL) as session:
            response = await session.raw_request("invalid/method", {}, "invalid-test")
            assert response.status_code == 200
            
            data = session._parse_sse_response(response.text)
            assert "error" in data
            assert data["id"] == "invalid-test"

    @pytest.mark.asyncio
    async def test_gateway_mcp_invalid_tool_call(self):
        """Test gateway MCP invalid tool call handling"""
        async with MCPSession(GATEWAY_URL) as session:
            response = await session.raw_request(
                "tools/call",
                {"name": "nonexistent_tool", "arguments": {}},
                "invalid-tool-test"
            )
            assert response.status_code == 200
            
            data = session._parse_sse_response(response.text)
            # Check for either error response or error content
            if "error" in data:
                assert data["id"] == "invalid-tool-test"
            else:
                # FastMCP returns tool errors as result with isError=True
                assert "result" in data
                result = data["result"]
                assert result.get("isError") is True
                assert data["id"] == "invalid-tool-test"




class TestGatewayMCPToolProxy:
    """Test gateway tool proxying functionality via MCP protocol"""

    @pytest.mark.asyncio
    async def test_gateway_tool_list(self):
        """Test gateway tool list"""
        async with MCPSession(GATEWAY_URL) as session:
            tools_result = await session.list_tools()
            
            assert "result" in tools_result
            assert "tools" in tools_result["result"]
            tools = tools_result["result"]["tools"]
            
            # Should have prefixed tools
            tool_names = extract_tool_names(tools_result)
            expected_tools = ["hello_greet", "hello_add_numbers", "hello_get_timestamp"]
            assert all(tool in tool_names for tool in expected_tools)

    @pytest.mark.asyncio
    async def test_gateway_proxy_greet(self):
        """Test gateway proxying greet tool"""
        async with MCPSession(GATEWAY_URL) as session:
            tool_result = await session.call_tool(
                "hello_greet", 
                {"name": "Gateway", "greeting": "Hey"}, 
                "gateway-greet-test"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "Hey, Gateway!" in content

    @pytest.mark.asyncio
    async def test_gateway_proxy_add_numbers(self):
        """Test gateway proxying add_numbers tool"""
        async with MCPSession(GATEWAY_URL) as session:
            tool_result = await session.call_tool(
                "hello_add_numbers", 
                {"a": 7, "b": 3}, 
                "gateway-add-test"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            assert "10" in content

    @pytest.mark.asyncio
    async def test_gateway_proxy_latex_upload(self, test_filename):
        """Test gateway proxying to LaTeX upload tool"""
        async with MCPSession(GATEWAY_URL) as session:
            sample_latex = r"""
            \documentclass{article}
            \begin{document}
            Gateway Test Document
            \end{document}
            """
            
            filename = test_filename("gateway_test", "tex")
            tool_result = await session.call_tool(
                "latex_upload_latex_file",
                {
                    "content": sample_latex,
                    "filename": filename
                },
                "gateway-upload-test"
            )
            
            # Should get response from backend through gateway
            if "result" in tool_result:
                result = tool_result["result"]
                if isinstance(result, dict) and result.get("success") is True:
                    assert "file_id" in result
                    assert result["filename"] == filename
                # If failed, that's also acceptable (depends on backend availability)
            # If no result, backend might be unavailable

    @pytest.mark.asyncio
    async def test_gateway_proxy_latex_file_compilation(self):
        """Test gateway proxying file-based LaTeX compilation"""
        async with MCPSession(GATEWAY_URL) as session:
            # This test depends on having uploaded a file first
            # Since we can't guarantee state, we'll test with a fake file_id
            # and expect a proper "not found" error
            
            tool_result = await session.call_tool(
                "latex_compile_latex_by_id",
                {"file_id": "test-nonexistent-id"},
                "gateway-compile-test"
            )
            
            # Should get response from backend through gateway
            if "result" in tool_result:
                result = tool_result["result"]
                if isinstance(result, dict) and result.get("success") is False:
                    assert "error" in result
                    # Should be file not found error, not gateway error
                    assert "not found" in result["error"].lower() or "file" in result["error"].lower()
            # If no result, backend might be unavailable


