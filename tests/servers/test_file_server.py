"""
File Server Tests

Tests for HTTP endpoints of the file server.
The file-server is a REST API service, not an MCP server.
"""

import os
import pytest
import httpx

FILE_SERVER_URL = os.getenv("FILE_SERVER_URL", "http://localhost:8003")


class TestFileServerHTTPEndpoints:
    """Test file server HTTP endpoints (legacy compatibility)"""

    @pytest.mark.asyncio
    async def test_upload_and_download_text_file(self):
        """Test uploading a text file and downloading it"""
        # Upload a text file
        files = {
            'file': ('test.txt', 'Hello, File Server!', 'text/plain')
        }
        
        async with httpx.AsyncClient() as client:
            # Upload file
            resp = await client.post(f"{FILE_SERVER_URL}/files", files=files)
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"]
            file_id = data["file_id"]
            filename = data["filename"]

            # Download file
            resp2 = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
            assert resp2.status_code == 200
            assert resp2.text == "Hello, File Server!"

            # Get file URL
            resp3 = await client.get(f"{FILE_SERVER_URL}/files/{file_id}/url")
            assert resp3.status_code == 200
            url_data = resp3.json()
            assert url_data["success"]
            assert url_data["url"].startswith("/files/")

            # Delete file
            resp4 = await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")
            assert resp4.status_code == 200
            del_data = resp4.json()
            assert del_data["success"]

            # Confirm deletion
            resp5 = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
            assert resp5.status_code == 404

@pytest.mark.asyncio
async def test_upload_text_content():
    """Test uploading text content via form data"""
    async with httpx.AsyncClient() as client:
        # Upload text content
        data = {
            'content': 'Hello, Text Upload!',
            'filename': 'test.txt'
        }
        
        resp = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
        assert resp.status_code == 200
        upload_data = resp.json()
        assert upload_data["success"]
        file_id = upload_data["file_id"]

        # Download and verify
        resp2 = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
        assert resp2.status_code == 200
        assert resp2.text == "Hello, Text Upload!"

        # Clean up
        await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")

@pytest.mark.asyncio
async def test_upload_binary_file():
    """Test uploading a binary file"""
    # Create a simple binary file (PNG header)
    binary_content = b"\x89PNG\r\n\x1a\n"
    
    files = {
        'file': ('image.png', binary_content, 'image/png')
    }
    
    async with httpx.AsyncClient() as client:
        # Upload binary file
        resp = await client.post(f"{FILE_SERVER_URL}/files", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]
        file_id = data["file_id"]

        # Download and verify
        resp2 = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
        assert resp2.status_code == 200
        assert resp2.content == binary_content

        # Clean up
        await client.delete(f"{FILE_SERVER_URL}/files/{file_id}")

@pytest.mark.asyncio
async def test_file_not_found():
    """Test handling of non-existent files"""
    async with httpx.AsyncClient() as client:
        # Try to download non-existent file
        resp = await client.get(f"{FILE_SERVER_URL}/files/nonexistent")
        assert resp.status_code == 404

        # Try to delete non-existent file
        resp2 = await client.delete(f"{FILE_SERVER_URL}/files/nonexistent")
        assert resp2.status_code == 404

        # Try to get URL for non-existent file
        resp3 = await client.get(f"{FILE_SERVER_URL}/files/nonexistent/url")
        assert resp3.status_code == 404

@pytest.mark.asyncio
async def test_health_and_info():
    """Test health and info endpoints"""
    async with httpx.AsyncClient() as client:
        # Health check
        resp = await client.get(f"{FILE_SERVER_URL}/health")
        assert resp.status_code == 200
        health_data = resp.json()
        assert health_data["status"] == "healthy"
        assert health_data["service"] == "File Server"

        # Info endpoint
        resp2 = await client.get(f"{FILE_SERVER_URL}/info")
        assert resp2.status_code == 200
        info_data = resp2.json()
        assert info_data["service"] == "File Server"
        assert info_data["version"] == "0.3.0"

@pytest.mark.asyncio
async def test_list_files():
    """Test listing files endpoint"""
    async with httpx.AsyncClient() as client:
        # List files
        resp = await client.get(f"{FILE_SERVER_URL}/files")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"]
        assert "files" in data
        assert "count" in data
        assert isinstance(data["files"], list)
        assert isinstance(data["count"], int)