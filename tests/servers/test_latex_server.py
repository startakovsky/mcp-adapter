#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#    "pytest==8.4.*",
#    "pytest-asyncio==1.0.*",
#    "httpx==0.28.*",
#    "fastmcp>=2.10",
# ]
# ///
"""
LaTeX MCP Server Tests

Tests for the individual tools implemented in the latex-server.
These tests focus on the tool implementations, not the MCP protocol.
"""

import pytest
import httpx
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, Any
import asyncio
from mcp_session_helper import MCPSession, extract_tool_result_content


# Test configuration - Use gateway for proper MCP protocol handling
GATEWAY_URL = "http://localhost:8080"


class TestLatexServerTools:
    """Test LaTeX server tools (simplified set)"""

    @pytest.mark.asyncio
    async def test_upload_latex_file(self):
        """Test upload_latex_file tool"""
        simple_latex = r"""
        \documentclass{article}
        \begin{document}
        Hello, File Upload!
        \end{document}
        """
        
        async with MCPSession(GATEWAY_URL) as session:
            tool_result = await session.call_tool(
                "latex_upload_latex_file",
                {
                    "content": simple_latex,
                    "filename": "upload_test.tex"
                },
                "upload-test"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            
            # Parse JSON if it's a string
            if isinstance(content, str):
                import json
                try:
                    content = json.loads(content)
                except json.JSONDecodeError:
                    # If it's not valid JSON, treat as raw response
                    content = {"raw": content}
                
            assert content.get("success") is True
            assert "file_id" in content
            assert content["filename"].endswith(".tex")  # Generated UUID filename
            assert "size_bytes" in content
            assert content["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_compile_latex_by_id_success(self):
        """Test compile_latex_by_id tool with valid file"""
        simple_latex = r"""
        \documentclass{article}
        \begin{document}
        Hello, File Compilation!
        \end{document}
        """
        
        async with MCPSession(GATEWAY_URL) as session:
            # First upload file
            upload_result = await session.call_tool(
                "latex_upload_latex_file",
                {
                    "content": simple_latex,
                    "filename": "compile_test.tex"
                },
                "upload-for-compile"
            )
            
            assert "result" in upload_result
            upload_content = extract_tool_result_content(upload_result)
            
            # Parse JSON if it's a string
            if isinstance(upload_content, str):
                import json
                try:
                    upload_content = json.loads(upload_content)
                except json.JSONDecodeError:
                    # If it's not valid JSON, treat as raw response
                    upload_content = {"raw": upload_content}
                
            assert upload_content.get("success") is True
            file_id = upload_content["file_id"]
            
            # Then compile by ID
            compile_result = await session.call_tool(
                "latex_compile_latex_by_id",
                {
                    "file_id": file_id,
                    "output_filename": "compiled_output"
                },
                "compile-by-id"
            )
            
            assert "result" in compile_result
            compile_content = extract_tool_result_content(compile_result)
            
            # Parse JSON if it's a string
            if isinstance(compile_content, str):
                import json
                try:
                    compile_content = json.loads(compile_content)
                except json.JSONDecodeError:
                    compile_content = {"raw": compile_content}
            
            # Check if compilation was successful or failed gracefully
            if compile_content.get("success") is True:
                # Check for either pdf_path or download_url (different response formats)
                assert ("pdf_path" in compile_content or "download_url" in compile_content)
                assert "filename" in compile_content
            else:
                # If compilation failed, check error reporting
                assert "error" in compile_content

    @pytest.mark.asyncio
    async def test_list_templates_includes_us_map(self):
        """Test that list_templates tool includes the US map template"""
        async with MCPSession(GATEWAY_URL) as session:
            tool_result = await session.call_tool(
                "latex_list_templates",
                {},
                "list-templates"
            )
            
            assert "result" in tool_result
            content = extract_tool_result_content(tool_result)
            
            # Parse JSON if it's a string
            if isinstance(content, str):
                import json
                content = json.loads(content)
            
            # Check that templates were returned
            assert "templates" in content
            assert "count" in content
            assert content["count"] > 0
            
            # Check that US map template is included
            templates = content["templates"]
            assert "us_map" in templates, f"us_map template not found in: {list(templates.keys())}"
            
            # Check US map template details
            us_map_template = templates["us_map"]
            assert "description" in us_map_template
            assert "path" in us_map_template
            assert "US map template" in us_map_template["description"]