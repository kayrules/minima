#!/usr/bin/env python3
"""
Simple test script for the Minima MCP SSE Server
"""
import asyncio
import httpx
import json

async def test_sse_server():
    """Test the SSE MCP server"""
    base_url = "http://localhost:8002"
    
    async with httpx.AsyncClient() as client:
        # Test health endpoint
        print("Testing health endpoint...")
        response = await client.get(f"{base_url}/health")
        print(f"Health check: {response.status_code} - {response.json()}")
        
        # Test root endpoint
        print("\nTesting root endpoint...")
        response = await client.get(f"{base_url}/")
        print(f"Root: {response.status_code} - {response.json()}")
        
        # Test MCP request endpoint
        print("\nTesting MCP request endpoint...")
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list"
        }
        
        response = await client.post(
            f"{base_url}/mcp/request",
            json=mcp_request,
            timeout=10.0
        )
        print(f"MCP Request: {response.status_code}")
        try:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Response text: {response.text}")
            print(f"Error parsing JSON: {e}")

async def test_mcp_query():
    """Test the MCP query functionality"""
    base_url = "http://localhost:8002"
    
    async with httpx.AsyncClient() as client:
        # Test MCP query
        print("\nTesting MCP query...")
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "minima-query",
                "arguments": {
                    "text": "term deposit"
                }
            }
        }
        
        response = await client.post(
            f"{base_url}/mcp/request",
            json=mcp_request,
            timeout=30.0
        )
        print(f"MCP Query: {response.status_code}")
        try:
            result = response.json()
            print(f"Query Response: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Response text: {response.text}")
            print(f"Error parsing JSON: {e}")

if __name__ == "__main__":
    print("Testing Minima MCP SSE Server...")
    print("Make sure the server is running on http://localhost:8002")
    print("=" * 50)
    
    try:
        asyncio.run(test_sse_server())
        asyncio.run(test_mcp_query())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Test failed: {e}")