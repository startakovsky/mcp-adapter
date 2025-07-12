#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "fastapi>=0.115",
#     "uvicorn>=0.35",
#     "python-multipart>=0.0.6",
#     "aiofiles>=23.2"
# ]
# ///
"""
File Server

A simple REST API for file storage and retrieval, designed for use in the MCP Studio ecosystem.
Provides file upload, download, and deletion via standard HTTP endpoints.
"""

import os
import uuid
import json
import re
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
import aiofiles
import uvicorn

# Configuration
FILES_PATH = Path(os.getenv("SHARED_FILES_PATH", "./shared_files"))
FILES_PATH.mkdir(exist_ok=True)
METADATA_FILE = FILES_PATH / "metadata.json"

app = FastAPI(
    title="File Server",
    description="Simple file storage and retrieval API",
    version="0.3.0"
)

# Metadata management functions
async def load_metadata():
    """Load file metadata from JSON file"""
    try:
        if METADATA_FILE.exists():
            async with aiofiles.open(METADATA_FILE, 'r') as f:
                content = await f.read()
                return json.loads(content)
        return {}
    except Exception:
        return {}

async def save_metadata(metadata):
    """Save file metadata to JSON file"""
    try:
        async with aiofiles.open(METADATA_FILE, 'w') as f:
            await f.write(json.dumps(metadata, indent=2))
    except Exception:
        pass

async def add_file_metadata(file_id: str, original_filename: str, size_bytes: int):
    """Add metadata for a file"""
    metadata = await load_metadata()
    metadata[file_id] = {
        "original_filename": original_filename,
        "size_bytes": size_bytes
    }
    await save_metadata(metadata)

async def get_file_metadata(file_id: str):
    """Get metadata for a file"""
    metadata = await load_metadata()
    return metadata.get(file_id, {})

def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitize filename to prevent directory traversal and other security issues
    
    Args:
        filename: Input filename (may be None)
    
    Returns:
        Sanitized filename safe for file system use
    """
    if not filename:
        return ""
    
    # Remove or replace dangerous characters
    # Allow only alphanumeric, underscore, hyphen, and dot
    sanitized = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
    
    # Prevent directory traversal
    sanitized = sanitized.replace('..', '_')
    sanitized = sanitized.replace('/', '_')
    sanitized = sanitized.replace('\\', '_')
    
    # Filter out dangerous keywords (case insensitive) - completely remove them
    dangerous_keywords = ['drop', 'delete', 'truncate', 'insert', 'update', 'select', 'exec', 'script', 'cmd']
    for keyword in dangerous_keywords:
        # Use regex to remove keyword in any case
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        sanitized = pattern.sub('', sanitized)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 100:
        sanitized = sanitized[:100]
    
    # Ensure it doesn't start with a dot (hidden file)
    if sanitized.startswith('.'):
        sanitized = 'file_' + sanitized[1:]
    
    # If empty after sanitization, provide default
    if not sanitized:
        sanitized = 'document'
    
    return sanitized


@app.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    filename: Optional[str] = Form(None)
):
    """Upload a file and return a file_id"""
    try:
        # Use provided filename or original filename
        original_filename = filename or file.filename or "file"
        
        # Sanitize the filename for security
        sanitized_filename = sanitize_filename(original_filename)
        
        # Ensure we have a valid filename after sanitization
        if not sanitized_filename or sanitized_filename == "":
            sanitized_filename = "file"
        
        # Generate timestamp-based file ID with original filename base
        from datetime import datetime
        # Include microseconds to ensure uniqueness
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%fZ")
        
        # Extract base name without extension to avoid .pdf.pdf
        base_name = Path(sanitized_filename).stem
        ext = Path(sanitized_filename).suffix or ''
        
        # Create user-friendly file ID: basename-timestamp
        file_id = f"{base_name}-{timestamp}"
        
        # Create safe filename with extension
        safe_name = f"{file_id}{ext}"
        file_path = FILES_PATH / safe_name
        
        # Read and save file content
        content = await file.read()
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        # Save metadata
        await add_file_metadata(file_id, original_filename, len(content))
        
        return {
            "success": True,
            "file_id": file_id,
            "filename": safe_name,
            "original_filename": original_filename,
            "user_friendly_name": original_filename,
            "size_bytes": len(content)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/files/text")
async def upload_text_file(
    content: str = Form(...),
    filename: str = Form(...)
):
    """Upload a text file with content as form data"""
    try:
        # Generate timestamp-based file ID with original filename base
        from datetime import datetime
        # Include microseconds to ensure uniqueness
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S-%fZ")
        
        # Sanitize the filename for security
        sanitized_filename = sanitize_filename(filename)
        
        # Extract base name without extension to avoid .pdf.pdf
        base_name = Path(sanitized_filename).stem
        ext = Path(sanitized_filename).suffix or ''
        
        # Create user-friendly file ID: basename-timestamp
        file_id = f"{base_name}-{timestamp}"
        
        # Create safe filename with extension
        safe_name = f"{file_id}{ext}"
        file_path = FILES_PATH / safe_name
        
        # Save text content
        async with aiofiles.open(file_path, 'w') as f:
            await f.write(content)
        
        # Save metadata
        await add_file_metadata(file_id, filename, len(content.encode('utf-8')))
        
        return {
            "success": True,
            "file_id": file_id,
            "filename": safe_name,
            "original_filename": filename,
            "user_friendly_name": filename,
            "size_bytes": len(content.encode('utf-8'))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/files/{file_id}")
async def download_file(file_id: str):
    """Download a file by file_id"""
    try:
        # Find file with this ID
        for f in FILES_PATH.glob(f"{file_id}.*"):
            # Determine proper media type based on file extension
            suffix = f.suffix.lower()
            if suffix == '.pdf':
                media_type = 'application/pdf'
                # Use original filename without collision counter
                filename = f"{file_id}.pdf"
            elif suffix in ['.tex', '.txt']:
                media_type = 'text/plain'
                filename = f"{file_id}{suffix}"
            elif suffix in ['.png', '.jpg', '.jpeg']:
                media_type = f'image/{suffix[1:]}'
                filename = f"{file_id}{suffix}"
            else:
                media_type = 'application/octet-stream'
                filename = f"{file_id}{suffix}"
                
            return FileResponse(
                str(f),
                filename=filename,
                media_type=media_type
            )
        
        raise HTTPException(status_code=404, detail="File not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Delete a file by file_id"""
    try:
        deleted = False
        for f in FILES_PATH.glob(f"{file_id}.*"):
            f.unlink()
            deleted = True
        
        if not deleted:
            raise HTTPException(status_code=404, detail="File not found")
        
        return {"success": True, "message": "File deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@app.get("/files/{file_id}/url")
async def get_file_url(file_id: str):
    """Get a download URL for a file by file_id"""
    try:
        # Find file with this ID (look for files starting with file_id)
        for f in FILES_PATH.glob(f"{file_id}.*"):
            url = f"/files/{file_id}"
            return {
                "success": True,
                "url": url,
                "filename": f.name
            }
        
        raise HTTPException(status_code=404, detail="File not found")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"URL generation failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "File Server",
        "files_path": str(FILES_PATH)
    }

@app.get("/info")
async def info():
    """Server information endpoint"""
    return {
        "service": "File Server",
        "version": "0.3.0",
        "description": "Simple file storage and retrieval API",
        "files_path": str(FILES_PATH)
    }

@app.get("/files")
async def list_files():
    """List all files in the file server"""
    try:
        files = []
        metadata = await load_metadata()
        
        for f in FILES_PATH.glob("*"):
            if f.is_file() and f.name != "metadata.json":
                file_id = f.stem  # Extract file_id from filename
                file_metadata = metadata.get(file_id, {})
                
                files.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "file_id": file_id,
                    "original_filename": file_metadata.get("original_filename", f.name),
                    "download_url": f"/files/{file_id}/download"
                })
        
        return {
            "success": True,
            "files": files,
            "count": len(files)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

@app.post("/admin/cleanup")
async def cleanup_test_files():
    """Clean up test artifacts - admin endpoint"""
    try:
        import glob
        
        # Patterns to clean up (test artifacts and non-essential files)
        patterns = [
            "test_*",
            "leak_test_*", 
            "pytest_*",
            "concurrent_*",
            "rapid_*",
            "timeout_test_*",
            "upload_test*",
            "compile_test*",
            "image*",
            # Legacy test artifacts - these should be cleaned up
            "_etc_passwd*",
            "hosts*",
            "js*",
            "*TABLE*",
            "_____*",  # Long underscore patterns
            "aaaa*",   # Long 'a' patterns
            "_2e_2e_2f*",  # URL encoded patterns
            "my_document*",
            "compiled_output*",
            "custom_output*",
            "reuse_*"
        ]
        
        files_removed = 0
        metadata = await load_metadata()
        updated_metadata = {}
        
        # Check each file against patterns
        import fnmatch
        for f in FILES_PATH.glob("*"):
            if f.is_file() and f.name not in ["metadata.json", ".gitkeep"]:
                should_remove = False
                for pattern in patterns:
                    if fnmatch.fnmatch(f.name, pattern):
                        should_remove = True
                        break
                
                if should_remove:
                    f.unlink()
                    files_removed += 1
                else:
                    # Keep in metadata
                    file_id = f.stem
                    if file_id in metadata:
                        updated_metadata[file_id] = metadata[file_id]
        
        # Update metadata
        await save_metadata(updated_metadata)
        
        return {
            "success": True,
            "files_removed": files_removed,
            "remaining_files": len(updated_metadata)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")

if __name__ == "__main__":
    port = int(os.getenv('SERVER_PORT', 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
