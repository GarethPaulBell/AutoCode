#!/usr/bin/env python3
import subprocess
import json
import sys

# Test JSON-RPC request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
}

# Start the MCP server
proc = subprocess.Popen(
    [sys.executable, "src/autocode/mcp_autocode_server.py"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    cwd="c:\\Users\\GGPC\\Documents\\GitHub\\AutoCode"
)

# Send the request
proc.stdin.write(json.dumps(request) + "\n")
proc.stdin.flush()

# Read the response
response = proc.stdout.readline()
proc.terminate()

print("Response:", response)

# Check if response is valid JSON
try:
    parsed = json.loads(response.strip())
    print("✅ Valid JSON response")
    print("Tools count:", len(parsed.get("result", {}).get("tools", [])))
except json.JSONDecodeError as e:
    print("❌ Invalid JSON response:", e)
    print("Raw response:", repr(response))
