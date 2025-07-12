#!/usr/bin/env python3
"""Debug script to see the actual MCP error response"""

import asyncio
import httpx
import json

async def debug_mcp_error():
    """Debug MCP error response"""
    async with httpx.AsyncClient() as client:
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        response = await client.post(
            "http://localhost:8001/mcp/",
            json=mcp_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code != 200:
            try:
                error_data = response.json()
                print(f"Error JSON: {json.dumps(error_data, indent=2)}")
            except:
                print("Could not parse error response as JSON")

if __name__ == "__main__":
    asyncio.run(debug_mcp_error())