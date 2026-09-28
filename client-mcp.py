import asyncio
import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    # Revert to the explicit /sse endpoint
    server_url = "http://localhost:8081/" 
    print(f"Connecting to OpenCost MCP server at {server_url}...")

    # Inject standard headers that Go HTTP routers often require
    custom_headers = {
        "User-Agent": "MCP-Python-Client/1.0",
        "Origin": "http://localhost:8081"
    }

    try:
        async with sse_client(url=server_url, headers=custom_headers) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                print("Session initialized successfully!\n")
                
                cost_result = await session.call_tool(
                    "get_allocation_costs", 
                    {"window": "7d", "aggregate": "namespace"}
                )
                
                print("\nCost Result:")
                for content in cost_result.content:
                    print(content.text)

    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e.response.status_code}")
        # This will print exactly why OpenCost rejected the request
        print(f"Server Response Body: {e.response.text}")
    except Exception as e:
        print(f"Failed to connect or execute: {e}")

if __name__ == "__main__":
    asyncio.run(main())
