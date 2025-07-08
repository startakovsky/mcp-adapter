#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "watchdog>=4.0.0",
#     "httpx>=0.25.0",
#     "rich>=13.0.0",
#     "click>=8.0.0",
# ]
# ///
"""
LaTeX File Watcher and Compiler

A terminal-based workflow tool for iterating on LaTeX documents.
Watches .tex files for changes and auto-compiles via MCP tools.
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

import click
import httpx
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

console = Console()

class MCPSessionHelper:
    """Helper class for MCP session management"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = None
        self.client = None
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize MCP session with proper handshake"""
        self.client = httpx.AsyncClient(timeout=60.0)
            
        # Step 1: Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "latex-watch-client",
                    "version": "0.3.0"
                },
                "capabilities": {}
            }
        }
        
        response = await self.client.post(
            f"{self.base_url}/mcp/",
            json=init_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        
        if response.status_code != 200:
            raise RuntimeError(f"Initialize failed: {response.status_code} - {response.text}")
        
        # Extract session ID from response headers
        self.session_id = response.headers.get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError("No session ID returned from initialize")
        
        # Parse SSE response
        init_result = self._parse_mcp_response(response.text)
        
        # Step 2: Send initialized notification
        initialized_request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        }
        
        notify_response = await self.client.post(
            f"{self.base_url}/mcp/",
            json=initialized_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self.session_id
            }
        )
        
        if notify_response.status_code not in [200, 202]:
            raise RuntimeError(f"Initialized notification failed: {notify_response.status_code}")
        
        return init_result
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call MCP tool and return parsed result"""
        if not self.client or not self.session_id:
            raise RuntimeError("Session not initialized")
        
        if arguments is None:
            arguments = {}
            
        request = {
            "jsonrpc": "2.0",
            "id": f"watch_{tool_name}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = await self.client.post(
            f"{self.base_url}/mcp/",
            json=request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "Mcp-Session-Id": self.session_id
            }
        )
        
        if response.status_code == 200:
            return self._parse_mcp_response(response.text)
        else:
            return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
    
    def _parse_mcp_response(self, response_text: str) -> Dict[str, Any]:
        """Parse MCP response from SSE format"""
        lines = response_text.strip().split('\n')
        
        # Find the data line
        data_line = None
        for line in lines:
            if line.startswith('data: '):
                data_line = line[6:]  # Remove 'data: ' prefix
                break
        
        if not data_line:
            return {"success": False, "error": f"No data line found in SSE response: {response_text}"}
        
        try:
            data = json.loads(data_line)
            if "result" in data:
                result = data["result"]
                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if content and isinstance(content, list):
                        text = content[0].get("text", "{}")
                        return json.loads(text)
                return result
            elif "error" in data:
                return {"success": False, "error": data["error"]}
            else:
                return data
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON in SSE data: {data_line}"}
        
        return {"success": False, "error": "Failed to parse response"}
    
    async def cleanup(self):
        """Clean up the session"""
        if self.client:
            await self.client.aclose()

class LaTeXHandler(FileSystemEventHandler):
    """File system event handler for LaTeX files"""
    
    def __init__(self, gateway_url: str, file_path: Path):
        self.gateway_url = gateway_url
        self.file_path = file_path
        self.file_id: Optional[str] = None
        self.last_compile_time = 0
        self.compile_debounce = 2.0  # seconds
        self.session_helper = None
        
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
            
        if Path(event.src_path) == self.file_path:
            current_time = time.time()
            if current_time - self.last_compile_time > self.compile_debounce:
                self.last_compile_time = current_time
                asyncio.create_task(self.compile_file())
    
    async def compile_file(self):
        """Compile the LaTeX file via MCP tools"""
        try:
            # Read file content
            with open(self.file_path, 'r') as f:
                content = f.read()
            
            # Initialize session helper if needed
            if not self.session_helper:
                self.session_helper = MCPSessionHelper(self.gateway_url)
                await self.session_helper.initialize()
            
            # Upload file if not already uploaded, or update existing
            if not self.file_id:
                upload_result = await self.session_helper.call_tool(
                    "latex_upload_latex_file",
                    {
                        "content": content,
                        "filename": self.file_path.name
                    }
                )
                if upload_result.get("success"):
                    self.file_id = upload_result["file_id"]
                    console.print(f"✓ Uploaded {self.file_path.name} (ID: {self.file_id[:8]})")
                else:
                    console.print(f"✗ Upload failed: {upload_result.get('error', 'Unknown error')}")
                    return
            else:
                # Update existing file (upload new version)
                upload_result = await self.session_helper.call_tool(
                    "latex_upload_latex_file",
                    {
                        "content": content,
                        "filename": self.file_path.name
                    }
                )
                if upload_result.get("success"):
                    self.file_id = upload_result["file_id"]
            
            # Compile file
            compile_result = await self.session_helper.call_tool(
                "latex_compile_latex_by_id",
                {
                    "file_id": self.file_id,
                    "output_filename": self.file_path.stem
                }
            )
            
            if compile_result.get("success"):
                pdf_path = compile_result["pdf_path"]
                size_kb = compile_result["size_bytes"] / 1024
                console.print(f"✓ Compiled successfully: {pdf_path} ({size_kb:.1f}KB)")
                
                # Auto-open PDF if on macOS
                if sys.platform == "darwin":
                    import subprocess
                    subprocess.run(["open", pdf_path], check=False)
            else:
                console.print(f"✗ Compilation failed: {compile_result.get('error', 'Unknown error')}")
                
                # Get detailed errors
                error_result = await self.session_helper.call_tool(
                    "latex_get_compilation_errors",
                    {"file_id": self.file_id}
                )
                if error_result.get("success") and error_result.get("errors"):
                    console.print("Errors:")
                    for error in error_result["errors"]:
                        console.print(f"  • {error}")
                        
        except Exception as e:
            console.print(f"✗ Error: {e}")
    


@click.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--gateway", default="http://localhost:8080", help="Gateway URL")
@click.option("--no-auto-open", is_flag=True, help="Don't auto-open PDF on macOS")
def main(file_path: Path, gateway: str, no_auto_open: bool):
    """
    Watch a LaTeX file and auto-compile on changes.
    
    FILE_PATH: Path to the .tex file to watch
    """
    
    if not file_path.suffix == ".tex":
        console.print("Error: File must have .tex extension")
        sys.exit(1)
    
    console.print(f"📁 Watching: {file_path}")
    console.print(f"🌐 Gateway: {gateway}")
    console.print(f"💾 Auto-open: {'disabled' if no_auto_open else 'enabled (macOS only)'}")
    console.print()
    
    # Create event handler
    handler = LaTeXHandler(gateway, file_path)
    
    # Set up file watcher
    observer = Observer()
    observer.schedule(handler, path=str(file_path.parent), recursive=False)
    
    try:
        observer.start()
        console.print("🔍 Watching for changes... (Press Ctrl+C to stop)")
        
        # Initial compilation
        asyncio.run(handler.compile_file())
        
        # Keep the script running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        console.print("\n👋 Stopping file watcher...")
        observer.stop()
        
        # Cleanup session
        if handler.session_helper:
            asyncio.run(handler.session_helper.cleanup())
    
    observer.join()


if __name__ == "__main__":
    main()