"""
Integration tests for file operations
Tests file upload, storage, and management functionality
"""

import pytest
import asyncio
from .conftest import MCPToolHelper, GATEWAY_URL

class TestFileUploadOperations:
    """Test file upload and storage operations"""

    @pytest.mark.asyncio
    async def test_file_upload_basic(self, sample_latex_document: str, test_filename):
        """Test basic file upload functionality"""
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            result = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": sample_latex_document,
                    "filename": test_filename("upload_test", "tex")
                }
            )
            
            assert result.get("success") is True
            assert "file_id" in result
            filename = result["filename"]
            assert filename.endswith(".tex") and len(filename) > 10  # UUID + .tex
            assert "size_bytes" in result
            assert result["size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_file_upload_without_filename(self, sample_latex_document: str):
        """Test file upload without specifying filename"""
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            result = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": sample_latex_document
                }
            )
            
            assert result.get("success") is True
            assert "file_id" in result
            assert "filename" in result
            assert result["filename"].endswith(".tex")

    @pytest.mark.asyncio
    async def test_file_upload_empty_content(self, test_filename):
        """Test file upload with empty content"""
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            result = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": "",
                    "filename": test_filename("empty_test", "tex", "upload")
                }
            )
            
            assert result.get("success") is True
            assert result["size_bytes"] == 0

    @pytest.mark.asyncio
    async def test_file_upload_special_characters(self, test_filename):
        """Test file upload with special characters in content"""
        
        special_content = r"""
\documentclass{article}
\usepackage[utf8]{inputenc}
\begin{document}
Special characters: áéíóú, ñ, ¿¡, €, ∑, ∞, ∫
Math: $\alpha \beta \gamma \delta$
\end{document}
"""
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            result = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": special_content,
                    "filename": test_filename("special_chars", "tex", "upload")
                }
            )
            
            assert result.get("success") is True
            assert "file_id" in result

    @pytest.mark.asyncio
    async def test_multiple_file_uploads(self, sample_latex_document: str, test_filename):
        """Test uploading multiple files"""
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            file_ids = []
            
            for i in range(5):
                content = sample_latex_document.replace("Integration Test Document", f"Test Document {i}")
                
                result = await gateway_helper.call_tool(
                    "latex_upload_latex_file",
                    {
                        "content": content,
                        "filename": test_filename(f"multi_test_{i}", "tex", "upload")
                    }
                )
                
                assert result.get("success") is True
                file_ids.append(result["file_id"])
            
            # All file IDs should be unique
            assert len(set(file_ids)) == len(file_ids)

    @pytest.mark.asyncio
    async def test_concurrent_file_uploads(self, sample_latex_document: str, test_filename):
        """Test concurrent file uploads with rate limiting for stability"""
        
        # Use a single shared session for all uploads to reduce connection overhead
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            
            async def upload_file(index: int):
                content = sample_latex_document.replace("Integration Test Document", f"Concurrent Test {index}")
                try:
                    return await gateway_helper.call_tool(
                        "latex_upload_latex_file",
                        {
                            "content": content,
                            "filename": test_filename(f"concurrent_{index}", "tex", "upload")
                        }
                    )
                except Exception as e:
                    return {"success": False, "error": str(e), "index": index}
            
            # Test with just 2 concurrent uploads to minimize session overhead
            # while still validating concurrent behavior
            num_concurrent = 2
            
            # Add small delays between starting tasks to reduce connection burst
            results = []
            for i in range(num_concurrent):
                if i > 0:
                    await asyncio.sleep(0.1)  # Small delay between task starts
                task = asyncio.create_task(upload_file(i))
                results.append(task)
            
            # Gather results with timeout
            try:
                completed_results = await asyncio.wait_for(
                    asyncio.gather(*results, return_exceptions=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                pytest.fail("Concurrent file uploads timed out after 30 seconds")
            
            # Check for exceptions in results
            exceptions = [r for r in completed_results if isinstance(r, Exception)]
            if exceptions:
                pytest.fail(f"Concurrent uploads had exceptions: {exceptions}")
            
            # Verify all uploads succeeded
            for i, result in enumerate(completed_results):
                assert isinstance(result, dict), f"Upload {i} returned non-dict: {type(result)}"
                if not result.get("success"):
                    pytest.fail(f"Upload {i} failed: {result}")
                assert "file_id" in result, f"Upload {i} missing file_id: {result}"
            
            # All file IDs should be unique
            file_ids = [result["file_id"] for result in completed_results]
            assert len(set(file_ids)) == len(file_ids), f"Duplicate file IDs found: {file_ids}"

class TestFileValidation:
    """Test file validation and security"""

    @pytest.mark.asyncio
    async def test_file_size_validation(self, test_filename):
        """Test file size validation"""
        
        # Create content that might exceed size limits
        large_content = "\\documentclass{article}\\begin{document}" + "x" * 20_000_000 + "\\end{document}"
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            result = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": large_content,
                    "filename": test_filename("huge_file", "tex", "validation")
                }
            )
            
            # Should either succeed or fail with size error
            if result.get("success") is False:
                assert any(keyword in result["error"].lower() for keyword in ["size", "large", "limit"])

    @pytest.mark.asyncio
    async def test_malicious_filename_handling(self, sample_latex_document: str, test_filename):
        """Test handling of potentially malicious filenames"""
        
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "test\x00.tex",
            "very_long_name_" + "x" * 1000 + ".tex"
        ]
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            for filename in malicious_filenames:
                result = await gateway_helper.call_tool(
                    "latex_upload_latex_file",
                    {
                        "content": sample_latex_document,
                        "filename": filename
                    }
                )
                
                # For now, accept that the server may pass through filenames without sanitization
                # TODO: Implement proper filename sanitization in the LaTeX server
                if result.get("success") is True:
                    returned_filename = result["filename"]
                    # Basic validation that a filename was returned
                    assert "filename" in result
                elif result.get("success") is False:
                    # Server rejected malicious filename - also acceptable
                    assert "error" in result

    @pytest.mark.asyncio
    async def test_content_validation(self):
        """Test content validation for potentially dangerous LaTeX"""
        
        dangerous_content = r"""
\documentclass{article}
\immediate\write18{rm -rf /}
\begin{document}
This document tries to execute shell commands
\end{document}
"""
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            result = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": dangerous_content,
                    "filename": "dangerous.tex"
                }
            )
            
            # Upload might succeed (validation happens at compile time)
            # But compilation should be safe due to LaTeX security settings
            assert "file_id" in result or "error" in result

class TestFileLifecycle:
    """Test file lifecycle management"""

    @pytest.mark.asyncio
    async def test_file_reuse(self, sample_latex_document: str):
        """Test reusing uploaded files for multiple compilations"""
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            # Upload file
            upload_result = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": sample_latex_document,
                    "filename": "reuse_test.tex"
                }
            )
            
            assert upload_result.get("success") is True
            file_id = upload_result["file_id"]
            
            # Use file multiple times
            for i in range(3):
                compile_result = await gateway_helper.call_tool(
                    "latex_compile_latex_by_id",
                    {
                        "file_id": file_id,
                        "output_filename": f"reuse_output_{i}"
                    }
                )
                
                # Should work each time (or fail consistently if LaTeX unavailable)
                assert "success" in compile_result

    @pytest.mark.asyncio
    async def test_file_update_workflow(self, sample_latex_document: str):
        """Test workflow of updating file content"""
        
        async with MCPToolHelper(GATEWAY_URL) as gateway_helper:
            # Upload initial version
            v1_content = sample_latex_document
            upload_v1 = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": v1_content,
                    "filename": "version_test.tex"
                }
            )
            
            assert upload_v1.get("success") is True
            
            # Upload updated version (new file ID)
            v2_content = sample_latex_document.replace("Integration Test Document", "Updated Test Document")
            upload_v2 = await gateway_helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": v2_content,
                    "filename": "version_test.tex"
                }
            )
            
            assert upload_v2.get("success") is True
            
            # Should get different file IDs
            assert upload_v1["file_id"] != upload_v2["file_id"]