#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "fastmcp>=2.10",
#     "pydantic>=2.11",
#     "jinja2>=3.1",
#     "aiofiles>=24.1",
#     "fastapi>=0.115",
#     "httpx>=0.28"
# ]
# ///
"""
LaTeX MCP Server

A Model Context Protocol server for compiling LaTeX documents to PDF.
"""

import os
import asyncio
import subprocess
import tempfile
import shutil
import uuid
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
from jinja2 import Environment, FileSystemLoader, Template
from fastmcp import FastMCP
from pydantic import BaseModel, Field
import aiofiles
import httpx
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', './output'))
TEMPLATE_DIR = Path(os.getenv('TEMPLATE_DIR', './templates'))
UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', './uploads'))
SHARED_FILES_PATH = Path(os.getenv('SHARED_FILES_PATH', './shared_files'))
FILE_SERVER_URL = os.getenv('FILE_SERVER_URL', 'http://file-server:8000')
LATEX_COMPILER = os.getenv('LATEX_COMPILER', 'pdflatex')
LATEX_TIMEOUT = int(os.getenv('LATEX_TIMEOUT', '30'))
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '10485760'))  # 10MB
ALLOWED_PACKAGES = os.getenv('ALLOWED_PACKAGES', '').split(',')
SAVE_INTERMEDIATE = os.getenv('SAVE_INTERMEDIATE_FILES', 'true').lower() == 'true'

# Ensure directories exist
OUTPUT_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# In-memory storage for file metadata
file_metadata_store = {}
SHARED_FILES_PATH.mkdir(exist_ok=True)

# File management
file_store = {}  # In-memory file store for demonstration

# Initialize MCP server
mcp = FastMCP("LaTeX Server")

async def upload_pdf_to_file_server(pdf_path: Path, original_filename: str) -> Dict[str, Any]:
    """Upload a PDF to the file server and return the file_id and download URL"""
    try:
        async with httpx.AsyncClient() as client:
            # Read the PDF file
            async with aiofiles.open(pdf_path, 'rb') as f:
                pdf_content = await f.read()
            
            # Upload to file server
            files = {
                'file': (original_filename, pdf_content, 'application/pdf')
            }
            
            response = await client.post(f"{FILE_SERVER_URL}/files", files=files)
            
            if response.status_code == 200:
                upload_result = response.json()
                file_id = upload_result["file_id"]
                
                # Get the download URL
                url_response = await client.get(f"{FILE_SERVER_URL}/files/{file_id}/url")
                if url_response.status_code == 200:
                    url_result = url_response.json()
                    download_url = f"http://localhost:8003{url_result['url']}"
                    
                    return {
                        "success": True,
                        "file_id": file_id,
                        "download_url": download_url,
                        "filename": url_result["filename"]
                    }
            
            return {
                "success": False,
                "error": f"Failed to upload to file server: {response.status_code}"
            }
            
    except Exception as e:
        logger.error(f"Error uploading PDF to file server: {e}")
        return {
            "success": False,
            "error": f"Upload failed: {str(e)}"
        }

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

class CompilationRequest(BaseModel):
    """Request model for LaTeX compilation"""
    content: str = Field(..., description="LaTeX content to compile")
    filename: Optional[str] = Field(None, description="Output filename (without extension)")
    compiler: Optional[str] = Field(None, description="LaTeX compiler to use (pdflatex, xelatex, lualatex)")

class TemplateRequest(BaseModel):
    """Request model for template-based compilation"""
    template_name: str = Field(..., description="Name of the template to use")
    variables: Dict[str, Any] = Field(..., description="Variables to substitute in template")
    filename: Optional[str] = Field(None, description="Output filename (without extension)")

class ValidationRequest(BaseModel):
    """Request model for LaTeX validation"""
    content: str = Field(..., description="LaTeX content to validate")

class FileUploadRequest(BaseModel):
    """Request model for file upload"""
    content: str = Field(..., description="LaTeX file content")
    filename: Optional[str] = Field(None, description="Original filename")

class FileCompileRequest(BaseModel):
    """Request model for file-based compilation"""
    file_id: str = Field(..., description="File ID from upload")
    compiler: Optional[str] = Field(None, description="LaTeX compiler to use")
    output_filename: Optional[str] = Field(None, description="Output filename")


@mcp.tool
async def compile_from_template(request: TemplateRequest) -> Dict[str, Any]:
    """
    Compile PDF from LaTeX template with variable substitution
    
    Args:
        request: Template request with template name and variables
    
    Returns:
        Dict with compilation results
    """
    try:
        template_path = TEMPLATE_DIR / f"{request.template_name}.tex"
        
        if not template_path.exists():
            return {
                "success": False,
                "error": f"Template '{request.template_name}' not found"
            }
        
        # Load and render template
        env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        template = env.get_template(f"{request.template_name}.tex")
        rendered_content = template.render(**request.variables)
        
        # Generate and sanitize filename
        safe_filename = sanitize_filename(request.filename) or f"{request.template_name}_{hash(str(request.variables)) % 10000}"
        
        # Compile rendered content
        result = await _compile_latex_content(
            content=rendered_content,
            filename=safe_filename,
            compiler=LATEX_COMPILER
        )
        
        # Add template info to result
        result["template_used"] = request.template_name
        result["variables"] = request.variables
        
        return result
        
    except Exception as e:
        logger.error(f"Template compilation error: {e}")
        return {
            "success": False,
            "error": f"Template compilation failed: {str(e)}"
        }


@mcp.tool
async def upload_latex_file(request: FileUploadRequest) -> Dict[str, Any]:
    """
    Upload a LaTeX file and return file ID for compilation
    """
    try:
        # Validate content size
        if len(request.content.encode('utf-8')) > MAX_FILE_SIZE:
            return {
                "success": False,
                "error": f"File too large. Max size: {MAX_FILE_SIZE} bytes"
            }
        
        # Use provided filename or generate default
        original_filename = request.filename or "document"
        
        # Sanitize filename for security
        safe_filename = sanitize_filename(original_filename)
        if not safe_filename:
            safe_filename = f"document_{str(uuid.uuid4())[:8]}"
        
        # Strip any existing extension to avoid double extensions like .pdf.pdf
        safe_filename = Path(safe_filename).stem
        
        # Ensure .tex extension
        safe_filename += '.tex'
        
        # Upload to file server
        async with httpx.AsyncClient() as client:
            data = {
                'content': request.content,
                'filename': safe_filename
            }
            
            response = await client.post(f"{FILE_SERVER_URL}/files/text", data=data)
            
            if response.status_code == 200:
                upload_result = response.json()
                file_id = upload_result["file_id"]
                
                # Store original filename in memory
                file_metadata_store[file_id] = {
                    "original_filename": original_filename,
                    "safe_filename": safe_filename
                }
                
                return {
                    "success": True,
                    "file_id": file_id,
                    "filename": upload_result["filename"],
                    "original_filename": original_filename,
                    "user_friendly_name": safe_filename,
                    "size_bytes": upload_result["size_bytes"]
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to upload to file server: {response.status_code}"
                }
        
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return {
            "success": False,
            "error": f"Upload failed: {str(e)}"
        }

@mcp.tool
async def compile_latex_by_id(request: FileCompileRequest) -> Dict[str, Any]:
    """
    Compile LaTeX file by ID with minimal token usage
    
    Args:
        request: File compilation request with file_id and options
    
    Returns:
        Dict with compilation results including file_id, download_url, and filename
        
    Note on output_filename parameter:
        - Controls the download URL path and affects the downloaded filename
        - PDF extension is added automatically during compilation
        - Examples:
          * output_filename: "report" → URL: /files/report, downloaded as: report.pdf
          * output_filename: "report.pdf" → URL: /files/report.pdf, downloaded as: report.pdf.pdf
        - Recommended: Use clean names without .pdf extension for cleaner URLs
        - If not specified, uses the original upload filename with .pdf extension
    """
    try:
        # Get file content and metadata from file server
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{FILE_SERVER_URL}/files/{request.file_id}")
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": "File not found. Please upload file first."
                }
            
            content = response.text
            
            # Get original filename from our in-memory store
            stored_metadata = file_metadata_store.get(request.file_id)
            if stored_metadata:
                original_filename = stored_metadata["original_filename"]
            else:
                # Fallback: try to get from file server metadata
                try:
                    list_response = await client.get(f"{FILE_SERVER_URL}/files")
                    if list_response.status_code == 200:
                        files_data = list_response.json()
                        file_metadata = next(
                            (f for f in files_data.get("files", []) if f["file_id"] == request.file_id),
                            None
                        )
                        original_filename = file_metadata.get("original_filename", "document") if file_metadata else "document"
                    else:
                        original_filename = "document"
                except Exception:
                    original_filename = "document"
        
        # Validate packages if specified
        if ALLOWED_PACKAGES and ALLOWED_PACKAGES[0]:
            used_packages = extract_packages(content)
            forbidden = [pkg for pkg in used_packages if pkg not in ALLOWED_PACKAGES]
            if forbidden:
                return {
                    "success": False,
                    "error": f"Forbidden packages: {forbidden}"
                }
        
        # Generate output filename based on original filename
        if request.output_filename:
            output_filename = request.output_filename
        else:
            # Extract base name from original filename and change extension to .pdf
            base_name = Path(original_filename).stem
            output_filename = f"{base_name}.pdf"
        
        # Sanitize the output filename
        safe_output_filename = sanitize_filename(output_filename)
        if not safe_output_filename:
            safe_output_filename = f"compiled_{request.file_id[:8]}"
        
        # Remove .pdf extension if present since _compile_latex_content will add it
        if safe_output_filename.endswith('.pdf'):
            safe_output_filename = safe_output_filename[:-4]
        
        # Compile LaTeX
        result = await _compile_latex_content(
            content=content,
            filename=safe_output_filename,
            compiler=request.compiler or LATEX_COMPILER
        )
        
        # Return result with updated fields
        if result["success"]:
            return {
                "success": True,
                "file_id": result["file_id"],
                "download_url": result["download_url"],
                "filename": result["filename"],
                "original_filename": original_filename,
                "output_filename": output_filename,
                "size_bytes": result["size_bytes"]
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Compilation failed")
            }
            
    except Exception as e:
        logger.error(f"File compilation error: {e}")
        return {
            "success": False,
            "error": f"Compilation failed: {str(e)}"
        }


@mcp.tool
async def list_templates() -> Dict[str, Any]:
    """
    List available LaTeX templates
    
    Returns:
        Dict with available templates and their descriptions
    """
    try:
        templates = {}
        
        for template_file in TEMPLATE_DIR.glob("*.tex"):
            template_name = template_file.stem
            
            # Try to extract description from template comments
            description = "No description available"
            try:
                async with aiofiles.open(template_file, 'r') as f:
                    content = await f.read()
                    for line in content.split('\n')[:10]:  # Check first 10 lines
                        if line.strip().startswith('% Description:'):
                            description = line.replace('% Description:', '').strip()
                            break
            except Exception:
                pass
            
            templates[template_name] = {
                "description": description,
                "path": str(template_file)
            }
        
        return {
            "templates": templates,
            "count": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Template listing error: {e}")
        return {
            "templates": {},
            "error": f"Failed to list templates: {str(e)}"
        }

async def _compile_latex_content(content: str, filename: str, compiler: str) -> Dict[str, Any]:
    """Internal function to compile LaTeX content"""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Handle filename - if it already has .tex extension, use as is
        if filename.endswith('.tex'):
            tex_filename = filename
            pdf_filename = filename.replace('.tex', '.pdf')
        else:
            tex_filename = f"{filename}.tex"
            pdf_filename = f"{filename}.pdf"
        
        tex_file = temp_path / tex_filename
        pdf_file = temp_path / pdf_filename
        
        # Write LaTeX content to file
        async with aiofiles.open(tex_file, 'w') as f:
            await f.write(content)
        
        # Compile LaTeX
        cmd = [
            compiler,
            '-interaction=nonstopmode',
            '-output-directory', str(temp_path),
            str(tex_file)
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=temp_path
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=LATEX_TIMEOUT
            )
            
            # Check if PDF was generated
            if pdf_file.exists():
                # Upload PDF to file server with user-friendly name
                upload_result = await upload_pdf_to_file_server(
                    pdf_file, 
                    pdf_filename
                )
                
                if upload_result["success"]:
                    result = {
                        "success": True,
                        "file_id": upload_result["file_id"],
                        "download_url": upload_result["download_url"],
                        "filename": upload_result["filename"],
                        "size_bytes": pdf_file.stat().st_size
                    }
                    
                    # Include intermediate files if requested
                    if SAVE_INTERMEDIATE:
                        log_file = temp_path / f"{Path(tex_filename).stem}.log"
                        if log_file.exists():
                            async with aiofiles.open(log_file, 'r') as f:
                                result["compilation_log"] = await f.read()
                    
                    return result
                else:
                    return {
                        "success": False,
                        "error": f"Failed to upload PDF: {upload_result.get('error', 'Unknown error')}"
                    }
            else:
                # Compilation failed
                return {
                    "success": False,
                    "error": "PDF generation failed",
                    "stdout": stdout.decode('utf-8', errors='replace'),
                    "stderr": stderr.decode('utf-8', errors='replace')
                }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"Compilation timeout after {LATEX_TIMEOUT} seconds"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Compilation error: {str(e)}"
            }

def extract_packages(content: str) -> List[str]:
    """Extract package names from LaTeX content"""
    packages = []
    for line in content.split('\n'):
        line = line.strip()
        if line.startswith('\\usepackage'):
            # Extract package name(s)
            start = line.find('{')
            end = line.find('}', start)
            if start != -1 and end != -1:
                package_list = line[start+1:end]
                packages.extend([pkg.strip() for pkg in package_list.split(',')])
    return packages

# Health check endpoint
@mcp.custom_route(path="/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "LaTeX MCP Server",
        "compiler": LATEX_COMPILER,
        "output_dir": str(OUTPUT_DIR),
        "template_dir": str(TEMPLATE_DIR)
    })

# Server info endpoint - only for GET requests, let FastMCP handle POST
@mcp.custom_route(path="/info", methods=["GET"])
async def server_info_endpoint(request):
    """Server information endpoint"""
    return JSONResponse({
        "service": "LaTeX MCP Server",
        "version": "0.3.0",
        "description": "MCP server for LaTeX PDF compilation",
        "compiler": LATEX_COMPILER,
        "max_file_size": MAX_FILE_SIZE,
        "allowed_packages": ALLOWED_PACKAGES if ALLOWED_PACKAGES and ALLOWED_PACKAGES[0] else "all",
        "available_tools": ["upload_latex_file", "compile_latex_by_id", "compile_from_template", "list_templates"]
    })

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('SERVER_PORT', 8000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting LaTeX MCP Server on port {port}")
    logger.info(f"Output directory: {OUTPUT_DIR}")
    logger.info(f"Template directory: {TEMPLATE_DIR}")
    logger.info(f"LaTeX compiler: {LATEX_COMPILER}")
    
    mcp.run(transport="http", host="0.0.0.0", port=port)