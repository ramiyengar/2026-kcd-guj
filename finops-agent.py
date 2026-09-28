import asyncio
import json
import httpx

# Configuration
OPENCOST_URL = "http://localhost:8081"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1"  # Or qwen2.5, mistral, etc.

# OpenCost MCP Tool Schemas for Ollama Function Calling
OPENCOST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_allocation_costs",
            "description": "Get Kubernetes resource allocation costs aggregated by dimension (e.g., namespace, pod, node, controller, service).",
            "parameters": {
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": "Time window for cost calculation. Examples: '24h', '7d', '30d'."
                    },
                    "aggregate": {
                        "type": "string",
                        "description": "Aggregation dimension. Allowed values: 'namespace', 'pod', 'node', 'controller', 'service'."
                    }
                },
                "required": ["window", "aggregate"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_asset_costs",
            "description": "Get physical and cloud asset costs (nodes, disks, network load balancers).",
            "parameters": {
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": "Time window for cost calculation. Examples: '24h', '7d', '30d'."
                    },
                    "aggregate": {
                        "type": "string",
                        "description": "Aggregation dimension. Examples: 'type', 'provider', 'node'."
                    }
                },
                "required": ["window", "aggregate"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cloud_costs",
            "description": "Get overarching cloud provider billing details (AWS, GCP, Azure).",
            "parameters": {
                "type": "object",
                "properties": {
                    "window": {
                        "type": "string",
                        "description": "Time window for cost calculation. Examples: '24h', '7d', '30d'."
                    },
                    "aggregate": {
                        "type": "string",
                        "description": "Aggregation dimension. Examples: 'service', 'region'."
                    }
                },
                "required": ["window", "aggregate"]
            }
        }
    }
]

async def execute_mcp_tool(tool_name: str, arguments: dict) -> str:
    """Executes the stateful 3-step MCP handshake and calls the OpenCost tool."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "MCP-Python-Client/1.0",
        "Origin": "http://localhost:8081"
    }

    async with httpx.AsyncClient() as client:
        try:
            # Step 1: Initialize
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "finops-cli", "version": "1.0.0"}
                }
            }
            r1 = await client.post(OPENCOST_URL, headers=headers, json=init_payload, timeout=10.0)
            r1.raise_for_status()

            session_id = r1.headers.get("Mcp-Session-Id")
            if session_id:
                headers["Mcp-Session-Id"] = session_id

            # Step 2: Initialized Notification
            notif_payload = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            r2 = await client.post(OPENCOST_URL, headers=headers, json=notif_payload, timeout=5.0)
            r2.raise_for_status()

            # Step 3: Execute Tool
            tool_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            r3 = await client.post(OPENCOST_URL, headers=headers, json=tool_payload, timeout=30.0)
            r3.raise_for_status()

            data = r3.json()
            if "error" in data:
                return f"MCP Error: {data['error']}"
            
            # Extract text response from result content
            contents = data.get("result", {}).get("content", [])
            return "\n".join([c.get("text", "") for c in contents])

        except Exception as e:
            return f"Failed to execute MCP tool: {str(e)}"

async def ask_ollama(messages: list, tools: list = None) -> dict:
    """Sends a chat request to the local Ollama instance."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient() as client:
        resp = await client.post(OLLAMA_URL, json=payload, timeout=60.0)
        resp.raise_for_status()
        return resp.json()

async def main():
    print("==================================================")
    print(" 🚀 K8s FinOps AI Agent (OpenCost MCP + Ollama)  ")
    print("==================================================")
    print("Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            user_input = input("FinOps AI > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                break

            messages = [
                {
                    "role": "system",
                    "content": "You are a FinOps Kubernetes assistant. You have access to tools that fetch live OpenCost cost data. Always use the provided tools to answer cost-related queries."
                },
                {"role": "user", "content": user_input}
            ]

            print("🤔 Analyzing query with Ollama...")
            response = await ask_ollama(messages, tools=OPENCOST_TOOLS)
            message = response.get("message", {})

            # Check if Ollama requested a tool call
            tool_calls = message.get("tool_calls", [])

            if tool_calls:
                for tool_call in tool_calls:
                    func = tool_call.get("function", {})
                    tool_name = func.get("name")
                    arguments = func.get("arguments", {})

                    print(f"🔧 [MCP Tool Request] -> {tool_name}({json.dumps(arguments)})")
                    print("📊 Querying OpenCost MCP server...")

                    # Call OpenCost MCP
                    mcp_data = await execute_mcp_tool(tool_name, arguments)

                    # Feed raw data back to Ollama for final summarization
                    print("✨ Summarizing response...")
                    summary_messages = messages + [
                        message,
                        {
                            "role": "tool",
                            "content": f"OpenCost Data:\n{mcp_data}"
                        },
                        {
                            "role": "user",
                            "content": "Summarize the cost data cleanly for a DevOps engineer."
                        }
                    ]

                    final_response = await ask_ollama(summary_messages)
                    print(f"\n🤖 Answer:\n{final_response.get('message', {}).get('content')}\n")
            else:
                # Direct response if no tool was needed
                print(f"\n🤖 Answer:\n{message.get('content')}\n")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")

if __name__ == "__main__":
    asyncio.run(main())
