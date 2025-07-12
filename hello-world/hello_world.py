#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "fastmcp>=2.10",
#     "uvicorn>=0.35",
#     "fastapi>=0.115"
# ]
# ///
"""
Hello World MCP Server

A minimal MCP server demonstrating FastMCP patterns with tools and resources.
"""

import os
import logging
from datetime import datetime
from fastmcp import FastMCP
from fastapi.responses import JSONResponse

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP("Hello World Server")

@mcp.tool
def greet(name: str, greeting: str = "Hello") -> str:
    """Generate a greeting message"""
    return f"{greeting}, {name}!"

@mcp.tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b

@mcp.tool
def get_timestamp() -> str:
    """Get the current timestamp"""
    return datetime.now().isoformat()

@mcp.resource("server://info")
def server_info() -> str:
    """Basic server information"""
    return f"""# Hello World MCP Server

- **Name**: Hello World Server
- **Version**: 0.3.0  
- **Description**: Minimal MCP server demonstrating tools and resources
- **Tools**: greet, add_numbers, get_timestamp
- **Resources**: server://info, server://status
- **Started**: {datetime.now().isoformat()}
"""

@mcp.resource("server://status")
def server_status() -> str:
    """Current server status"""
    return f"""# Server Status

- **Status**: Running
- **Uptime**: Active
- **Environment**: {os.getenv('ENVIRONMENT', 'development')}
- **Port**: {os.getenv('SERVER_PORT', '8000')}
- **Last Check**: {datetime.now().isoformat()}
"""

# Health check endpoint
@mcp.custom_route(path="/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "service": "Hello World MCP Server",
        "timestamp": datetime.now().isoformat()
    })

# Server info endpoint for HTTP discovery
@mcp.custom_route(path="/info", methods=["GET"])
async def server_info_endpoint(request):
    """Server information endpoint"""
    return JSONResponse({
        "service": "Hello World MCP Server",
        "version": "0.3.0",
        "description": "Minimal MCP server with basic tools",
        "available_tools": ["greet", "add_numbers", "get_timestamp"]
    })

if __name__ == "__main__":
    port = int(os.getenv('SERVER_PORT', 8000))
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    logger.info(f"Starting Hello World MCP Server on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    mcp.run(transport="http", host="0.0.0.0", port=port)