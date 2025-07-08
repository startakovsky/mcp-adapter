#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "httpx>=0.25.0",
#     "rich>=13.0.0",
# ]
# ///
"""
Example LaTeX workflow using file-based MCP tools

Demonstrates the token-efficient workflow:
1. Upload LaTeX file once
2. Compile multiple times with minimal token usage
3. Get detailed errors only when needed
"""

import asyncio
import json
import sys
from typing import Dict, Any

import httpx
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

GATEWAY_URL = "http://localhost:8080"

class MCPToolHelper:
    """Helper for MCP tool calls with proper session management"""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session_id = None
        self.client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(timeout=60.0)
        await self.initialize()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
    
    async def initialize(self) -> Dict[str, Any]:
        """Initialize MCP session with proper handshake"""
        if not self.client:
            raise RuntimeError("Client not initialized")
            
        # Step 1: Send initialize request
        init_request = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "example-workflow-client",
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
            "id": f"example_{tool_name}",
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
                        # Try to parse as JSON, but if it fails, treat as plain text
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            # If parsing fails, it's a plain text response (possibly an error)
                            if result.get("isError"):
                                return {"success": False, "error": text}
                            else:
                                return {"success": True, "message": text}
                return result
            elif "error" in data:
                return {"success": False, "error": data["error"]}
            else:
                return data
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON in SSE data: {data_line}"}
        
        return {"success": False, "error": "Failed to parse response"}

async def demonstrate_workflow():
    """Demonstrate the file-based LaTeX workflow"""
    
    console.print(Panel.fit("🚀 LaTeX File-Based Workflow Demo", style="bold blue"))
    
    async with MCPToolHelper(GATEWAY_URL) as helper:
        
        # Sample LaTeX document
        latex_content = r"""
\documentclass{article}
\usepackage{amsmath}
\usepackage{graphicx}

\title{Token-Efficient LaTeX Workflow}
\author{MCP Studio}
\date{\today}

\begin{document}

\maketitle

\section{Introduction}
This document demonstrates the new file-based LaTeX workflow that dramatically reduces token usage.

\section{Mathematical Example}
Here's Einstein's famous equation:
\begin{equation}
E = mc^2
\end{equation}

\section{Benefits}
\begin{itemize}
\item \textbf{Reduced token usage}: Upload once, compile many times
\item \textbf{Better error handling}: Get detailed errors only when needed
\item \textbf{Workflow efficiency}: Perfect for iterative document development
\end{itemize}

\section{Workflow Steps}
\begin{enumerate}
\item Upload \texttt{.tex} file to get file ID
\item Compile by file ID (minimal tokens)
\item Get detailed errors if compilation fails
\item Iterate on document and recompile
\end{enumerate}

\end{document}
"""
        
        console.print("\n📄 LaTeX Document:")
        syntax = Syntax(latex_content.strip(), "latex", theme="monokai", line_numbers=True)
        console.print(syntax)
        
        try:
            # Step 1: Upload file
            console.print("\n🔄 Step 1: Uploading LaTeX file...")
            upload_result = await helper.call_tool(
                "latex_upload_latex_file",
                {
                    "content": latex_content,
                    "filename": "workflow_demo.tex"
                }
            )
        
            if upload_result.get("success"):
                file_id = upload_result["file_id"]
                size_kb = upload_result["size_bytes"] / 1024
                console.print(f"✅ Upload successful!")
                console.print(f"   File ID: {file_id}")
                console.print(f"   Size: {size_kb:.1f} KB")
            else:
                console.print(f"❌ Upload failed: {upload_result.get('error')}")
                return
        
            # Step 2: Compile file (multiple times to show efficiency)
            console.print(f"\n🔄 Step 2: Compiling document (file ID: {file_id[:8]}...)...")
            
            for i in range(3):
                console.print(f"\n   Compilation #{i+1}:")
                compile_result = await helper.call_tool(
                    "latex_compile_latex_by_id",
                    {
                        "file_id": file_id,
                        "output_filename": f"demo_output_{i+1}"
                    }
                )
            
                if compile_result.get("success"):
                    pdf_path = compile_result["pdf_path"]
                    size_kb = compile_result["size_bytes"] / 1024
                    console.print(f"   ✅ Success: {pdf_path} ({size_kb:.1f} KB)")
                else:
                    console.print(f"   ❌ Failed: {compile_result.get('error')}")
                    
                    # Step 3: Get detailed errors
                    console.print(f"\n🔄 Step 3: Getting detailed error information...")
                    error_result = await helper.call_tool(
                        "latex_get_compilation_errors",
                        {"file_id": file_id}
                    )
                    
                    if error_result.get("success") and error_result.get("errors"):
                        console.print("   📋 Compilation errors:")
                        for error in error_result["errors"]:
                            console.print(f"      • {error}")
                    break
        
            # Show token usage comparison
            console.print(Panel.fit("""
🎯 Token Usage Comparison:

Traditional approach (per compilation):
• Full LaTeX content: ~2,000 tokens
• Compilation log: ~3,000 tokens  
• Total per compile: ~5,000 tokens
• 3 compilations: ~15,000 tokens

File-based approach:
• Upload once: ~2,000 tokens
• Per compilation: ~50 tokens
• 3 compilations: ~2,150 tokens
• 📉 87% reduction in token usage!
            """, style="green", title="💡 Efficiency Gains"))
            
        except Exception as e:
            console.print(f"\n❌ Error: {e}")
            console.print("\n💡 Make sure the MCP Studio services are running:")
            console.print("   docker-compose up -d")

if __name__ == "__main__":
    asyncio.run(demonstrate_workflow())