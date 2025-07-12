#!/usr/bin/env python3
"""Test MCP initialization and session management"""

import asyncio
import httpx
import json

async def test_mcp_initialization():
    """Test proper MCP initialization sequence"""
    
    print("=== Testing MCP Initialization Sequence ===")
    
    async with httpx.AsyncClient() as client:
        # Step 1: Send initialize request
        print("\n1. Sending initialize request...")
        initialize_request = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": "test-client",
                    "version": "0.3.0"
                },
                "capabilities": {}
            }
        }
        
        response = await client.post(
            "http://localhost:8001/mcp/",
            json=initialize_request,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        session_id = response.headers.get("mcp-session-id")
        if session_id:
            print(f"Session ID received: {session_id}")
        
        if response.status_code == 200:
            try:
                init_result = response.json()
                print(f"Initialize result: {json.dumps(init_result, indent=2)}")
            except:
                print("Could not parse initialize response as JSON")
        
        # Step 2: Send initialized notification (if successful)
        if response.status_code == 200 and session_id:
            print("\n2. Sending initialized notification...")
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            response = await client.post(
                "http://localhost:8001/mcp/",
                json=initialized_notification,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Session-Id": session_id
                }
            )
            
            print(f"Notification Status Code: {response.status_code}")
            print(f"Notification Response: {response.text}")
        
        # Step 3: Now try tools/list with session ID
        if session_id:
            print("\n3. Sending tools/list request with session ID...")
            tools_request = {
                "jsonrpc": "2.0",
                "id": "tools-1",
                "method": "tools/list",
                "params": {}
            }
            
            response = await client.post(
                "http://localhost:8001/mcp/",
                json=tools_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Session-Id": session_id
                }
            )
            
            print(f"Tools list Status Code: {response.status_code}")
            print(f"Tools list Response: {response.text}")
            
            if response.status_code == 200:
                try:
                    tools_result = response.json()
                    print(f"Tools result: {json.dumps(tools_result, indent=2)}")
                except:
                    print("Could not parse tools response as JSON")
        
        # Step 4: Test tool call with session ID
        if session_id:
            print("\n4. Testing tool call with session ID...")
            tool_call_request = {
                "jsonrpc": "2.0",
                "id": "call-1",
                "method": "tools/call",
                "params": {
                    "name": "greet",
                    "arguments": {"name": "Test", "greeting": "Hello"}
                }
            }
            
            response = await client.post(
                "http://localhost:8001/mcp/",
                json=tool_call_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "Mcp-Session-Id": session_id
                }
            )
            
            print(f"Tool call Status Code: {response.status_code}")
            print(f"Tool call Response: {response.text}")
            
            if response.status_code == 200:
                try:
                    tool_result = response.json()
                    print(f"Tool result: {json.dumps(tool_result, indent=2)}")
                except:
                    print("Could not parse tool call response as JSON")

if __name__ == "__main__":
    asyncio.run(test_mcp_initialization())