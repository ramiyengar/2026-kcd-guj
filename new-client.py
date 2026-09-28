import asyncio
import httpx

async def main():
    server_url = "http://localhost:8081" 
    print(f"Connecting to OpenCost MCP server at {server_url}...")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "MCP-Python-Client/1.0",
        "Origin": "http://localhost:8081"
    }

    # We use a single httpx.AsyncClient session to automatically retain 
    # any Set-Cookie headers the Go server might use for state tracking.
    async with httpx.AsyncClient() as client:
        try:
            # ==========================================
            # STEP 1: The Initialize Handshake
            # ==========================================
            print("1. Sending 'initialize' request...")
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "python-client",
                        "version": "1.0.0"
                    }
                }
            }
            
            resp1 = await client.post(server_url, headers=headers, json=init_payload, timeout=10.0)
            resp1.raise_for_status()
            
            # If the server uses explicit header-based state tracking (MCP standard):
            session_id = resp1.headers.get("Mcp-Session-Id")
            if session_id:
                headers["Mcp-Session-Id"] = session_id

            # ==========================================
            # STEP 2: The Initialized Notification
            # ==========================================
            print("2. Sending 'notifications/initialized'...")
            notif_payload = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            # Notifications do not expect a response body, but we ensure it didn't 400/500
            resp2 = await client.post(server_url, headers=headers, json=notif_payload, timeout=5.0)
            resp2.raise_for_status()

            # ==========================================
            # STEP 3: The Tool Execution
            # ==========================================
            print("3. Executing tool: get_allocation_costs...")
            tool_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "get_allocation_costs",
                    "arguments": {
                        "window": "7d",
                        "aggregate": "namespace"
                    }
                }
            }
            
            resp3 = await client.post(server_url, headers=headers, json=tool_payload, timeout=30.0)
            resp3.raise_for_status()
            
            # Output parsing
            data = resp3.json()
            if "error" in data:
                print(f"\nMCP Server Error: {data['error']}")
            else:
                print("\nCost Result:")
                for content in data.get("result", {}).get("content", []):
                    print(content.get("text", ""))

        except httpx.HTTPStatusError as e:
            print(f"\nHTTP Error: {e.response.status_code}")
            print(f"Server Response Body: {e.response.text}")
        except Exception as e:
            print(f"Failed to execute protocol handshake: {e}")

if __name__ == "__main__":
    asyncio.run(main())
