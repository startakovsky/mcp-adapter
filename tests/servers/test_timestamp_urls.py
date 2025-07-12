#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#    "pytest==8.4.*",
#    "pytest-asyncio==1.0.*",
#    "httpx==0.28.*",
# ]
# ///
"""
Timestamp URL Format Tests

Tests to verify that file uploads generate user-friendly timestamp-based URLs
and that PDF extension handling prevents .pdf.pdf issues.
"""

import pytest
import httpx
import re
from datetime import datetime


FILE_SERVER_URL = "http://localhost:8003"


class TestTimestampUrlGeneration:
    """Test timestamp-based URL generation"""

    @pytest.mark.asyncio
    async def test_pdf_upload_generates_timestamp_url(self):
        """Test that PDF uploads generate timestamp-based file IDs without .pdf.pdf"""
        
        # Create test PDF content
        test_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        filename = "resume.pdf"
        
        async with httpx.AsyncClient() as client:
            files = {
                'file': (filename, test_content, 'application/pdf')
            }
            response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
            
            assert response.status_code == 200
            result = response.json()
            
            # Verify response structure
            assert result["success"] is True
            assert "file_id" in result
            assert result["original_filename"] == filename
            
            file_id = result["file_id"]
            
            # Verify file_id format: basename-YYYY-MM-DDTHH-MM-SS-microsecondsZ
            timestamp_pattern = r"^resume-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}Z$"
            assert re.match(timestamp_pattern, file_id), f"File ID '{file_id}' doesn't match timestamp pattern"
            
            # Verify filename is correct (should be file_id + .pdf)
            expected_filename = f"{file_id}.pdf"
            assert result["filename"] == expected_filename
            
            # Verify no double extension (.pdf.pdf)
            assert not result["filename"].endswith(".pdf.pdf")
            
            # Test file accessibility via generated URL
            url_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}/url")
            assert url_response.status_code == 200
            url_result = url_response.json()
            
            # Verify URL format
            expected_url = f"/files/{file_id}"
            assert url_result["url"] == expected_url
            
            # Test actual file download
            download_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
            assert download_response.status_code == 200
            assert download_response.content == test_content

    @pytest.mark.asyncio
    async def test_text_file_upload_generates_timestamp_url(self):
        """Test that text file uploads also generate timestamp-based URLs"""
        
        content = "Test LaTeX content"
        filename = "document.tex"
        
        async with httpx.AsyncClient() as client:
            data = {
                'content': content,
                'filename': filename
            }
            response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
            
            assert response.status_code == 200
            result = response.json()
            
            file_id = result["file_id"]
            
            # Verify file_id format for .tex file
            timestamp_pattern = r"^document-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}Z$"
            assert re.match(timestamp_pattern, file_id), f"File ID '{file_id}' doesn't match timestamp pattern"
            
            # Verify filename
            expected_filename = f"{file_id}.tex"
            assert result["filename"] == expected_filename

    @pytest.mark.asyncio
    async def test_filename_without_extension_handling(self):
        """Test handling of filenames without extensions"""
        
        test_content = b"Binary data"
        filename = "myfile"  # No extension
        
        async with httpx.AsyncClient() as client:
            files = {
                'file': (filename, test_content, 'application/octet-stream')
            }
            response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
            
            assert response.status_code == 200
            result = response.json()
            
            file_id = result["file_id"]
            
            # Should still generate timestamp format
            timestamp_pattern = r"^myfile-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}Z$"
            assert re.match(timestamp_pattern, file_id)
            
            # Filename should be just the file_id (no extension)
            assert result["filename"] == file_id

    @pytest.mark.asyncio
    async def test_multiple_uploads_same_base_name_unique_timestamps(self):
        """Test that multiple uploads of same filename get unique timestamps"""
        
        test_content = b"PDF content"
        filename = "test.pdf"
        
        async with httpx.AsyncClient() as client:
            file_ids = []
            
            # Upload same filename multiple times
            for i in range(3):
                files = {
                    'file': (filename, test_content, 'application/pdf')
                }
                response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                
                assert response.status_code == 200
                result = response.json()
                file_ids.append(result["file_id"])
                
                # Small delay to ensure different timestamps
                import asyncio
                await asyncio.sleep(0.1)
            
            # All file IDs should be unique
            assert len(set(file_ids)) == 3, f"Expected unique file IDs, got: {file_ids}"
            
            # All should follow timestamp pattern
            for file_id in file_ids:
                timestamp_pattern = r"^test-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}Z$"
                assert re.match(timestamp_pattern, file_id)
                
                # All files should be accessible
                download_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                assert download_response.status_code == 200

    @pytest.mark.asyncio
    async def test_timestamp_format_validity(self):
        """Test that generated timestamps are valid ISO 8601 format"""
        
        test_content = b"Test content"
        filename = "timetest.pdf"
        
        async with httpx.AsyncClient() as client:
            files = {
                'file': (filename, test_content, 'application/pdf')
            }
            response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
            
            assert response.status_code == 200
            result = response.json()
            
            file_id = result["file_id"]
            
            # Extract timestamp part
            timestamp_part = file_id.replace("timetest-", "")
            
            # Verify it can be parsed as a valid datetime
            try:
                parsed_time = datetime.strptime(timestamp_part, "%Y-%m-%dT%H-%M-%S-%fZ")
                assert parsed_time is not None
            except ValueError:
                pytest.fail(f"Generated timestamp '{timestamp_part}' is not valid ISO 8601 format")


if __name__ == "__main__":
    pytest.main([__file__])