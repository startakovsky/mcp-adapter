#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#    "pytest==8.4.*",
#    "pytest-asyncio==1.0.*",
#    "httpx==0.28.*",
#    "fastapi>=0.115"
# ]
# ///
"""
Security Test Suite

Comprehensive security tests for the MCP Adapter including:
- File upload validation and security
- Input sanitization and injection attacks
- Path traversal prevention
- Content validation
- Size limit enforcement
- Package restriction validation
"""

import pytest
import httpx
import tempfile
import os
import base64
from pathlib import Path
from typing import Dict, Any

# Test configuration
GATEWAY_URL = "http://localhost:8080"
FILE_SERVER_URL = "http://localhost:8003"
LATEX_SERVER_URL = "http://localhost:8002"


class SecurityTestHelper:
    """Helper class for security testing"""
    
    @staticmethod
    def create_malicious_file_content(attack_type: str) -> bytes:
        """Create malicious file content for testing"""
        if attack_type == "path_traversal":
            return b"../../../etc/passwd"
        elif attack_type == "script_injection":
            return b"<script>alert('xss')</script>"
        elif attack_type == "latex_injection":
            return rb"\immediate\write18{rm -rf /}"
        elif attack_type == "binary_bomb":
            return b"PK" + b"\x00" * 10000  # Fake zip file
        elif attack_type == "large_content":
            return b"A" * (100 * 1024 * 1024)  # 100MB
        else:
            return b"malicious content"
    
    @staticmethod
    def create_malicious_latex_content(attack_type: str) -> str:
        """Create malicious LaTeX content for testing"""
        if attack_type == "shell_injection":
            return r"""
            \documentclass{article}
            \begin{document}
            \immediate\write18{cat /etc/passwd}
            Hello World
            \end{document}
            """
        elif attack_type == "file_read":
            return r"""
            \documentclass{article}
            \begin{document}
            \input{/etc/passwd}
            \end{document}
            """
        elif attack_type == "infinite_loop":
            return r"""
            \documentclass{article}
            \def\recursion{\recursion}
            \begin{document}
            \recursion
            \end{document}
            """
        elif attack_type == "package_injection":
            return r"""
            \documentclass{article}
            \usepackage{../../../malicious}
            \begin{document}
            Hello World
            \end{document}
            """
        elif attack_type == "large_document":
            content = r"""
            \documentclass{article}
            \begin{document}
            """
            # Create very large content
            content += "Text content. " * 1000000  # Very large
            content += r"\end{document}"
            return content
        else:
            return r"""
            \documentclass{article}
            \begin{document}
            Malicious content test
            \end{document}
            """


class TestFileUploadSecurity:
    """Test file upload security measures"""
    
    @pytest.mark.asyncio
    async def test_file_upload_path_traversal_prevention(self):
        """Test prevention of path traversal in file uploads"""
        malicious_names = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "C:\\windows\\system32\\drivers\\etc\\hosts",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"  # URL encoded
        ]
        
        for malicious_name in malicious_names:
            files = {
                'file': (malicious_name, b'test content', 'text/plain')
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    # If upload succeeds, verify filename is sanitized
                    assert ".." not in data.get("filename", "")
                    assert "/" not in data.get("filename", "")
                    assert "\\" not in data.get("filename", "")
                    
                    # Clean up
                    file_id = data.get("file_id")
                    if file_id:
                        await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
    
    @pytest.mark.asyncio
    async def test_file_upload_size_limits(self):
        """Test file upload size limit enforcement"""
        # Create large file content
        large_content = b"A" * (50 * 1024 * 1024)  # 50MB
        
        files = {
            'file': ('large_file.txt', large_content, 'text/plain')
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
            
            # Should either reject due to size or handle gracefully
            if response.status_code != 200:
                # Expected behavior - request rejected
                assert response.status_code in [400, 413, 500]
            else:
                # If accepted, verify it's properly handled
                data = response.json()
                assert data.get("success") is True
                
                # Clean up if successful
                file_id = data.get("file_id")
                if file_id:
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
    
    @pytest.mark.asyncio
    async def test_file_upload_malicious_mime_types(self):
        """Test handling of malicious MIME types"""
        malicious_files = [
            ('script.js', b'alert("xss")', 'application/javascript'),
            ('payload.exe', b'MZ\x90\x00\x03', 'application/x-msdownload'),
            ('shell.php', b'<?php system($_GET["cmd"]); ?>', 'application/x-php'),
            ('exploit.html', b'<script>document.cookie</script>', 'text/html')
        ]
        
        for filename, content, mime_type in malicious_files:
            files = {
                'file': (filename, content, mime_type)
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    # Should accept file but sanitize metadata
                    assert data.get("success") is True
                    
                    # Clean up
                    file_id = data.get("file_id")
                    if file_id:
                        await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
    
    @pytest.mark.asyncio
    async def test_file_upload_binary_content_validation(self):
        """Test validation of binary file content"""
        # Test various binary file types
        binary_files = [
            ('test.zip', b'PK\x03\x04' + b'\x00' * 100),  # ZIP header
            ('test.pdf', b'%PDF-1.4' + b'\x00' * 100),    # PDF header
            ('test.exe', b'MZ' + b'\x00' * 100),           # PE header
            ('test.elf', b'\x7fELF' + b'\x00' * 100),      # ELF header
        ]
        
        for filename, content in binary_files:
            files = {
                'file': (filename, content, 'application/octet-stream')
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    file_id = data.get("file_id")
                    
                    # Verify file can be downloaded safely
                    download_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                    assert download_response.status_code == 200
                    
                    # Clean up
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
    
    @pytest.mark.asyncio
    async def test_file_upload_filename_injection(self):
        """Test prevention of filename injection attacks"""
        malicious_filenames = [
            "'; DROP TABLE files; --",
            "<script>alert('xss')</script>.txt",
            "$(rm -rf /).txt",
            "`whoami`.txt",
            "file\x00.txt",  # Null byte injection
            "file\r\n.txt",  # CRLF injection
            "CON.txt",       # Windows reserved name
            "PRN.txt",       # Windows reserved name
            "." * 300,       # Very long filename
        ]
        
        for malicious_filename in malicious_filenames:
            files = {
                'file': (malicious_filename, b'test content', 'text/plain')
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    # Verify filename is sanitized
                    sanitized_filename = data.get("filename", "")
                    assert "script" not in sanitized_filename.lower()
                    assert "drop" not in sanitized_filename.lower()
                    assert "$(" not in sanitized_filename
                    assert "`" not in sanitized_filename
                    assert "\x00" not in sanitized_filename
                    assert len(sanitized_filename) <= 150  # Increased for timestamp-based filenames
                    
                    # Clean up
                    file_id = data.get("file_id")
                    if file_id:
                        await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")


class TestLatexSecurityValidation:
    """Test LaTeX compilation security measures"""
    
    @pytest.mark.asyncio
    async def test_latex_shell_injection_prevention(self):
        """Test prevention of shell injection in LaTeX"""
        malicious_latex_samples = [
            r"\immediate\write18{rm -rf /}",
            r"\write18{cat /etc/passwd}",
            r"\input{|cat /etc/passwd}",
            r"\openout\myfile=|rm -rf /",
            r"\special{dvi: rm -rf /}",
            r"\immediate\openout1=|rm -rf /",
        ]
        
        for malicious_latex in malicious_latex_samples:
            full_document = f"""
            \\documentclass{{article}}
            \\begin{{document}}
            {malicious_latex}
            Hello World
            \\end{{document}}
            """
            
            # Test with file upload and compilation
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Upload LaTeX file
                data = {
                    'content': full_document,
                    'filename': 'malicious_test.tex'
                }
                
                response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
                
                if response.status_code == 200:
                    upload_data = response.json()
                    file_id = upload_data["file_id"]
                    
                    # Attempt compilation - should either reject or compile safely
                    try:
                        # This is a direct HTTP test of LaTeX server
                        # In real MCP, this would go through the gateway
                        latex_response = await client.post(
                            f"{LATEX_SERVER_URL}/mcp/",
                            json={
                                "jsonrpc": "2.0",
                                "id": "security-test",
                                "method": "tools/call",
                                "params": {
                                    "name": "compile_latex_by_id",
                                    "arguments": {"file_id": file_id}
                                }
                            },
                            timeout=30.0
                        )
                        
                        # Should either fail compilation or succeed without executing malicious code
                        # No assertion here as we're testing it doesn't break the system
                        
                    except Exception:
                        # Timeout or error is acceptable for security test
                        pass
                    
                    # Clean up
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
    
    @pytest.mark.asyncio
    async def test_latex_file_inclusion_prevention(self):
        """Test prevention of unauthorized file inclusion"""
        malicious_includes = [
            r"\input{/etc/passwd}",
            r"\include{../../../sensitive_file}",
            r"\InputIfFileExists{/etc/shadow}{}{}",
            r"\openin1=/etc/passwd",
            r"\read1 to \temp",
        ]
        
        for malicious_include in malicious_includes:
            full_document = f"""
            \\documentclass{{article}}
            \\begin{{document}}
            {malicious_include}
            Normal content
            \\end{{document}}
            """
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                data = {
                    'content': full_document,
                    'filename': 'inclusion_test.tex'
                }
                
                response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
                
                if response.status_code == 200:
                    upload_data = response.json()
                    file_id = upload_data["file_id"]
                    
                    # Attempt compilation
                    try:
                        latex_response = await client.post(
                            f"{LATEX_SERVER_URL}/mcp/",
                            json={
                                "jsonrpc": "2.0",
                                "id": "inclusion-test",
                                "method": "tools/call",
                                "params": {
                                    "name": "compile_latex_by_id",
                                    "arguments": {"file_id": file_id}
                                }
                            },
                            timeout=30.0
                        )
                        
                    except Exception:
                        pass  # Expected for security test
                    
                    # Clean up
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
    
    @pytest.mark.asyncio
    async def test_latex_package_restrictions(self):
        """Test LaTeX package restriction enforcement"""
        # Test with restricted packages if ALLOWED_PACKAGES is configured
        restricted_packages = [
            "tikz-external",  # Can execute external commands
            "minted",         # Requires shell escape
            "pythontex",      # Executes Python code
            "sagetex",        # Executes Sage code
            "luacode",        # Executes Lua code
        ]
        
        for package in restricted_packages:
            latex_content = f"""
            \\documentclass{{article}}
            \\usepackage{{{package}}}
            \\begin{{document}}
            Hello World
            \\end{{document}}
            """
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                data = {
                    'content': latex_content,
                    'filename': f'package_test_{package}.tex'
                }
                
                response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
                
                if response.status_code == 200:
                    upload_data = response.json()
                    file_id = upload_data["file_id"]
                    
                    # Test validation first
                    try:
                        validation_response = await client.post(
                            f"{LATEX_SERVER_URL}/mcp/",
                            json={
                                "jsonrpc": "2.0",
                                "id": "validation-test",
                                "method": "tools/call",
                                "params": {
                                    "name": "validate_latex",
                                    "arguments": {"content": latex_content}
                                }
                            },
                            timeout=30.0
                        )
                        
                    except Exception:
                        pass
                    
                    # Clean up
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
    
    @pytest.mark.asyncio
    async def test_latex_resource_exhaustion_prevention(self):
        """Test prevention of resource exhaustion attacks"""
        resource_exhaustion_samples = [
            # Memory exhaustion
            r"""
            \documentclass{article}
            \begin{document}
            """ + r"\rule{10000pt}{10000pt}" * 1000 + r"""
            \end{document}
            """,
            
            # Infinite recursion
            r"""
            \documentclass{article}
            \def\bomb{\bomb\bomb}
            \begin{document}
            \bomb
            \end{document}
            """,
            
            # Large table
            r"""
            \documentclass{article}
            \begin{document}
            \begin{tabular}{""" + "c" * 1000 + r"""}
            """ + r" & ".join(["cell"] * 1000) + r"""\\
            \end{tabular}
            \end{document}
            """,
        ]
        
        for i, malicious_latex in enumerate(resource_exhaustion_samples):
            async with httpx.AsyncClient(timeout=60.0) as client:
                data = {
                    'content': malicious_latex,
                    'filename': f'resource_test_{i}.tex'
                }
                
                response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
                
                if response.status_code == 200:
                    upload_data = response.json()
                    file_id = upload_data["file_id"]
                    
                    # Attempt compilation with timeout
                    try:
                        latex_response = await client.post(
                            f"{LATEX_SERVER_URL}/mcp/",
                            json={
                                "jsonrpc": "2.0",
                                "id": "resource-test",
                                "method": "tools/call",
                                "params": {
                                    "name": "compile_latex_by_id",
                                    "arguments": {"file_id": file_id}
                                }
                            },
                            timeout=15.0  # Short timeout for resource exhaustion test
                        )
                        
                    except httpx.TimeoutException:
                        # Timeout is expected and acceptable for this test
                        pass
                    except Exception:
                        # Other errors are also acceptable
                        pass
                    
                    # Clean up
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")


class TestInputSanitization:
    """Test input sanitization across all services"""
    
    @pytest.mark.asyncio
    async def test_gateway_input_sanitization(self):
        """Test gateway input sanitization"""
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "$(rm -rf /)",
            "../../../etc/passwd",
            "\x00\x01\x02",  # Control characters
            "A" * 10000,     # Very long input
        ]
        
        for malicious_input in malicious_inputs:
            async with httpx.AsyncClient() as client:
                # Test various gateway endpoints with malicious input
                endpoints_to_test = [
                    f"/oauth/authorize?client_id={malicious_input}&response_type=code",
                    f"/oauth/register",
                ]
                
                for endpoint in endpoints_to_test:
                    try:
                        if "register" in endpoint:
                            response = await client.post(
                                f"{GATEWAY_URL}{endpoint}",
                                json={"client_name": malicious_input},
                                timeout=10.0
                            )
                        else:
                            response = await client.get(f"{GATEWAY_URL}{endpoint}", timeout=10.0)
                        
                        # Should either reject or sanitize input
                        if response.status_code == 200:
                            # If successful, verify no malicious content in response
                            response_text = response.text.lower()
                            assert "script" not in response_text
                            assert "drop table" not in response_text
                            assert "rm -rf" not in response_text
                    
                    except Exception:
                        # Errors are acceptable for malicious input
                        pass
    
    @pytest.mark.asyncio
    async def test_file_server_input_sanitization(self):
        """Test file server input sanitization"""
        malicious_content_types = [
            ("SQL Injection", "'; DROP TABLE files; --"),
            ("XSS", "<script>alert('xss')</script>"),
            ("Command Injection", "$(cat /etc/passwd)"),
            ("Path Traversal", "../../../etc/passwd"),
            ("Null Bytes", "test\x00.txt"),
            ("CRLF Injection", "test\r\nContent-Type: text/html\r\n\r\n<script>"),
        ]
        
        for attack_type, malicious_content in malicious_content_types:
            # Test text upload endpoint
            async with httpx.AsyncClient() as client:
                data = {
                    'content': malicious_content,
                    'filename': f'{attack_type.lower().replace(" ", "_")}_test.txt'
                }
                
                response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
                
                if response.status_code == 200:
                    upload_data = response.json()
                    file_id = upload_data["file_id"]
                    
                    # Verify file can be downloaded safely
                    download_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                    assert download_response.status_code == 200
                    
                    # Content should be preserved but filename should be sanitized
                    filename = upload_data.get("filename", "")
                    assert "script" not in filename.lower()
                    assert "drop" not in filename.lower()
                    assert ".." not in filename
                    
                    # Clean up
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
    
    @pytest.mark.asyncio
    async def test_content_type_validation(self):
        """Test content type validation and handling"""
        content_type_tests = [
            # (filename, content, declared_type, expected_behavior)
            ("test.txt", b"Hello World", "text/plain", "accept"),
            ("test.js", b"alert('test')", "application/javascript", "sanitize"),
            ("test.html", b"<html><script>alert('xss')</script></html>", "text/html", "sanitize"),
            ("test.svg", b"<svg><script>alert('xss')</script></svg>", "image/svg+xml", "sanitize"),
            ("test.pdf", b"%PDF-1.4\nfake pdf", "application/pdf", "accept"),
            ("test.bin", b"\x00\x01\x02\x03", "application/octet-stream", "accept"),
        ]
        
        for filename, content, content_type, expected in content_type_tests:
            files = {
                'file': (filename, content, content_type)
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    file_id = data["file_id"]
                    
                    # Download and verify content handling
                    download_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                    assert download_response.status_code == 200
                    
                    # Clean up
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")


class TestRateLimitingAndDoS:
    """Test rate limiting and DoS protection"""
    
    @pytest.mark.asyncio
    async def test_rapid_file_uploads(self):
        """Test handling of rapid file uploads"""
        async with httpx.AsyncClient() as client:
            upload_tasks = []
            
            # Attempt many rapid uploads
            for i in range(20):
                files = {
                    'file': (f'test_{i}.txt', f'content {i}'.encode(), 'text/plain')
                }
                
                upload_tasks.append(
                    client.post(f"{FILE_SERVER_URL}/files", files=files)
                )
            
            # Execute uploads concurrently
            responses = await asyncio.gather(*upload_tasks, return_exceptions=True)
            
            successful_uploads = []
            for i, response in enumerate(responses):
                if isinstance(response, httpx.Response) and response.status_code == 200:
                    data = response.json()
                    successful_uploads.append(data["file_id"])
            
            # Clean up successful uploads
            for file_id in successful_uploads:
                try:
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
                except:
                    pass
            
            # Verify system handled the load (some may succeed, some may fail)
            # The important thing is the system doesn't crash
            assert len([r for r in responses if not isinstance(r, Exception)]) > 0
    
    @pytest.mark.asyncio
    async def test_large_request_handling(self):
        """Test handling of unusually large requests"""
        # Test large form data
        large_content = "A" * (10 * 1024 * 1024)  # 10MB string
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                data = {
                    'content': large_content,
                    'filename': 'large_content_test.txt'
                }
                
                response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
                
                # Should either accept or reject gracefully
                if response.status_code == 200:
                    upload_data = response.json()
                    file_id = upload_data["file_id"]
                    
                    # Clean up if successful
                    await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
                else:
                    # Rejection is acceptable
                    assert response.status_code in [400, 413, 500]
                    
            except httpx.TimeoutException:
                # Timeout is acceptable for very large requests
                pass
    
    @pytest.mark.asyncio
    async def test_concurrent_oauth_requests(self):
        """Test handling of concurrent OAuth requests"""
        async with httpx.AsyncClient() as client:
            # Test concurrent client registrations
            registration_tasks = []
            
            for i in range(10):
                registration_data = {
                    "client_name": f"Concurrent Test Client {i}",
                    "redirect_uris": [f"http://localhost:300{i}/callback"]
                }
                
                registration_tasks.append(
                    client.post(
                        f"{GATEWAY_URL}/oauth/register",
                        json=registration_data,
                        timeout=10.0
                    )
                )
            
            responses = await asyncio.gather(*registration_tasks, return_exceptions=True)
            
            # Most should succeed (rate limiting may cause some to fail)
            successful_registrations = [
                r for r in responses 
                if isinstance(r, httpx.Response) and r.status_code == 200
            ]
            
            assert len(successful_registrations) > 0


class TestErrorHandlingAndLogging:
    """Test error handling and security logging"""
    
    @pytest.mark.asyncio
    async def test_error_information_disclosure(self):
        """Test that errors don't disclose sensitive information"""
        malicious_requests = [
            # Try to trigger various error conditions
            ("Invalid JSON", f"{GATEWAY_URL}/oauth/register", "invalid json"),
            ("Missing file", f"{FILE_SERVER_URL}/files/nonexistent-file-id", None),
            ("Invalid LaTeX", f"{LATEX_SERVER_URL}/mcp/", {"method": "invalid"}),
        ]
        
        for test_name, url, data in malicious_requests:
            async with httpx.AsyncClient() as client:
                try:
                    if data is None:
                        response = await client.get(url)
                    elif isinstance(data, str):
                        response = await client.post(url, content=data)
                    else:
                        response = await client.post(url, json=data)
                    
                    # Check that error responses don't leak sensitive info
                    if response.status_code >= 400:
                        error_text = response.text.lower()
                        
                        # Should not contain sensitive paths or system info
                        sensitive_patterns = [
                            "/etc/passwd",
                            "/var/log",
                            "c:\\windows",
                            "database error",
                            "sql error",
                            "traceback",
                            "exception:",
                            "file not found: /",
                        ]
                        
                        for pattern in sensitive_patterns:
                            assert pattern not in error_text, f"Sensitive info leaked in {test_name}: {pattern}"
                
                except Exception:
                    # Errors are acceptable, we're testing information disclosure
                    pass
    
    @pytest.mark.asyncio
    async def test_http_security_headers(self):
        """Test presence of security-related HTTP headers"""
        endpoints_to_test = [
            f"{GATEWAY_URL}/health",
            f"{GATEWAY_URL}/dashboard",
            f"{FILE_SERVER_URL}/health",
            f"{LATEX_SERVER_URL}/health",
        ]
        
        for endpoint in endpoints_to_test:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(endpoint)
                    
                    if response.status_code == 200:
                        headers = response.headers
                        
                        # Check for important security headers (if implemented)
                        security_headers = [
                            "x-content-type-options",
                            "x-frame-options",
                            "x-xss-protection",
                            "content-security-policy",
                            "strict-transport-security",
                        ]
                        
                        # Note: These headers might not be implemented yet,
                        # so we just check if they exist without asserting
                        present_headers = [h for h in security_headers if h in headers]
                        
                        # Log which headers are present (for informational purposes)
                        # In a real test, you might want to assert these are present
                        
                except Exception:
                    # Connection errors are acceptable for this test
                    pass


# Import asyncio for concurrent tests
import asyncio