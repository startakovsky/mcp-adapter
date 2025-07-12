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
File ID Collision Regression Tests

Tests to ensure that file uploads with identical filenames get unique file IDs
and that all uploaded files remain accessible via the API.
"""

import pytest
import httpx
import tempfile
import os
from pathlib import Path


FILE_SERVER_URL = "http://localhost:8003"


class TestFileIdCollisionRegression:
    """Regression tests for file ID collision bug fix"""

    @pytest.mark.asyncio
    async def test_multiple_uploads_same_filename_get_unique_file_ids(self):
        """Test that multiple uploads with same filename get unique file IDs"""
        
        # Create test PDF content
        test_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        filename = "test_document.pdf"
        
        async with httpx.AsyncClient() as client:
            # Upload same filename multiple times
            uploads = []
            for i in range(3):
                files = {
                    'file': (filename, test_content, 'application/pdf')
                }
                response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                
                assert response.status_code == 200
                upload_result = response.json()
                uploads.append(upload_result)
                
                # Verify successful upload
                assert upload_result["success"] is True
                assert "file_id" in upload_result
                assert upload_result["original_filename"] == filename
            
            # Verify all uploads got unique file IDs (now timestamp-based)
            file_ids = [upload["file_id"] for upload in uploads]
            assert len(set(file_ids)) == 3, f"Expected 3 unique file IDs, got: {file_ids}"
            
            # Verify all file IDs follow timestamp pattern: test_document-YYYY-MM-DDTHH-MM-SS-microsecondsZ
            import re
            timestamp_pattern = r"^test_document-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}Z$"
            for file_id in file_ids:
                assert re.match(timestamp_pattern, file_id), f"File ID '{file_id}' doesn't match timestamp pattern"
            
            # Verify all files are accessible via their unique file IDs
            for upload in uploads:
                file_id = upload["file_id"]
                
                # Test file content retrieval
                content_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                assert content_response.status_code == 200
                assert content_response.content == test_content
                
                # Test file URL generation
                url_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}/url")
                assert url_response.status_code == 200
                url_result = url_response.json()
                assert "url" in url_result
                assert "filename" in url_result

    @pytest.mark.asyncio
    async def test_latex_workflow_multiple_compilations_unique_pdfs(self):
        """Test LaTeX workflow: multiple compilations of same filename produce unique accessible PDFs"""
        
        # This test requires the gateway to be running for MCP tool access
        gateway_url = "http://localhost:8080"
        
        latex_content = r"""
        \documentclass{{article}}
        \begin{{document}}
        Test Document - Version {version}
        \end{{document}}
        """
        
        async with httpx.AsyncClient() as client:
            # Test gateway connectivity first
            try:
                health_response = await client.get(f"{gateway_url}/health")
                if health_response.status_code != 200:
                    pytest.skip("Gateway not available for LaTeX workflow test")
            except:
                pytest.skip("Gateway not available for LaTeX workflow test")
            
            # Upload same LaTeX file multiple times (simulating edits)
            file_ids = []
            for version in [1, 2, 3]:
                versioned_content = latex_content.format(version=version)
                
                # Upload LaTeX file
                upload_data = {
                    'content': versioned_content,
                    'filename': 'my_document.tex'
                }
                
                upload_response = await client.post(f"{FILE_SERVER_URL}/files/text", data=upload_data)
                assert upload_response.status_code == 200
                upload_result = upload_response.json()
                file_ids.append(upload_result["file_id"])
            
            # Verify all uploads got unique file IDs (now timestamp-based)
            assert len(set(file_ids)) == 3, f"Expected 3 unique file IDs, got: {file_ids}"
            
            # Verify all file IDs follow timestamp pattern: my_document-YYYY-MM-DDTHH-MM-SS-microsecondsZ
            import re
            timestamp_pattern = r"^my_document-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-\d{6}Z$"
            for file_id in file_ids:
                assert re.match(timestamp_pattern, file_id), f"File ID '{file_id}' doesn't match timestamp pattern"
            
            # Verify all LaTeX files are accessible
            for file_id in file_ids:
                content_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                assert content_response.status_code == 200
                assert "Test Document - Version" in content_response.text

    @pytest.mark.asyncio  
    async def test_file_server_metadata_consistency(self):
        """Test that file metadata remains consistent with unique file IDs"""
        
        filename = "consistency_test.txt"
        
        async with httpx.AsyncClient() as client:
            # Upload multiple files with same filename
            uploads = []
            for i in range(2):
                content = f"Content version {i+1}"
                files = {
                    'file': (filename, content.encode(), 'text/plain')
                }
                response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
                
                assert response.status_code == 200
                upload_result = response.json()
                uploads.append(upload_result)
            
            # List all files and verify metadata
            list_response = await client.get(f"{FILE_SERVER_URL}/files")
            assert list_response.status_code == 200
            files_data = list_response.json()
            
            # Find our uploaded files in the list
            our_files = [
                f for f in files_data.get("files", [])
                if f["file_id"] in [upload["file_id"] for upload in uploads]
            ]
            
            assert len(our_files) == 2, "Both files should be listed in metadata"
            
            # Verify each file has correct metadata
            for file_data in our_files:
                assert file_data["original_filename"] == filename
                assert "file_id" in file_data
                assert "size_bytes" in file_data
                
                # Verify file is accessible via its file_id
                file_id = file_data["file_id"]
                content_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}")
                assert content_response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__])